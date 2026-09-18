"""Pure governance & node graph policies for scripts (Rule R2)."""

from __future__ import annotations

from typing import Any

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


def validate_node_graph(entry_node_id: str, nodes: list[dict[str, Any]]) -> list[str]:
    """Validate graph structure returning a list of validation error messages.

    Checks:
    1. entry_node_id points to an existing node.
    2. Duplicate node IDs.
    3. Transition target node IDs exist or specify valid terminal flags (endCall).
    """
    problems: list[str] = []
    if not nodes:
        return ["Node graph cannot be empty"]

    node_ids: set[str] = set()
    for idx, node in enumerate(nodes):
        nid = node.get("id")
        if not nid:
            problems.append(f"Node at index {idx} missing 'id'")
        elif nid in node_ids:
            problems.append(f"Duplicate node ID '{nid}'")
        else:
            node_ids.add(str(nid))

    if entry_node_id not in node_ids:
        problems.append(f"Entry node ID '{entry_node_id}' does not exist in nodes graph")

    for node in nodes:
        nid = node.get("id")
        transitions = node.get("transitions") or []
        for t_idx, tr in enumerate(transitions):
            next_id = tr.get("nextNodeId")
            end_call = tr.get("endCall", False)
            if not end_call and next_id and next_id not in node_ids:
                problems.append(
                    f"Node '{nid}' transition {t_idx} references non-existent target node '{next_id}'"
                )

    return problems
