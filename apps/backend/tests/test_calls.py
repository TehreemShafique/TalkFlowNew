"""Tests for the calls module.

Covers the frozen wire contract (camelCase envelope), the pure qualification /
disposition policies (ADR-03), citizen permission gating (Rule R4), scope
isolation (Rule R5), the disposition→qualification roll-up on the CDR, and
(STEP 18) full-text transcript search via the generated ``tsv`` column.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.modules.calls.policies import (
    can_update_disposition,
    evaluate_qualification,
    live_state,
    map_disposition_layer,
    to_vicidial_status,
)
from app.modules.calls.repository import search_transcripts
from app.packages.contracts.enums import (
    CallStatus,
    QualificationStatus,
)
from app.packages.db.models import (
    Call,
    CallEvent,
    CallNodePath,
    CallPerformance,
    TranscriptTurn,
)

# ---------------------------------------------------------------------------
# Pure policy (no DB / no HTTP)
# ---------------------------------------------------------------------------


def test_evaluate_qualification_qualified_when_all_evidence_yes():
    status, reason = evaluate_qualification(
        {"medicare_part_ab": "yes", "age_in_range": True}
    )
    assert status == QualificationStatus.QUALIFIED
    assert reason is None


def test_evaluate_qualification_disqualified_on_part_b_missing():
    status, reason = evaluate_qualification(
        {"medicare_part_ab": "no", "age_in_range": "yes"}
    )
    assert status == QualificationStatus.DISQUALIFIED
    assert reason == "disqualified_no_part_ab"


def test_evaluate_qualification_age_gate():
    status, reason = evaluate_qualification(
        {"medicare_part_ab": True, "age_in_range": "false"}
    )
    assert status == QualificationStatus.DISQUALIFIED
    assert reason == "disqualified_age_range"


def test_evaluate_qualification_incomplete_when_evidence_missing():
    status, reason = evaluate_qualification({"medicare_part_ab": True})
    assert status == QualificationStatus.INCOMPLETE
    assert reason is None


def test_evaluate_qualification_part_b_missing_wins_over_age_gap():
    # A stated Part A/B "no" disqualifies even though age was never captured.
    status, _ = evaluate_qualification({"medicare_part_ab": "no"})
    assert status == QualificationStatus.DISQUALIFIED


def test_can_update_disposition_only_while_in_dialer_loop():
    assert can_update_disposition(CallStatus.IN_PROGRESS.value) is True
    assert can_update_disposition(CallStatus.QUEUED.value) is True
    assert can_update_disposition(CallStatus.COMPLETED.value) is False
    assert can_update_disposition(CallStatus.FAILED.value) is False
    assert can_update_disposition(CallStatus.TRANSFERRED.value) is False


def test_map_disposition_layer():
    assert map_disposition_layer("no_answer") == "telephony"
    assert map_disposition_layer("opted_out") == "conversation"
    assert map_disposition_layer("disqualified_age") == "qualification"
    assert map_disposition_layer("verified_accepted") == "verifier"
    assert map_disposition_layer("IQA-8000-007") == "unknown"
    assert map_disposition_layer(None) == "unknown"


def test_to_vicidial_status_seeded_mapping():
    assert to_vicidial_status("disqualified_age") == "DNQ"
    assert to_vicidial_status("opted_out") == "DNC"
    assert to_vicidial_status("callback_requested") == "CLBK"
    assert to_vicidial_status("verified_accepted") == "SALE"
    assert to_vicidial_status("no_answer") == "NP"
    assert to_vicidial_status(None) is None
    assert to_vicidial_status("unknown_code") is None


def test_live_state_best_effort():
    assert live_state(CallStatus.IN_PROGRESS.value) == "listening"
    assert live_state(CallStatus.TRANSFERRING.value) == "transferring"
    assert live_state("bogus") == "connecting"


# ---------------------------------------------------------------------------
# HTTP contract
# ---------------------------------------------------------------------------


async def _insert_call(seeded, **overrides) -> uuid.UUID:
    """Insert one call row with sensible defaults (ORM so status is settable)."""
    async with seeded["factory"]() as db:
        call = Call(
            id=overrides.pop("id", uuid.uuid4()),
            reference=overrides.pop("reference", "TF-20981"),
            started_at=overrides.pop(
                "started_at", datetime.now(UTC) - timedelta(minutes=5)
            ),
            **overrides,
        )
        db.add(call)
        await db.commit()
        return call.id


async def test_requires_authentication(client):
    resp = await client.get("/calls")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth.not_authenticated"


async def test_list_calls_returns_camel_case_contract(client, seeded):
    resp = await client.get("/calls?page=1&pageSize=20", headers=seeded["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert "meta" in body and "data" in body
    assert body["meta"]["total"] >= 1
    call = body["data"][0]
    assert call["id"] == str(seeded["call_id"])
    assert call["reference"] == str(seeded["call_id"])
    assert call["status"] == "queued"
    assert "caller" in call and "masked" in call["caller"]
    assert call["qualification"]["status"] == "PASSED"
    assert call["direction"] == "outbound"
    assert "startedAt" in call and "createdAt" in call


async def test_get_call_detail(
    client,
    seeded,
):
    resp = await client.get(f"/calls/{seeded['call_id']}", headers=seeded["headers"])
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == str(seeded["call_id"])
    assert data["disposition"] == "IQA-8000-007"
    assert data["durationSeconds"] == 42


async def test_get_call_unknown_returns_404(client, seeded):
    resp = await client.get(
        "/calls/00000000-0000-0000-0000-00000000ffff", headers=seeded["headers"]
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "call.not_found"


async def test_viewer_can_list_but_not_dispose(client, seeded):
    list_resp = await client.get("/calls", headers=seeded["viewer_headers"])
    assert list_resp.status_code == 200

    dispose_resp = await client.patch(
        f"/calls/{seeded['call_id']}/disposition",
        headers=seeded["viewer_headers"],
        json={"disposition": "qualified_transferred"},
    )
    assert dispose_resp.status_code == 403
    assert dispose_resp.json()["error"]["code"] == "auth.permission_denied"


async def test_admin_disposition_updates_qualification_and_writes_audit(client, seeded):
    resp = await client.patch(
        f"/calls/{seeded['call_id']}/disposition",
        headers=seeded["headers"],
        json={"disposition": "disqualified_age", "reason": "Caller under 65"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["disposition"] == "disqualified_age"
    assert data["qualification"]["status"] == "disqualified"
    assert data["qualification"]["disqualificationReason"] == "disqualified_age_range"
    assert data["vicidialStatus"] == "DNQ"

    async with seeded["factory"]() as db:
        from sqlalchemy import func, select

        from app.packages.db.models import audit_log_table, outbox_table

        dispatched = await db.execute(
            select(func.count())
            .select_from(outbox_table)
            .where(outbox_table.c.event_type == "call.disposition_changed")
        )
        assert dispatched.scalar_one() == 1
        audited = await db.execute(
            select(func.count())
            .select_from(audit_log_table)
            .where(audit_log_table.c.action == "call.disposition")
        )
        assert audited.scalar_one() == 1


async def test_disposition_rejected_when_call_closed(client, seeded):
    call_id = await _insert_call(seeded, status=CallStatus.COMPLETED.value)
    resp = await client.patch(
        f"/calls/{call_id}/disposition",
        headers=seeded["headers"],
        json={"disposition": "verified_accepted"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "call.invalid_state"


async def test_live_calls_returns_only_active(client, seeded):
    live_id = await _insert_call(
        seeded, status=CallStatus.IN_PROGRESS.value, reference="TF-LIVE-1"
    )
    await _insert_call(seeded, status=CallStatus.COMPLETED.value, reference="TF-DONE-1")

    resp = await client.get("/calls/live", headers=seeded["headers"])
    assert resp.status_code == 200
    live = resp.json()["data"]
    refs = [c["reference"] for c in live]
    assert live_id in {uuid.UUID(c["id"]) for c in live}
    assert "TF-LIVE-1" in refs
    assert "TF-DONE-1" not in refs
    assert live[0]["liveState"] in {"listening", "transferring"}


async def test_live_includes_seeded_call_by_status(client, seeded):
    # Seeded call is queued -> not live.
    resp = await client.get("/calls/live", headers=seeded["headers"])
    ids = [c["id"] for c in resp.json()["data"]]
    assert str(seeded["call_id"]) not in ids


async def test_transcript_timeline_performance_script_path(client, seeded):
    call_id = seeded["call_id"]
    headers = seeded["headers"]

    transcript = await client.get(f"/calls/{call_id}/transcript", headers=headers)
    assert transcript.status_code == 200
    assert transcript.json()["data"] == []

    timeline = await client.get(f"/calls/{call_id}/timeline", headers=headers)
    assert timeline.status_code == 200
    assert timeline.json()["data"] == []

    perf = await client.get(f"/calls/{call_id}/performance", headers=headers)
    assert perf.status_code == 200
    assert perf.json()["data"]["vadMs"] is None

    path = await client.get(f"/calls/{call_id}/script-path", headers=headers)
    assert path.status_code == 200
    assert path.json()["data"] == []


async def test_transcript_and_timeline_return_rows(client, seeded):
    call_id = seeded["call_id"]
    await _insert_transcript(seeded, call_id)
    await _insert_timeline(seeded, call_id)
    await _insert_perf(seeded, call_id)
    await _insert_node_path(seeded, call_id)

    headers = seeded["headers"]
    transcript = await client.get(f"/calls/{call_id}/transcript", headers=headers)
    assert transcript.status_code == 200
    turns = transcript.json()["data"]
    assert len(turns) == 1
    assert turns[0]["speaker"] == "bot"
    assert turns[0]["text"] == "Hello, do we have your consent to record?"
    assert turns[0]["startMs"] == 1200

    timeline = await client.get(f"/calls/{call_id}/timeline", headers=headers)
    assert timeline.status_code == 200
    events = timeline.json()["data"]
    assert len(events) == 1
    assert events[0]["type"] == "call.state_changed"
    assert events[0]["category"] == "CALL"

    perf = await client.get(f"/calls/{call_id}/performance", headers=headers)
    assert perf.status_code == 200
    assert perf.json()["data"]["sttMs"] == 210

    path = await client.get(f"/calls/{call_id}/script-path", headers=headers)
    assert path.status_code == 200
    nodes = path.json()["data"]
    assert len(nodes) == 1
    assert nodes[0]["nodeId"] == "intro"
    assert nodes[0]["transitionTaken"] == "yes"


async def test_phone_masked_without_pii_permission(client, seeded):
    call_id = await _insert_call(
        seeded, caller_number="+18505554586", caller_state="FL"
    )
    admin = await client.get(f"/calls/{call_id}", headers=seeded["headers"])
    viewer = await client.get(f"/calls/{call_id}", headers=seeded["viewer_headers"])

    assert admin.json()["data"]["caller"]["number"] == "+18505554586"
    assert viewer.json()["data"]["caller"]["number"] is None
    assert viewer.json()["data"]["caller"]["masked"] == "(850) ***-4586"


async def test_transcript_search(seeded):
    """STEP 18 - full-text search matches only turns containing the query."""
    call_id = seeded["call_id"]
    async with seeded["factory"]() as db:
        db.add(
            TranscriptTurn(
                call_id=call_id,
                speaker="bot",
                seq=1,
                text="I have medicare part a and b",
                node_id="n_part_ab",
            )
        )
        db.add(
            TranscriptTurn(
                call_id=call_id,
                speaker="user",
                seq=2,
                text="no thanks",
                node_id="n_opt_out",
            )
        )
        await db.commit()

    async with seeded["factory"]() as db:
        matches = await search_transcripts(db, {}, "medicare")

    assert len(matches) == 1
    assert matches[0].text == "I have medicare part a and b"
    assert matches[0].call_id == call_id


async def test_search_matches_reference(client, seeded):
    call_id = await _insert_call(seeded, reference="TF-SEARCH-77")
    resp = await client.get("/calls?search=TF-SEARCH-77", headers=seeded["headers"])
    assert resp.status_code == 200
    assert resp.json()["meta"]["total"] >= 1
    assert str(call_id) in {c["id"] for c in resp.json()["data"]}


async def test_filter_by_status(client, seeded):
    await _insert_call(
        seeded, status=CallStatus.IN_PROGRESS.value, reference="TF-FILTER-1"
    )
    resp = await client.get("/calls?status=in_progress", headers=seeded["headers"])
    assert resp.status_code == 200
    refs = [c["reference"] for c in resp.json()["data"]]
    assert refs == ["TF-FILTER-1"]


# ---------------------------------------------------------------------------
# Helpers that insert the child tables through the ORM
# ---------------------------------------------------------------------------


async def _insert_transcript(seeded, call_id: uuid.UUID) -> None:
    async with seeded["factory"]() as db:
        db.add(
            TranscriptTurn(
                call_id=call_id,
                speaker="bot",
                seq=1,
                text="Hello, do we have your consent to record?",
                start_ts_ms=1200,
                end_ts_ms=2400,
                node_id="intro",
                confidence=0.98,
            )
        )
        await db.commit()


async def _insert_timeline(seeded, call_id: uuid.UUID) -> None:
    async with seeded["factory"]() as db:
        db.add(
            CallEvent(
                call_id=call_id,
                external_event_id="evt-1",
                type="call.state_changed",
                payload={"to": "in_progress"},
            )
        )
        await db.commit()


async def _insert_perf(seeded, call_id: uuid.UUID) -> None:
    async with seeded["factory"]() as db:
        db.add(
            CallPerformance(
                call_id=call_id,
                stt_ms=210,
                tts_total_ms=150,
                turn_count=4,
            )
        )
        await db.commit()


async def _insert_node_path(seeded, call_id: uuid.UUID) -> None:
    async with seeded["factory"]() as db:
        db.add(
            CallNodePath(
                call_id=call_id,
                seq=1,
                node_id="intro",
                node_type="greeting",
                node_name="Introduction",
                transition_taken="yes",
                meta={"consent": "granted"},
            )
        )
        await db.commit()
