"""Tests for the campaigns module.

Covers the frozen wire contract (camelCase envelope), the all-at-once start
guard (ADR-03), lifecycle transitions, optimistic locking and permission gating.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.modules.campaigns.errors import (
    CAMPAIGN_NO_ACTIVE_SCRIPT,
    CAMPAIGN_NO_CALLER_IDS,
    CAMPAIGN_NO_COMPLIANCE_PROFILE,
    CAMPAIGN_NO_LIST_MAPPING,
    CAMPAIGN_NO_RULE_SET,
    CAMPAIGN_NO_VERIFIER_GROUP,
)
from app.modules.campaigns.policies import (
    CampaignSnapshot,
    can_start_campaign,
    can_stop,
)
from app.packages.contracts.enums import CampaignStatus
from app.packages.db.models import calls_table, campaigns_table


def _complete_payload(name: str = "Live Campaign") -> dict:
    return {
        "name": name,
        "activeScriptVersionId": str(uuid.uuid4()),
        "ruleSetVersionId": str(uuid.uuid4()),
        "complianceProfileId": str(uuid.uuid4()),
        "closerInGroup": "Licensed_QA_Pool",
        "vicidialCampaignId": "VICI_CAMP_01",
        "vicidialListIds": ["1001", "1002"],
    }


# ---------------------------------------------------------------------------
# Pure policy (no DB / no HTTP)
# ---------------------------------------------------------------------------


def test_can_start_campaign_bare_returns_all_five_problems():
    problems = can_start_campaign(CampaignSnapshot())
    assert len(problems) == 6
    assert set(problems) == {
        CAMPAIGN_NO_ACTIVE_SCRIPT,
        CAMPAIGN_NO_RULE_SET,
        CAMPAIGN_NO_COMPLIANCE_PROFILE,
        CAMPAIGN_NO_VERIFIER_GROUP,
        CAMPAIGN_NO_LIST_MAPPING,
        CAMPAIGN_NO_CALLER_IDS,
    }


def test_can_start_campaign_complete_returns_empty():
    snap = CampaignSnapshot(
        active_script_version_id=uuid.uuid4(),
        rule_set_version_id=uuid.uuid4(),
        compliance_profile_id=uuid.uuid4(),
        closer_in_group="Licensed_QA_Pool",
        vicidial_campaign_id="VICI_CAMP_01",
        vicidial_list_ids=("1001",),
        caller_ids=("18005550100",),
    )
    assert can_start_campaign(snap) == []


def test_can_stop_only_from_running_states():
    assert can_stop(CampaignStatus.ACTIVE.value) is True
    assert can_stop(CampaignStatus.PAUSED.value) is True
    assert can_stop(CampaignStatus.DRAFT.value) is False
    assert can_stop(CampaignStatus.STOPPED.value) is False
    assert can_stop(CampaignStatus.ARCHIVED.value) is False


# ---------------------------------------------------------------------------
# HTTP contract
# ---------------------------------------------------------------------------


async def test_requires_authentication(client):
    resp = await client.get("/campaigns")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth.not_authenticated"


async def test_create_and_list_campaign_camel_case(client, seeded):
    resp = await client.post(
        "/campaigns", headers=seeded["headers"], json={"name": "Test Campaign"}
    )
    assert resp.status_code == 201
    body = resp.json()["data"]
    assert body["name"] == "Test Campaign"
    assert body["status"] == "draft"
    assert body["version"] == 1
    assert body["vicidialListIds"] == []
    assert "createdAt" in body and "updatedAt" in body

    listing = await client.get(
        "/campaigns?page=1&pageSize=20", headers=seeded["headers"]
    )
    assert listing.status_code == 200
    body = listing.json()
    assert body["meta"]["total"] >= 2  # seeded + created
    names = [c["name"] for c in body["data"]]
    assert "Test Campaign" in names


async def test_start_reports_every_gap_at_once(client, seeded):
    created = await client.post(
        "/campaigns", headers=seeded["headers"], json={"name": "Bare Campaign"}
    )
    campaign_id = created.json()["data"]["id"]

    resp = await client.post(
        f"/campaigns/{campaign_id}/start", headers=seeded["headers"]
    )
    assert resp.status_code == 409
    error = resp.json()["error"]
    assert error["code"] == "campaign.start_failed"
    assert len(error["details"]["problems"]) == 6


async def test_start_then_pause_lifecycle(client, seeded):
    created = await client.post(
        "/campaigns", headers=seeded["headers"], json=_complete_payload()
    )
    campaign_id = created.json()["data"]["id"]

    started = await client.post(
        f"/campaigns/{campaign_id}/start", headers=seeded["headers"]
    )
    assert started.status_code == 200
    data = started.json()["data"]
    assert data["problems"] == []
    assert data["campaign"]["status"] == "active"
    assert sorted(data["campaign"]["vicidialListIds"]) == ["1001", "1002"]

    paused = await client.post(
        f"/campaigns/{campaign_id}/pause", headers=seeded["headers"]
    )
    assert paused.status_code == 200
    assert paused.json()["data"]["status"] == "paused"


async def test_pause_requires_active_state(client, seeded):
    created = await client.post(
        "/campaigns", headers=seeded["headers"], json=_complete_payload("Draft Only")
    )
    campaign_id = created.json()["data"]["id"]

    resp = await client.post(
        f"/campaigns/{campaign_id}/pause", headers=seeded["headers"]
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "campaign.invalid_state"


async def test_start_requires_campaign_start_permission(client, seeded):
    created = await client.post(
        "/campaigns", headers=seeded["headers"], json=_complete_payload("Perm Test")
    )
    campaign_id = created.json()["data"]["id"]

    resp = await client.post(
        f"/campaigns/{campaign_id}/start", headers=seeded["viewer_headers"]
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "auth.permission_denied"


async def test_update_rejects_version_conflict_and_direct_activation(client, seeded):
    created = await client.post(
        "/campaigns", headers=seeded["headers"], json={"name": "Concurrency"}
    )
    campaign_id = created.json()["data"]["id"]

    stale = await client.put(
        f"/campaigns/{campaign_id}",
        headers=seeded["headers"],
        json={"name": "Renamed", "version": 99},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "campaign.version_conflict"

    activate = await client.put(
        f"/campaigns/{campaign_id}",
        headers=seeded["headers"],
        json={"status": "active"},
    )
    assert activate.status_code == 409
    assert activate.json()["error"]["code"] == "campaign.invalid_state"


async def test_unknown_campaign_returns_404(client, seeded):
    resp = await client.get(
        "/campaigns/00000000-0000-0000-0000-00000000ffff",
        headers=seeded["headers"],
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "campaign.not_found"


# ---------------------------------------------------------------------------
# Lifecycle - stop
# ---------------------------------------------------------------------------


def _call_row(
    campaign_id: uuid.UUID,
    *,
    started_at: datetime,
    duration_seconds: int | None,
    qualification_status: str | None,
    disposition: str | None,
) -> dict:
    return {
        "id": uuid.uuid4(),
        "started_at": started_at,
        "duration_seconds": duration_seconds,
        "qualification_status": qualification_status,
        "disposition": disposition,
        "campaign_id": campaign_id,
    }


async def _insert_calls(seeded, rows: list[dict]) -> None:
    async with seeded["factory"]() as db:
        await db.execute(calls_table.insert().values(rows))
        await db.commit()


async def test_start_pause_stop_lifecycle(client, seeded):
    created = await client.post(
        "/campaigns", headers=seeded["headers"], json=_complete_payload("Stop Me")
    )
    campaign_id = created.json()["data"]["id"]

    await client.post(f"/campaigns/{campaign_id}/start", headers=seeded["headers"])
    paused = await client.post(
        f"/campaigns/{campaign_id}/pause", headers=seeded["headers"]
    )
    assert paused.json()["data"]["status"] == "paused"

    stopped = await client.post(
        f"/campaigns/{campaign_id}/stop", headers=seeded["headers"]
    )
    assert stopped.status_code == 200
    assert stopped.json()["data"]["status"] == "stopped"

    again = await client.post(
        f"/campaigns/{campaign_id}/stop", headers=seeded["headers"]
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "campaign.invalid_state"


async def test_stop_active_campaign_directly(client, seeded):
    created = await client.post(
        "/campaigns",
        headers=seeded["headers"],
        json=_complete_payload("Active To Stop"),
    )
    campaign_id = created.json()["data"]["id"]

    await client.post(f"/campaigns/{campaign_id}/start", headers=seeded["headers"])
    stopped = await client.post(
        f"/campaigns/{campaign_id}/stop", headers=seeded["headers"]
    )
    assert stopped.status_code == 200
    assert stopped.json()["data"]["status"] == "stopped"


async def test_stop_draft_is_rejected(client, seeded):
    created = await client.post(
        "/campaigns", headers=seeded["headers"], json={"name": "Draft Stop"}
    )
    campaign_id = created.json()["data"]["id"]

    resp = await client.post(
        f"/campaigns/{campaign_id}/stop", headers=seeded["headers"]
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "campaign.invalid_state"


async def test_stop_requires_campaign_start_permission(client, seeded):
    created = await client.post(
        "/campaigns",
        headers=seeded["headers"],
        json=_complete_payload("Stop Perm"),
    )
    campaign_id = created.json()["data"]["id"]
    await client.post(f"/campaigns/{campaign_id}/start", headers=seeded["headers"])

    resp = await client.post(
        f"/campaigns/{campaign_id}/stop", headers=seeded["viewer_headers"]
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "auth.permission_denied"


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


async def test_stats_counts_today_only_for_this_campaign(client, seeded):
    created = await client.post(
        "/campaigns",
        headers=seeded["headers"],
        json=_complete_payload("Stats Campaign"),
    )
    campaign_id = uuid.UUID(created.json()["data"]["id"])
    other_id = uuid.uuid4()
    now = datetime.now(UTC)
    yesterday = now - timedelta(days=1)

    # The new FK on calls.campaign_id requires the "other" campaign to exist.
    async with seeded["factory"]() as db:
        await db.execute(
            campaigns_table.insert().values(id=other_id, name="Other Campaign")
        )
        await db.commit()

    await _insert_calls(
        seeded,
        [
            _call_row(
                campaign_id,
                started_at=now,
                duration_seconds=30,
                qualification_status="qualified",
                disposition="qualified_transferred",
            ),
            _call_row(
                campaign_id,
                started_at=now,
                duration_seconds=12,
                qualification_status="disqualified",
                disposition="caller_hung_up_early",
            ),
            _call_row(
                campaign_id,
                started_at=now,
                duration_seconds=0,
                qualification_status=None,
                disposition="no_answer",
            ),
            _call_row(
                campaign_id,
                started_at=now,
                duration_seconds=5,
                qualification_status="PASSED",
                disposition="verified_accepted",
            ),
            # Excluded: started yesterday.
            _call_row(
                campaign_id,
                started_at=yesterday,
                duration_seconds=30,
                qualification_status="qualified",
                disposition="qualified_transferred",
            ),
            # Excluded: belongs to another campaign.
            _call_row(
                other_id,
                started_at=now,
                duration_seconds=30,
                qualification_status="qualified",
                disposition="qualified_transferred",
            ),
        ],
    )

    resp = await client.get(
        f"/campaigns/{campaign_id}/stats", headers=seeded["headers"]
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["callsToday"] == 4
    assert data["contactRate"] == 0.75
    assert data["qualificationRate"] == 0.5
    assert data["transferRate"] == 0.5


async def test_stats_without_calls_is_zero(client, seeded):
    created = await client.post(
        "/campaigns", headers=seeded["headers"], json={"name": "Empty Stats"}
    )
    campaign_id = created.json()["data"]["id"]

    resp = await client.get(
        f"/campaigns/{campaign_id}/stats", headers=seeded["headers"]
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == {
        "callsToday": 0,
        "contactRate": 0.0,
        "qualificationRate": 0.0,
        "transferRate": 0.0,
    }


async def test_stats_unknown_campaign_returns_404(client, seeded):
    resp = await client.get(
        "/campaigns/00000000-0000-0000-0000-00000000ffff/stats",
        headers=seeded["headers"],
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "campaign.not_found"
