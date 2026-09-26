"""Tests for the scripts module.

Covers:
- Pure state machine transition rules (can_transition)
- Pure node graph structural validation
- B3-3 approved Medicare script bundle validation & Redis bundle compilation
- Script CRUD HTTP lifecycle (/scripts)
- Versioning, submit, approve, reject, activate workflow
- Version diffing engine
- Interactive conversation flow simulator
- Approval queue listing (/scripts/approvals)
- Integration with campaign start guard & script binding
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.modules.compliance.policies import compile_script_bundle
from app.modules.compliance.service import publish_bundle_to_redis
from app.modules.scripts.policies import (
    can_transition,
    validate_graph,
    validate_node_graph,
)

GRAPH_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "graph"
APPROVED_MEDICARE_GRAPH = json.loads(
    (GRAPH_FIXTURES_DIR / "approved_medicare.json").read_text(encoding="utf-8")
)


class StrictComplianceProfile:
    def rule(self, name: str) -> str:
        if name == "tpmo_disclaimer_precedes_benefits":
            return "enforce"
        return "off"


STRICT = StrictComplianceProfile()


class MemoryRedis:
    def __init__(self):
        self._store: dict[str, bytes] = {}

    async def set(self, key: str, value: str):
        self._store[key] = value.encode() if isinstance(value, str) else value

    async def get(self, key: str):
        return self._store.get(key)


# ---------------------------------------------------------------------------
# 1. Pure State Machine & Policies Tests
# ---------------------------------------------------------------------------


def test_state_machine_allowed_transitions():
    assert can_transition("draft", "pending_approval") is True
    assert can_transition("pending_approval", "approved") is True
    assert can_transition("pending_approval", "draft") is True
    assert can_transition("approved", "active") is True
    assert can_transition("active", "archived") is True
    assert can_transition("approved", "archived") is True


def test_state_machine_disallowed_transitions():
    assert can_transition("draft", "approved") is False
    assert can_transition("draft", "active") is False
    assert can_transition("pending_approval", "active") is False
    assert can_transition("archived", "draft") is False
    assert can_transition("archived", "active") is False
    assert can_transition("active", "draft") is False


def test_node_graph_validation_valid():
    nodes = [
        {
            "id": "node-1",
            "type": "greeting",
            "label": "Greeting",
            "prompt": "Hello",
            "transitions": [{"when": "always", "nextNodeId": "node-2"}],
        },
        {
            "id": "node-2",
            "type": "closing",
            "label": "Closing",
            "prompt": "Goodbye",
            "transitions": [{"when": "always", "endCall": True}],
        },
    ]
    problems = validate_node_graph("node-1", nodes)
    assert problems == []


def test_node_graph_validation_invalid_entry_and_target():
    nodes = [
        {
            "id": "node-1",
            "type": "greeting",
            "label": "Greeting",
            "prompt": "Hello",
            "transitions": [{"when": "always", "nextNodeId": "missing-node"}],
        },
    ]
    problems = validate_node_graph("non-existent-entry", nodes)
    assert len(problems) >= 2
    assert any("non-existent-entry" in p for p in problems)
    assert any("missing-node" in p for p in problems)


# ---------------------------------------------------------------------------
# B3-3. Approved Medicare Script Bundle Validation & Redis Compilation
# ---------------------------------------------------------------------------


def load_approved_medicare_graph() -> tuple[str, list[dict]]:
    entry = APPROVED_MEDICARE_GRAPH["entryNodeId"]
    nodes = APPROVED_MEDICARE_GRAPH["nodes"]
    return entry, nodes


def test_approved_medicare_bundle_passes_strict_validation():
    """Authored budget must be structurally valid and compliance-clean under strict profile."""
    entry, nodes = load_approved_medicare_graph()
    problems = validate_graph(nodes, entry, profile=STRICT)
    assert problems == []


def test_approved_medicare_bundle_structural_rules():
    """Entry exists, every transition target resolves, all nodes reachable, terminals declared."""
    entry, nodes = load_approved_medicare_graph()
    node_ids = {n["id"] for n in nodes}
    assert entry == "n_greeting"
    assert entry in node_ids

    for node in nodes:
        assert node["id"] in node_ids
        for trans in node.get("transitions", []):
            if "nextNodeId" in trans:
                assert trans["nextNodeId"] in node_ids

    problems = validate_graph(nodes, entry)
    assert problems == []


def test_approved_medicare_bundle_disclaimer_precedes_benefits():
    """tpmo_disclaimer must appear before every discussesBenefits node on all paths."""
    entry, nodes = load_approved_medicare_graph()
    problems = validate_graph(nodes, entry, profile=STRICT)
    assert not any(e.code == "BENEFITS_BEFORE_DISCLAIMER" for e in problems)

    disclaimer_index = nodes.index(
        next(n for n in nodes if n.get("complianceRole") == "tpmo_disclaimer")
    )
    benefits_indices = [
        i for i, n in enumerate(nodes) if n.get("discussesBenefits") is True
    ]
    assert benefits_indices
    for benefit_idx in benefits_indices:
        assert disclaimer_index < benefit_idx


def test_approved_medicare_bundle_benefits_before_disclaimer_fails():
    """A path that reaches a benefits node without passing the disclaimer must trip the rule."""
    entry, nodes = load_approved_medicare_graph()
    nodes = [dict(n) for n in nodes]
    # Redirect the greeting straight to the first benefit-discussing question,
    # bypassing the tpmo_disclaimer node entirely.
    greeting = next(n for n in nodes if n["id"] == "n_greeting")
    benefits = [n for n in nodes if n.get("discussesBenefits") is True]
    greeting["transitions"] = [{"when": "always", "nextNodeId": benefits[0]["id"]}]

    problems = validate_graph(nodes, entry, profile=STRICT)
    assert any(e.code == "BENEFITS_BEFORE_DISCLAIMER" for e in problems)


def test_approved_medicare_bundle_activation_path():
    """draft -> pending_approval -> approved -> active is a legal lifecycle for the bundle."""
    assert can_transition("draft", "pending_approval")
    assert can_transition("pending_approval", "approved")
    assert can_transition("approved", "active")
    assert not can_transition("draft", "active")


@pytest.mark.asyncio
async def test_approved_medicare_bundle_compiles_to_redis():
    """Full bundle compilation mirrors STEP 25: version activates, bundle is published."""
    redis = MemoryRedis()
    entry, nodes = load_approved_medicare_graph()
    campaign_id = "camp-001"
    version_id = "ver-001"
    script_id = "script-001"

    bundle = compile_script_bundle(
        {
            "id": version_id,
            "script_id": script_id,
            "version": 1,
            "entry_node_id": entry,
            "nodes": nodes,
        }
    )
    assert bundle["entryNodeId"] == "n_greeting"
    assert {n["id"] for n in bundle["nodes"]} == {n["id"] for n in nodes}
    assert (
        bundle["complianceProfile"]["rules"]["tpmo_disclaimer_precedes_benefits"]
        == "enforce"
    )

    await publish_bundle_to_redis(redis, campaign_id, version_id, bundle)

    ptr = await redis.get(f"cp:campaign:{campaign_id}:active_script")
    assert ptr is not None
    assert ptr.decode() == version_id

    raw_bundle = await redis.get(f"cp:script:bundle:{version_id}")
    assert raw_bundle is not None
    published = json.loads(raw_bundle.decode())
    assert published["entryNodeId"] == entry
    assert len(published["nodes"]) == 6


# ---------------------------------------------------------------------------
# 2. HTTP Surface & Endpoints Tests
# ---------------------------------------------------------------------------


async def test_scripts_requires_auth(client):
    resp = await client.get("/scripts")
    assert resp.status_code == 401


async def test_create_list_and_get_script(client, seeded):
    # 1. Create script
    payload = {
        "name": "Medicare Qualification Script",
        "description": "Standard Medicare Part C/D qualification script",
        "language": "en-US",
        "greeting": "Hello this is Alex from SmartBrains BPO.",
        "consent": "This call is recorded under TCPA rules.",
        "qualificationQuestions": [
            "Are you 65 years or older?",
            "Do you have active Medicare Part A and B?",
        ],
        "transferMessage": "Connecting to a licensed verifier now.",
        "disqualificationMessage": "Thank you, goodbye.",
    }
    create_resp = await client.post("/scripts", headers=seeded["headers"], json=payload)
    assert create_resp.status_code == 201
    s_data = create_resp.json()["data"]
    script_id = s_data["id"]
    assert s_data["name"] == "Medicare Qualification Script"
    assert s_data["status"] == "draft"
    assert s_data["currentVersion"] == 1

    # 2. List scripts
    list_resp = await client.get("/scripts", headers=seeded["headers"])
    assert list_resp.status_code == 200
    list_body = list_resp.json()
    assert len(list_body["data"]) >= 1
    assert any(s["id"] == script_id for s in list_body["data"])

    # 3. Get single script detail
    get_resp = await client.get(f"/scripts/{script_id}", headers=seeded["headers"])
    assert get_resp.status_code == 200
    detail = get_resp.json()["data"]
    assert detail["id"] == script_id
    assert len(detail["versions"]) == 1
    assert detail["versions"][0]["version"] == 1


async def test_script_lifecycle_workflow(client, seeded):
    """Test full version lifecycle: create -> edit -> submit -> reject -> resubmit -> approve -> activate."""
    # 1. Create script
    create_resp = await client.post(
        "/scripts",
        headers=seeded["headers"],
        json={"name": "Lifecycle Test Script"},
    )
    script_id = create_resp.json()["data"]["id"]

    # 2. Submit version 1 for approval
    submit_resp = await client.post(
        f"/scripts/{script_id}/versions/1/submit", headers=seeded["headers"]
    )
    assert submit_resp.status_code == 200
    assert submit_resp.json()["data"]["status"] == "pending_approval"

    # 3. Verify it shows in approval queue (/scripts/approvals)
    appr_resp = await client.get("/scripts/approvals", headers=seeded["headers"])
    assert appr_resp.status_code == 200
    appr_items = appr_resp.json()["data"]
    assert any(item["scriptId"] == script_id for item in appr_items)

    # 4. Reject version with reason
    reject_resp = await client.post(
        f"/scripts/{script_id}/versions/1/reject",
        headers=seeded["headers"],
        json={"reason": "Please update TCPA disclaimer wording."},
    )
    assert reject_resp.status_code == 200
    rej_ver = reject_resp.json()["data"]
    assert rej_ver["status"] == "draft"
    assert rej_ver["rejectedReason"] == "Please update TCPA disclaimer wording."

    # 5. Edit draft version after rejection
    patch_resp = await client.patch(
        f"/scripts/{script_id}/versions/1",
        headers=seeded["headers"],
        json={"changeNote": "Updated TCPA wording per compliance review."},
    )
    assert patch_resp.status_code == 200

    # 6. Resubmit
    resubmit_resp = await client.post(
        f"/scripts/{script_id}/versions/1/submit", headers=seeded["headers"]
    )
    assert resubmit_resp.status_code == 200
    assert resubmit_resp.json()["data"]["status"] == "pending_approval"

    # 7. Approve version
    approve_resp = await client.post(
        f"/scripts/{script_id}/versions/1/approve", headers=seeded["headers"]
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["data"]["status"] == "approved"

    # 8. Activate version
    activate_resp = await client.post(
        f"/scripts/{script_id}/versions/1/activate",
        headers=seeded["headers"],
        json={},
    )
    assert activate_resp.status_code == 200
    act_ver = activate_resp.json()["data"]
    assert act_ver["status"] == "active"


async def test_duplicate_and_diff_script(client, seeded):
    # 1. Create base script
    create_resp = await client.post(
        "/scripts",
        headers=seeded["headers"],
        json={"name": "Original Script"},
    )
    script_id = create_resp.json()["data"]["id"]

    # 2. Duplicate script
    dup_resp = await client.post(
        f"/scripts/{script_id}/duplicate", headers=seeded["headers"]
    )
    assert dup_resp.status_code == 201
    dup_data = dup_resp.json()["data"]
    assert dup_data["name"] == "Original Script (Copy)"
    assert dup_data["id"] != script_id

    # 3. Create version 2 on original script
    v2_resp = await client.post(
        f"/scripts/{script_id}/versions",
        headers=seeded["headers"],
        json={"changeNote": "Version 2 addition"},
    )
    assert v2_resp.status_code == 201
    assert v2_resp.json()["data"]["version"] == 2

    # 4. Diff version 2 against version 1
    diff_resp = await client.get(
        f"/scripts/{script_id}/versions/2/diff?against=1",
        headers=seeded["headers"],
    )
    assert diff_resp.status_code == 200
    diff_data = diff_resp.json()["data"]
    assert diff_data["version"] == 2
    assert diff_data["againstVersion"] == 1
    assert "diffSummary" in diff_data


async def test_script_simulation_engine(client, seeded):
    # 1. Create script with standard node graph
    create_resp = await client.post(
        "/scripts",
        headers=seeded["headers"],
        json={
            "name": "Simulated Script",
            "greeting": "Welcome to Medicare Assistance.",
            "consent": "Do you consent to this call?",
            "qualificationQuestions": ["Are you 65 or older?"],
        },
    )
    script_id = create_resp.json()["data"]["id"]

    # 2. Run simulation with positive inputs
    sim_resp = await client.post(
        f"/scripts/{script_id}/simulate",
        headers=seeded["headers"],
        json={
            "inputs": [
                {"nodeId": "node-2", "userResponse": "yes"},
                {"nodeId": "node-q1", "userResponse": "yes"},
            ]
        },
    )
    assert sim_resp.status_code == 200
    sim_data = sim_resp.json()["data"]
    assert len(sim_data["steps"]) >= 2
    assert len(sim_data["spokenPrompts"]) >= 2
    assert sim_data["capturedFields"].get("tcpa_consent") == "yes"
    assert sim_data["finalDisposition"] == "qualified_transferred"


async def test_campaign_bind_and_start_guard(client, seeded):
    # 1. Create a campaign
    camp_resp = await client.post(
        "/campaigns",
        headers=seeded["headers"],
        json={"name": "Script Integration Campaign"},
    )
    camp_id = camp_resp.json()["data"]["id"]

    # 2. Create a script and approve it
    script_resp = await client.post(
        "/scripts", headers=seeded["headers"], json={"name": "Approved Campaign Script"}
    )
    script_id = script_resp.json()["data"]["id"]

    # Submit and approve version 1
    await client.post(
        f"/scripts/{script_id}/versions/1/submit", headers=seeded["headers"]
    )
    appr_resp = await client.post(
        f"/scripts/{script_id}/versions/1/approve", headers=seeded["headers"]
    )
    ver_id = appr_resp.json()["data"]["id"]

    # 3. Bind script to campaign
    bind_resp = await client.post(
        f"/campaigns/{camp_id}/script?script_id={script_id}&active_script_version_id={ver_id}",
        headers=seeded["headers"],
    )
    assert bind_resp.status_code == 200
    camp_updated = bind_resp.json()["data"]
    assert camp_updated["scriptId"] == script_id
    assert camp_updated["activeScriptVersionId"] == ver_id
