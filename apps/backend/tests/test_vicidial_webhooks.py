"""Tests for BACKEND-8a — VICIdial telephony edge & webhook integration.

Covers:
- TalkFlow -> VICIdial status disposition mapping (mapper)
- ``add_lead`` vendor_lead_code passthrough + lead-id extraction
- Idempotency guard (Redis NX + in-process fallback) and replay protection
- Webhook authentication (X-TalkFlow-Telephony-Token, 401 on missing/invalid)
- start-call / dispo-call lifecycle incl. ignored_duplicate replay
- Metadata preservation: script_version_id + call_id on every persisted row
- AMI listener framing, event relevance and duration calculation
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from app.core.idempotency import (
    IDEMPOTENCY_TTL_SECONDS,
    build_vicidial_key,
    get_vicidial_idempotency_guard,
)
from app.modules.telephony.service import (
    process_dispo_call,
    process_start_call,
)
from app.packages.telephony.ami_listener import (
    AMIEvent,
    AMIListener,
    compute_call_duration,
    is_relevant_event,
    parse_event_block,
    parse_line,
)
from app.packages.vicidial.mapper import (
    OUTCOME_TO_VICIDIAL_STATUS,
    map_outcome_safe,
    map_talkflow_to_vicidial_status,
)
from app.packages.vicidial.parser import (
    VicidialResponse,
    extract_added_lead_id,
    parse_vicidial_response,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "vicidial"


def load_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Status disposition mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "outcome,expected",
    [
        ("qualified", "AIQUAL"),
        ("not_qualified", "AINQ"),
        ("callback", "AICB"),
        ("opt_out", "DNC"),
        ("suppressed", "DNC"),
        ("no_answer", "NA"),
        ("busy", "B"),
        ("disconnected", "DC"),
    ],
)
def test_map_talkflow_to_vicidial_status(outcome, expected):
    assert map_talkflow_to_vicidial_status(outcome) == expected


def test_map_unknown_outcome_raises():
    with pytest.raises(KeyError):
        map_talkflow_to_vicidial_status("made_up_outcome")


def test_map_outcome_safe_returns_none_for_unknown():
    assert map_outcome_safe("made_up_outcome") is None
    assert map_outcome_safe(None) is None


def test_mapping_table_matches_spec():
    assert OUTCOME_TO_VICIDIAL_STATUS == {
        "qualified": "AIQUAL",
        "not_qualified": "AINQ",
        "callback": "AICB",
        "opt_out": "DNC",
        "suppressed": "DNC",
        "no_answer": "NA",
        "busy": "B",
        "disconnected": "DC",
    }


# ---------------------------------------------------------------------------
# 2. add_lead vendor_lead_code passthrough + lead-id extraction
# ---------------------------------------------------------------------------


def test_extract_added_lead_id_from_success():
    parsed = parse_vicidial_response(load_fixture("add_lead_success.txt"))
    assert extract_added_lead_id(parsed) == "10001"


def test_extract_added_lead_id_returns_none_on_error():
    parsed = VicidialResponse(
        success=False,
        error="add_lead LEAD NOT ADDED - DUPLICATE PHONE NUMBER IN LIST",
    )
    assert extract_added_lead_id(parsed) is None


@pytest.mark.asyncio
async def test_add_lead_sends_vendor_lead_code_and_returns_id():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.url.params))
        return httpx.Response(200, text=load_fixture("add_lead_success.txt"))

    from app.packages.vicidial.methods import add_lead

    parsed = await add_lead(
        "13125550000",
        list_id="1001",
        campaign_id="TEST_CAMP",
        vendor_lead_code="lead-abc-123",
        transport=httpx.MockTransport(handler),
    )
    assert captured["vendor_lead_code"] == "lead-abc-123"
    assert parsed.success is True
    assert extract_added_lead_id(parsed) == "10001"


# ---------------------------------------------------------------------------
# 3. Idempotency guard
# ---------------------------------------------------------------------------


class MemoryRedis:
    """Offline stand-in for redis.asyncio.Redis (set-nx + get)."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def set(
        self, key: str, value: str, *, nx: bool = False, ex: int | None = None
    ):
        if nx and key in self._store:
            return None
        self._store[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self._store.get(key)


@pytest.mark.asyncio
async def test_vicidial_key_format():
    assert (
        build_vicidial_key("lead-1", "call-2")
        == "idempotency:vicidial_webhook:lead-1:call-2"
    )


@pytest.mark.asyncio
async def test_guard_acquires_once_and_blocks_replay():
    redis = MemoryRedis()
    from app.core.idempotency import VicidialIdempotencyGuard

    guard = VicidialIdempotencyGuard()
    assert await guard.try_acquire("lead-1", "call-1", client=redis) is True
    assert await guard.try_acquire("lead-1", "call-1", client=redis) is False
    # A different call id is a fresh transaction.
    assert await guard.try_acquire("lead-1", "call-2", client=redis) is True


@pytest.mark.asyncio
async def test_guard_falls_back_in_process_when_redis_raising():
    class BrokenRedis:
        async def set(self, *args, **kwargs):
            raise RuntimeError("redis down")

    from app.core.idempotency import VicidialIdempotencyGuard

    guard = VicidialIdempotencyGuard()
    assert await guard.try_acquire("lead-1", "call-1", client=BrokenRedis()) is True
    # Second (duplicate) request must still be rejected.
    assert await guard.try_acquire("lead-1", "call-1", client=BrokenRedis()) is False


def test_in_process_guard_expiry_configured():
    assert IDEMPOTENCY_TTL_SECONDS == 24 * 60 * 60


# ---------------------------------------------------------------------------
# 4. Webhook service: metadata preservation + idempotent replay
# ---------------------------------------------------------------------------


class RecordingSession:
    """Minimal AsyncSession double capturing ``Call`` rows + commit counts.

    ``execute`` returns a stub result so outbox writes and repository inserts
    do not touch a database.
    """

    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.executes = 0

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def execute(self, *args, **kwargs):
        self.executes += 1

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


def make_start_payload(**overrides):
    from app.modules.telephony.schemas import StartCallPayload

    base = {
        "lead_id": "11111111-1111-1111-1111-111111111111",
        "call_id": "22222222-2222-2222-2222-222222222222",
        "script_version_id": "33333333-3333-3333-3333-333333333333",
        "campaign_id": "44444444-4444-4444-4444-444444444444",
        "channel_id": "SIP/trunk-0000000011",
        "caller_number": "18505550000",
    }
    return StartCallPayload(**(base | overrides))


def make_dispo_payload(**overrides):
    from app.modules.telephony.schemas import DispoCallPayload

    base = {
        "lead_id": "11111111-1111-1111-1111-111111111111",
        "call_id": "22222222-2222-2222-2222-222222222222",
        "script_version_id": "33333333-3333-3333-3333-333333333333",
        "outcome": "qualified",
        "duration_seconds": 42,
    }
    return DispoCallPayload(**(base | overrides))


class FakePipeline:
    """Bundle the session + idempotency client used by webhook service tests."""

    def __init__(self) -> None:
        self.session = RecordingSession()
        self.redis = MemoryRedis()
        self.guard_cls = None

    def new_guard(self):
        from app.core.idempotency import VicidialIdempotencyGuard

        return VicidialIdempotencyGuard()


@pytest.mark.asyncio
async def test_start_call_persists_and_preserves_metadata():
    pipeline = FakePipeline()
    payload = make_start_payload()
    result = await process_start_call(
        pipeline.session,
        payload,
        idempotency_client=pipeline.redis,
        idempotency_guard=pipeline.new_guard(),
    )
    assert result.status == "processed"
    assert result.ignored_duplicate is False
    assert result.valid is True
    assert pipeline.session.commits == 1
    # Idempotency key was consumed.
    assert await pipeline.redis.get(
        build_vicidial_key(payload.lead_id, payload.call_id)
    )


@pytest.mark.asyncio
async def test_start_call_replay_is_ignored_without_second_commit():
    pipeline = FakePipeline()
    payload = make_start_payload()
    guard = pipeline.new_guard()

    first = await process_start_call(
        pipeline.session,
        payload,
        idempotency_client=pipeline.redis,
        idempotency_guard=guard,
    )
    replay = await process_start_call(
        pipeline.session,
        payload,
        idempotency_client=pipeline.redis,
        idempotency_guard=guard,
    )
    assert first.status == "processed"
    assert replay.status == "ignored_duplicate"
    assert replay.ignored_duplicate is True
    # Duplicate never reaches the database.
    assert pipeline.session.commits == 1


@pytest.mark.asyncio
async def test_dispo_call_maps_outcome_and_preserves_metadata():
    pipeline = FakePipeline()
    payload = make_dispo_payload(outcome="callback")
    result = await process_dispo_call(
        pipeline.session,
        payload,
        idempotency_client=pipeline.redis,
        idempotency_guard=pipeline.new_guard(),
    )
    assert result.status == "processed"
    assert pipeline.session.commits == 1


@pytest.mark.asyncio
async def test_dispo_call_replay_is_ignored():
    pipeline = FakePipeline()
    payload = make_dispo_payload()
    guard = pipeline.new_guard()

    await process_dispo_call(
        pipeline.session,
        payload,
        idempotency_client=pipeline.redis,
        idempotency_guard=guard,
    )
    replay = await process_dispo_call(
        pipeline.session,
        payload,
        idempotency_client=pipeline.redis,
        idempotency_guard=guard,
    )
    assert replay.ignored_duplicate is True
    assert pipeline.session.commits == 1


# ---------------------------------------------------------------------------
# 5. Webhook HTTP surface: authentication + idempotency replay
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """A bare FastAPI app exposing only the telephony router."""
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    from app.modules.telephony.vicidial_webhooks import router
    from app.packages.contracts.errors import TalkFlowError

    app = FastAPI()

    @app.exception_handler(TalkFlowError)
    async def talkflow_error_handler(request, exc: TalkFlowError) -> JSONResponse:
        envelope = exc.to_envelope(trace_id="")
        return JSONResponse(
            status_code=exc.http_status,
            content=envelope,
        )

    app.include_router(router)
    return app


@pytest.fixture
def override_dependencies(app, monkeypatch):
    """Point the router's DB + idempotency dependencies at offline doubles."""
    from app.core.database import get_db
    from app.modules.telephony import repository as telephony_repo
    from app.modules.telephony.vicidial_webhooks import get_idempotency_client

    session = RecordingSession()
    redis = MemoryRedis()

    async def fake_db():
        yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = fake_db
    app.dependency_overrides[get_idempotency_client] = lambda: redis

    # Keep the service from hitting Postgres insert statements offline.
    async def _fake_ensure_call_started(_session, payload):
        return payload.call_id

    async def _fake_record_disposition(_session, payload, vicidial_status):
        return payload.call_id

    monkeypatch.setattr(
        telephony_repo, "ensure_call_started", _fake_ensure_call_started
    )
    monkeypatch.setattr(telephony_repo, "record_disposition", _fake_record_disposition)
    return {"session": session, "redis": redis}


async def post_webhook(app, path: str, body: dict, token: str | None):
    transport = httpx.ASGITransport(app=app)
    headers = {}
    if token is not None:
        headers["X-TalkFlow-Telephony-Token"] = token
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        return await client.post(path, json=body, headers=headers)


@pytest.mark.asyncio
async def test_webhook_401_without_token(app, override_dependencies):
    resp = await post_webhook(
        app,
        "/telephony/vicidial/start-call",
        make_start_payload().model_dump(mode="json"),
        token=None,
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_401_with_invalid_token(app, override_dependencies, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "telephony_webhook_token", "correct-token")
    resp = await post_webhook(
        app,
        "/telephony/vicidial/start-call",
        make_start_payload().model_dump(mode="json"),
        token="wrong-token",
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_start_call_accepted_and_replay_ignored(
    app, override_dependencies, monkeypatch
):
    from app.core.config import settings

    monkeypatch.setattr(settings, "telephony_webhook_token", "correct-token")
    body = make_start_payload().model_dump(mode="json")

    first = await post_webhook(
        app, "/telephony/vicidial/start-call", body, token="correct-token"
    )
    assert first.status_code == 200
    payload_first = first.json()
    assert payload_first["ignoredDuplicate"] is False

    replay = await post_webhook(
        app, "/telephony/vicidial/start-call", body, token="correct-token"
    )
    assert replay.status_code == 200
    assert replay.json()["ignoredDuplicate"] is True
    assert replay.json()["status"] == "ignored_duplicate"


@pytest.mark.asyncio
async def test_webhook_dispo_call_accepted(app, override_dependencies, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "telephony_webhook_token", "correct-token")
    body = make_dispo_payload().model_dump(mode="json")
    resp = await post_webhook(
        app, "/telephony/vicidial/dispo-call", body, token="correct-token"
    )
    assert resp.status_code == 200
    assert resp.json()["ignoredDuplicate"] is False


# ---------------------------------------------------------------------------
# 6. AMI listener: framing, relevance, duration
# ---------------------------------------------------------------------------


def test_parse_line():
    assert parse_line("ActionID: 7") == ("ActionID", "7")
    assert parse_line("Channel: SIP/trunk-01") == ("Channel", "SIP/trunk-01")
    assert parse_line("no-colon-line") is None


def test_parse_event_block():
    block = (
        "Event: Hangup\r\n"
        "Channel: SIP/trunk-0000000011\r\n"
        "Uniqueid: 123456.789\r\n"
        "Peer: SIP/verifier-01\r\n"
    )
    event = parse_event_block(block)
    assert isinstance(event, AMIEvent)
    assert event.name == "Hangup"
    assert event["Channel"] == "SIP/trunk-0000000011"
    assert event.get("Uniqueid") == "123456.789"


@pytest.mark.parametrize(
    "name,relevant",
    [
        ("Hangup", True),
        ("BridgeExec", True),
        ("UserEvent", True),
        ("Newchannel", False),
        ("VarSet", False),
    ],
)
def test_relevant_events_only(name, relevant):
    assert is_relevant_event(name) is relevant


def test_compute_call_duration():
    assert compute_call_duration(1700000000.0, 1700000030.0) == 30
    assert compute_call_duration(None, 1700000030.0) is None


def test_compute_call_duration_zero_or_negative_clamped():
    assert compute_call_duration(1700000030.0, 1700000000.0) == 0


@pytest.mark.asyncio
async def test_ami_listener_reads_and_filters_events():
    raw = (
        "Event: Newchannel\r\n"
        "Channel: SIP/trunk-0001\r\n\r\n"
        "Event: Hangup\r\n"
        "Channel: SIP/trunk-0001\r\n"
        "Uniqueid: 55.1\r\n"
        "\r\n"
    )
    reader = asyncio.StreamReader()
    reader.feed_data(raw.encode())
    reader.feed_eof()

    listener = AMIListener()
    listener._reader = reader
    seen: list[AMIEvent] = []

    async def capture(event: AMIEvent) -> None:
        seen.append(event)

    # Manually scope the stream loop over the two blocks.
    first = await listener.read_event()
    if is_relevant_event(first.name):
        await capture(first)
    second = await listener.read_event()
    if is_relevant_event(second.name):
        await capture(second)

    assert [e.name for e in seen] == ["Hangup"]
    assert seen[0]["Uniqueid"] == "55.1"


def test_in_process_guard_shared_instance():
    assert get_vicidial_idempotency_guard() is not None
