"""Pure governance & node graph policies for scripts (Rule R2, Steps 20-21)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GraphError:
    node_id: str
    code: str
    details: str | None = None


ALLOWED: set[tuple[str, str]] = {
    ("draft", "pending_approval"),
    ("pending_approval", "approved"),
    ("pending_approval", "draft"),
    ("approved", "active"),
    ("active", "archived"),
    ("approved", "archived"),
}


def can_transition(frm: str, to: str) -> bool:
    """Return True if the state transition from `frm` to `to` is allowed."""
    return (frm, to) in ALLOWED


def can_edit_version(status: str) -> bool:
    """Only draft versions can be mutated in-place."""
    return status == "draft"


def validate_graph(
    nodes: list[dict[str, Any]],
    entry_id: str,
    profile: Any = None,
) -> list[GraphError]:
    """Pure node graph structural and compliance validation (Step 21).

    Checks:
    - MISSING_ENTRY: entry_id not in nodes
    - DANGLING_TRANSITION: transition target not in nodes
    - UNREACHABLE: node not reachable via BFS from entry_id
    - DEAD_END: non-terminal node with no transitions
    - BENEFITS_BEFORE_DISCLAIMER: if profile enforces tpmo_disclaimer_precedes_benefits,
      ensures disclaimer node comes before any benefits node on all paths.
    """
    errs: list[GraphError] = []
    if not nodes:
        return [
            GraphError(
                node_id="root", code="EMPTY_GRAPH", details="Node graph is empty"
            )
        ]

    by_id: dict[str, dict[str, Any]] = {}
    for idx, n in enumerate(nodes):
        nid = n.get("id")
        if not nid:
            errs.append(
                GraphError(
                    node_id=f"idx_{idx}",
                    code="MISSING_ID",
                    details=f"Node at index {idx} missing id",
                )
            )
        else:
            by_id[str(nid)] = n

    ids = set(by_id.keys())
    if entry_id not in ids:
        errs.append(
            GraphError(
                node_id=entry_id,
                code="MISSING_ENTRY",
                details=f"Entry node '{entry_id}' not found",
            )
        )

    # Transition targets validation & dead end detection
    for n in nodes:
        nid = str(n.get("id", ""))
        transitions = n.get("transitions") or []
        is_terminal = n.get("terminal") is True or n.get("isTerminal") is True

        for t in transitions:
            next_id = t.get("nextNodeId")
            end_call = t.get("endCall") is True
            if not end_call and next_id and str(next_id) not in ids:
                errs.append(
                    GraphError(
                        node_id=nid,
                        code="DANGLING_TRANSITION",
                        details=str(next_id),
                    )
                )

        if not is_terminal and not transitions:
            errs.append(
                GraphError(
                    node_id=nid,
                    code="DEAD_END",
                    details=f"Node '{nid}' has no transitions and is not terminal",
                )
            )

    # Reachability via BFS
    reachable: set[str] = set()
    if entry_id in ids:
        queue = [entry_id]
        reachable.add(entry_id)
        while queue:
            curr_id = queue.pop(0)
            curr_node = by_id.get(curr_id)
            if not curr_node:
                continue
            for t in curr_node.get("transitions") or []:
                nxt = t.get("nextNodeId")
                if nxt and str(nxt) in ids and str(nxt) not in reachable:
                    reachable.add(str(nxt))
                    queue.append(str(nxt))

    for n in nodes:
        nid = str(n.get("id", ""))
        if nid and nid not in reachable:
            errs.append(
                GraphError(
                    node_id=nid,
                    code="UNREACHABLE",
                    details=f"Node '{nid}' is not reachable from entry",
                )
            )

    # Compliance check: disclaimer precedes benefits
    rule_mode = None
    if profile is not None:
        if hasattr(profile, "rule"):
            rule_mode = profile.rule("tpmo_disclaimer_precedes_benefits")
        elif isinstance(profile, dict):
            rule_mode = profile.get("rules", {}).get(
                "tpmo_disclaimer_precedes_benefits"
            )

    if rule_mode == "enforce" and entry_id in ids:

        def all_paths(start_id: str) -> list[list[str]]:
            paths: list[list[str]] = []

            def dfs(curr: str, current_path: list[str], visited: set[str]):
                current_path.append(curr)
                node = by_id.get(curr)
                transitions = (node.get("transitions") or []) if node else []
                next_nodes = [
                    str(t.get("nextNodeId"))
                    for t in transitions
                    if t.get("nextNodeId") and str(t.get("nextNodeId")) in ids
                ]
                if not next_nodes:
                    paths.append(list(current_path))
                else:
                    for nxt in next_nodes:
                        if nxt not in visited:
                            visited.add(nxt)
                            dfs(nxt, current_path, visited)
                            visited.remove(nxt)
                        else:
                            paths.append(list(current_path) + [nxt])
                current_path.pop()

            dfs(start_id, [], {start_id})
            return paths

        for path in all_paths(entry_id):
            seen_disc = False
            for nid in path:
                node = by_id.get(nid, {})
                if node.get("complianceRole") == "tpmo_disclaimer":
                    seen_disc = True
                if node.get("discussesBenefits") and not seen_disc:
                    errs.append(
                        GraphError(
                            node_id=nid,
                            code="BENEFITS_BEFORE_DISCLAIMER",
                            details=f"Node '{nid}' discusses benefits before disclaimer",
                        )
                    )
                    break

    return errs


def validate_node_graph(entry_node_id: str, nodes: list[dict[str, Any]]) -> list[str]:
    """Compatibility wrapper returning formatted strings."""
    errs = validate_graph(nodes, entry_node_id)
    return [f"{e.code}: {e.details or e.node_id}" for e in errs]
