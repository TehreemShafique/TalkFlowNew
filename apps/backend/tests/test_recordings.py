"""End-to-end tests for the recordings module (Task: recordings alignment).

Acceptance criteria covered here:

* list / detail return the camelCase envelope with ``transcript`` + float
  ``qaScore`` (frontend RecordingView contract),
* signed stream + single-use download grants actually serve the audio bytes,
* purge (ER) and the background retention purge flip READY -> PURGED,
* POST /recordings/{id}/qa-audit persists the scorecard and reflects it,
* permission gating is enforced (hide-on-404 for missing permissions).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.recordings import service
from app.packages.contracts.enums import RecordingStatus
from app.packages.db.models import CallRecording, calls_table

pytestmark = pytest.mark.asyncio


def _cid(suffix: int) -> uuid.UUID:
    return uuid.UUID(f"00000000-0000-0000-0000-{suffix:012d}")


async def test_list_recordings_returns_camel_case_contract(client, seeded):
    resp = await client.get("/recordings?page=1&pageSize=20", headers=seeded["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 1
    assert body["meta"]["total"] == 1

    rec = body["data"][0]
    assert rec["id"] == str(seeded["recording_id"])
    assert rec["leadName"] == "Jane Doe"
    assert rec["campaign"] == "Medicare Advantage 2026"
    assert rec["disposition"] == "IQA-8000-007"
    assert rec["durationSec"] == 42
    assert rec["consentCaptured"] is True
    assert rec["qualStatus"] == "PASSED"
    assert rec["status"] == "ready"
    assert isinstance(rec["qaScore"], (float, int, type(None)))
    assert isinstance(rec["transcript"], list)
    assert [t["speaker"] for t in rec["transcript"]] == ["Agent", "Bot"]
    assert rec["audioUrl"].startswith("http://testserver/api/v1/recordings/stream/")


async def test_list_phone_is_masked_without_pii_permission(client, seeded):
    resp = await client.get("/recordings", headers=seeded["viewer_headers"])
    assert resp.status_code == 200
    assert resp.json()["data"][0]["phone"] == "(850) ***-4586"


async def test_get_recording_details(client, seeded):
    resp = await client.get(
        f"/recordings/{seeded['recording_id']}", headers=seeded["headers"]
    )
    assert resp.status_code == 200
    rec = resp.json()["data"]
    assert rec["callId"] == str(seeded["call_id"])
    assert rec["transcript"][0]["text"] == "Hello, thank you for calling."
    assert rec["qaScore"] is None


async def test_stream_url_serves_audio(client, seeded):
    url_resp = await client.get(
        f"/recordings/{seeded['recording_id']}/stream", headers=seeded["headers"]
    )
    assert url_resp.status_code == 200
    stream_url = url_resp.json()
    assert stream_url.startswith("http://testserver/api/v1/recordings/stream/")

    audio_resp = await client.get(stream_url, headers=seeded["headers"])
    assert audio_resp.status_code == 200
    assert audio_resp.content == seeded["audio_bytes"]


async def test_download_url_is_single_use(client, seeded):
    url_resp = await client.get(
        f"/recordings/{seeded['recording_id']}/download", headers=seeded["headers"]
    )
    assert url_resp.status_code == 200
    download_url = url_resp.json()
    assert download_url.startswith("http://testserver/api/v1/recordings/download/")

    first = await client.get(download_url, headers=seeded["headers"])
    assert first.status_code == 200
    assert first.content == seeded["audio_bytes"]

    second = await client.get(download_url, headers=seeded["headers"])
    assert second.status_code == 403
    assert second.json()["error"]["code"] == "recording.download_unauthorized"


async def test_purge_marks_recording_purged_and_removes_audio(client, seeded):
    resp = await client.post(
        f"/recordings/{seeded['recording_id']}/purge",
        headers=seeded["headers"],
        json={"reason": "ER request #42"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "purged"
    assert data["audioUrl"] is None
    assert seeded["audio_path"].exists() is False

    detail = await client.get(
        f"/recordings/{seeded['recording_id']}", headers=seeded["headers"]
    )
    assert detail.json()["data"]["status"] == "purged"


async def test_qa_audit_persists_scorecard(client, seeded):
    payload = {
        "score": 4.85,
        "status": "Audited",
        "consentVerified": True,
        "qualVerified": True,
        "transferVerified": True,
        "notes": "Consent script read verbatim; transfer handled correctly.",
    }
    resp = await client.post(
        f"/recordings/{seeded['recording_id']}/qa-audit",
        headers=seeded["headers"],
        json=payload,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["qaScore"] == 4.85
    assert resp.json()["data"]["qaStatus"] == "Audited"

    detail = await client.get(
        f"/recordings/{seeded['recording_id']}", headers=seeded["headers"]
    )
    assert detail.json()["data"]["qaScore"] == 4.85
    assert detail.json()["data"]["qaStatus"] == "Audited"


async def test_qa_audit_requires_permission_hidden_as_404(client, seeded):
    resp = await client.post(
        f"/recordings/{seeded['recording_id']}/qa-audit",
        headers=seeded["viewer_headers"],
        json={"score": 4.0},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "recording.not_found"


async def test_purge_expired_recordings_background_job(seeded):
    now = datetime.now(UTC)
    async with seeded["factory"]() as db:
        expired_call = _cid(1)
        future_call = _cid(2)
        await db.execute(
            calls_table.insert().values(
                id=expired_call,
                tenant_id=None,
                started_at=now,
                duration_seconds=10,
                disposition="IQA-8000-007",
                qualification_status="PASSED",
                lead_id=seeded["lead_id"],
                campaign_id=None,
                verifier_id=None,
            )
        )
        await db.execute(
            calls_table.insert().values(
                id=future_call,
                tenant_id=None,
                started_at=now,
                duration_seconds=10,
                disposition="IQA-8000-007",
                qualification_status="PASSED",
                lead_id=seeded["lead_id"],
                campaign_id=None,
                verifier_id=None,
            )
        )
        expired = CallRecording(
            id=_cid(0x41),
            call_id=expired_call,
            status=RecordingStatus.READY.value,
            storage_provider="local",
            storage_key="rec/expired.wav",
            duration_seconds=10,
            expires_at=now - timedelta(hours=1),
        )
        future = CallRecording(
            id=_cid(0x42),
            call_id=future_call,
            status=RecordingStatus.READY.value,
            storage_provider="local",
            storage_key="rec/future.wav",
            duration_seconds=10,
            expires_at=now + timedelta(days=30),
        )
        db.add_all([expired, future])
        await db.commit()

        count = await service.purge_expired_recordings(db)
        assert count == 1

        from sqlalchemy import select

        await db.commit()
        expired_row = (
            await db.execute(
                select(CallRecording).where(CallRecording.id == expired.id)
            )
        ).scalar_one()
        future_row = (
            await db.execute(select(CallRecording).where(CallRecording.id == future.id))
        ).scalar_one()
        assert expired_row.status == RecordingStatus.PURGED.value
        assert expired_row.audio_purged_at is not None
        assert future_row.status == RecordingStatus.READY.value


async def test_requires_authentication(client):
    resp = await client.get("/recordings")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "auth.not_authenticated"


async def test_unknown_recording_returns_404(client, seeded):
    resp = await client.get(
        "/recordings/00000000-0000-0000-0000-00000000ffff",
        headers=seeded["headers"],
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "recording.not_found"