"""STEP 15 - call ingest consumer worker tests.

Drives ``CallIngestHandler`` directly against the suite Postgres engine (no
live Kafka broker, matching the roadmap STEP 17 ``ingest.handle(...)`` sketch)
and covers the three non-negotiable ingest rules:

1. **Dedup / idempotent replay** - feeding the same event stream twice yields
   exactly one call, one turn per transcript, one raw event per external id.
2. **Out-of-order reconciliation** - a ``closed`` that beats the transcripts /
   node events never reopens the call, and a replayed ``closed`` with an
   *earlier* ``event_ts`` never rewinds ``ended_at``.
3. **Dedupe of ``(call_id, external_event_id)``** - a duplicate external id is
   swallowed (pre-check + the DB unique constraint catches races).

Plus the live Redis snapshot lifecycle (``cp:call:live:{call_id}`` /
``cp:calls:live:index``) and the wait-for-open contract on unknown calls.

**STEP 17** - the final three resilience tests run the ``call_qualified.json``
fixture (a complete 8-turn qualified call) end-to-end: a full replay creates
nothing new, wildly out-of-order delivery keeps ``completed`` / ``ended_at``
stable, and re-sending one ``(call_id, external_event_id)`` is swallowed
without an ``IntegrityError``.  **STEP 18** - a streaming partial transcript
(``isFinal: false``) is ignored as a turn but still audited as a raw event.
"""
from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pytest_asyncio import fixture as async_fixture
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.redis import get_redis
from app.packages.contracts.enums import CallStatus, QualificationStatus
from app.packages.db.models import (
    Call,
    CallEvent,
    CallNodePath,
    CallPerformance,
    CallQualificationField,
    Campaign,
    TranscriptTurn,
)
from workers.call_ingest_worker import (
    LIVE_INDEX_KEY,
    LIVE_SNAPSHOT_KEY,
    CallIngestHandler,
    WaitForOpenError,
)

N_TURNS = 8

# STEP 17 fixture: a full 8-turn qualified call (see fixtures/call_qualified.json).
FIXTURE_CALL_ID = uuid.UUID("8a1b2c3d-4e5f-4a6b-9c0d-1e2f3a4b5c6d")


@async_fixture(autouse=True)
async def _flush_cp_keys():
    """Every ingest test starts (and ends) with a clean cp:* namespace."""
    client = get_redis()
    async for key in client.scan_iter(match="cp:*"):
        await client.delete(key)
    yield
    async for key in get_redis().scan_iter(match="cp:*"):
        await get_redis().delete(key)


# ---------------------------------------------------------------------------
# Event builders (fake-gateway wire shape)
# ---------------------------------------------------------------------------
def _mk_events(lead_id: uuid.UUID, campaign_id: uuid.UUID, *, n_turns=N_TURNS):
    """A believable open -> (node+transcript)*n -> fields -> close stream.

    Returns ``(call_id, channel_id, [(topic, event), ...])`` with monotonically
    increasing ``eventTs`` starting now.
    """
    call_id = uuid.uuid4()
    channel_id = f"chn.{int(datetime.now(UTC).timestamp())}.{uuid.uuid4().hex[:8]}"
    script_version_id = uuid.uuid4()
    rule_set_version_id = uuid.uuid4()
    base = datetime.now(UTC)
    clock = 0.0

    def ev(**kw):
        nonlocal clock
        clock += 1.0
        return {
            "callId": str(call_id),
            "externalEventId": f"{call_id}-{int(clock)}",
            "eventTs": (base + timedelta(seconds=clock)).isoformat(),
            **kw,
        }

    events = [
        (
            "talkflow.call.opened.v1",
            ev(
                channelId=channel_id,
                campaignId=str(campaign_id),
                leadId=str(lead_id),
                direction="outbound",
                agentAlias="Adriana",
                scriptVersionId=str(script_version_id),
                ruleSetVersionId=str(rule_set_version_id),
                didUsed="855-555-4586",
                callerIdUsed="855-555-4586",
                callerNumber="202-555-0134",
                callerState="DC",
            ),
        )
    ]
    nodes = [("n_greeting", "Greeting"), ("n_qual_a", "Qualification Part A"), ("n_qual_b", "Qualification Part B")]
    for i in range(n_turns):
        node_id, node_name = nodes[i % len(nodes)]
        speaker = "bot" if i % 2 == 0 else "user"
        text = (
            f"Bot line {i}"
            if speaker == "bot"
            else f"Caller response number {i} about Medicare."
        )
        start_ms = i * 2500
        events.append(
            ("talkflow.call.event.v1", ev(type="node_entered", nodeId=node_id, nodeName=node_name))
        )
        events.append(
            (
                "talkflow.call.transcript.v1",
                ev(
                    speaker=speaker,
                    text=text,
                    startMs=start_ms,
                    endMs=start_ms + 2000,
                    nodeId=node_id,
                    confidence=0.93,
                    isFinal=True,
                ),
            )
        )
        if i == 3:
            events.append(
                (
                    "talkflow.call.field.v1",
                    ev(
                        field="medicare_part_ab",
                        label="Has Part A & B",
                        value=True,
                        valueType="boolean",
                        nodeId=node_id,
                        confidence=0.95,
                    ),
                )
            )
        if i == 5:
            events.append(
                (
                    "talkflow.call.field.v1",
                    ev(
                        field="age_in_range",
                        label="Age in range",
                        value=True,
                        valueType="boolean",
                        nodeId=node_id,
                        confidence=0.91,
                    ),
                )
            )
    events.append(
        (
            "talkflow.call.closed.v1",
            ev(
                status="completed",
                proposedDisposition="qualified_transferred",
                durationSeconds=n_turns * 3,
                talkTimeSeconds=n_turns * 2,
                performance={
                    "vadMs": 18,
                    "sttMs": 240,
                    "decideMs": 9,
                    "ttsTtfaMs": 410,
                    "totalTurnMs": 690,
                    "turnCount": n_turns,
                },
            ),
        )
    )
    return call_id, channel_id, events


async def _ingest(handler, factory, events, *, commit=True):
    async with factory() as db:
        for topic, event in events:
            await handler.handle_topic(db, topic, event)
        if commit:
            await db.commit()


async def _campaign_id(factory) -> uuid.UUID:
    async with factory() as db:
        return (await db.execute(select(Campaign.id).limit(1))).scalar_one()


def _load_fixture_events(lead_id: uuid.UUID, campaign_id: uuid.UUID):
    """Load ``call_qualified.json`` and repoint campaign/lead to seeded values."""
    path = Path(__file__).parent / "fixtures" / "call_qualified.json"
    payload = json.loads(path.read_text("utf-8"))
    events = [(entry["topic"], entry["event"]) for entry in payload["events"]]
    for topic, event in events:
        if topic == "talkflow.call.opened.v1":
            event["campaignId"] = str(campaign_id)
            event["leadId"] = str(lead_id)
    return events


# ---------------------------------------------------------------------------
# Rule 1 - idempotent replay
# ---------------------------------------------------------------------------
async def test_replayed_event_stream_is_idempotent(seeded):
    lead_id = seeded["lead_id"]
    campaign_id = await _campaign_id(seeded["factory"])
    call_id, channel_id, events = _mk_events(lead_id, campaign_id)
    handler = CallIngestHandler()

    await _ingest(handler, seeded["factory"], events)
    await _ingest(handler, seeded["factory"], events)  # replay

    async with seeded["factory"]() as db:
        assert (
            await db.execute(select(func.count()).select_from(Call).where(Call.id == call_id))
        ).scalar_one() == 1
        assert (
            await db.execute(
                select(func.count())
                .select_from(TranscriptTurn)
                .where(TranscriptTurn.call_id == call_id)
            )
        ).scalar_one() == N_TURNS
        assert (
            await db.execute(
                select(func.count())
                .select_from(CallNodePath)
                .where(CallNodePath.call_id == call_id)
            )
        ).scalar_one() == N_TURNS
        assert (
            await db.execute(
                select(func.count())
                .select_from(CallQualificationField)
                .where(CallQualificationField.call_id == call_id)
            )
        ).scalar_one() == 2
        assert (
            await db.execute(
                select(func.count()).select_from(CallEvent).where(CallEvent.call_id == call_id)
            )
        ).scalar_one() == len(events)

        call = (
            await db.execute(select(Call).where(Call.id == call_id))
        ).scalar_one()
        assert call.status == CallStatus.COMPLETED.value
        assert call.qualification_status == QualificationStatus.QUALIFIED.value
        assert call.vicidial_status == "RAXFER"
        assert call.agent_alias_used == "Adriana"
        assert call.rule_set_version_id is not None
        assert call.channel_id == channel_id

        performance = (
            await db.execute(select(CallPerformance).where(CallPerformance.call_id == call_id))
        ).scalar_one()
        assert performance.vad_ms == 18
        assert performance.total_turn_ms == 690
        assert performance.turn_count == N_TURNS

        turns = (
            await db.execute(
                select(TranscriptTurn).where(TranscriptTurn.call_id == call_id).order_by(TranscriptTurn.seq)
            )
        ).scalars().all()
        assert [t.seq for t in turns] == list(range(1, N_TURNS + 1))
        assert all(t.tsv is not None for t in turns)


# ---------------------------------------------------------------------------
# Rule 3 - out-of-order closed-vs-transcript reconciliation
# ---------------------------------------------------------------------------
async def test_closed_before_transcripts_never_reopens_or_rewinds(client, seeded):
    lead_id = seeded["lead_id"]
    campaign_id = await _campaign_id(seeded["factory"])
    call_id, _, events = _mk_events(lead_id, campaign_id)
    handler = CallIngestHandler()

    opened = next(ev for topic, ev in events if topic == "talkflow.call.opened.v1")
    transcript_events = [ev for topic, ev in events if topic == "talkflow.call.transcript.v1"]
    node_events = [ev for topic, ev in events if topic == "talkflow.call.event.v1"]
    field_events = [ev for topic, ev in events if topic == "talkflow.call.field.v1"]
    closed_event = next(ev for topic, ev in events if topic == "talkflow.call.closed.v1")
    closed_ts = datetime.fromisoformat(closed_event["eventTs"])

    # 1. opened, then closed immediately (before any transcript / node event).
    await _ingest(handler, seeded["factory"], [
        ("talkflow.call.opened.v1", opened),
        ("talkflow.call.closed.v1", closed_event),
    ])

    async with seeded["factory"]() as db:
        call = (await db.execute(select(Call).where(Call.id == call_id))).scalar_one()
        assert call.status == CallStatus.COMPLETED.value
        assert call.ended_at == closed_ts
        assert call.disposition == "qualified_transferred"
        assert call.vicidial_status == "RAXFER"

    # 2. Then the transcripts / node events / fields arrive late.
    late = (
        [("talkflow.call.event.v1", ev) for ev in node_events]
        + [("talkflow.call.transcript.v1", ev) for ev in transcript_events]
        + [("talkflow.call.field.v1", ev) for ev in field_events]
    )
    await _ingest(handler, seeded["factory"], late)

    # 3. A replayed closed with an EARLIER eventTs (rewind attempt).
    rewind = dict(closed_event, externalEventId=f"{call_id}-rewind", eventTs=(
        closed_ts - timedelta(seconds=30)
    ).isoformat())
    await _ingest(handler, seeded["factory"], [("talkflow.call.closed.v1", rewind)])

    async with seeded["factory"]() as db:
        call = (await db.execute(select(Call).where(Call.id == call_id))).scalar_one()
        # Closed stays closed; ended_at is the first close, never rewound.
        assert call.status == CallStatus.COMPLETED.value
        assert call.ended_at == closed_ts
        # The late turns were accepted (rule 3) without reopening the call.
        assert (
            await db.execute(
                select(func.count())
                .select_from(TranscriptTurn)
                .where(TranscriptTurn.call_id == call_id)
            )
        ).scalar_one() == N_TURNS
        assert (
            await db.execute(
                select(func.count())
                .select_from(CallNodePath)
                .where(CallNodePath.call_id == call_id)
            )
        ).scalar_one() == N_TURNS
        assert (
            await db.execute(
                select(func.count())
                .select_from(CallQualificationField)
                .where(CallQualificationField.call_id == call_id)
            )
        ).scalar_one() == 2

    # And the closed-before-anything call still serves its transcript via the API.
    resp = await client.get(f"/calls/{call_id}/transcript", headers=seeded["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == N_TURNS
    assert body["data"][0]["speaker"] in {"bot", "user"}


# ---------------------------------------------------------------------------
# Rule 1 - dedupe a duplicate (call_id, external_event_id)
# ---------------------------------------------------------------------------
async def test_duplicate_external_event_id_is_deduped(seeded):
    lead_id = seeded["lead_id"]
    campaign_id = await _campaign_id(seeded["factory"])
    call_id, _, events = _mk_events(lead_id, campaign_id)
    handler = CallIngestHandler()

    await _ingest(handler, seeded["factory"], [("talkflow.call.opened.v1", events[0][1])])

    # Two transcript messages sharing ONE external_event_id - the second must die.
    base = dict(events[2][1])  # a transcript event envelope
    first = dict(base, text="hello", externalEventId="dup-1")
    second = dict(base, text="world", externalEventId="dup-1")
    await _ingest(handler, seeded["factory"], [
        ("talkflow.call.transcript.v1", first),
        ("talkflow.call.transcript.v1", second),
    ])

    async with seeded["factory"]() as db:
        turns = (
            await db.execute(
                select(TranscriptTurn).where(TranscriptTurn.call_id == call_id)
            )
        ).scalars().all()
        assert len(turns) == 1
        assert turns[0].text == "hello"
        assert (
            await db.execute(
                select(func.count())
                .select_from(CallEvent)
                .where(
                    CallEvent.call_id == call_id,
                    CallEvent.external_event_id == "dup-1",
                )
            )
        ).scalar_one() == 1

        # The DB unique constraint still catches racing consumers: a direct
        # duplicate is an IntegrityError that the handler swallows via savepoint.
        with pytest.raises(IntegrityError):
            async with db.begin_nested():
                db.add(
                    CallEvent(
                        call_id=call_id,
                        external_event_id="dup-1",
                        type="call.transcript",
                        payload=None,
                        event_ts=datetime.now(UTC),
                    )
                )
                await db.flush()
        assert (
            await db.execute(
                select(func.count())
                .select_from(CallEvent)
                .where(
                    CallEvent.call_id == call_id,
                    CallEvent.external_event_id == "dup-1",
                )
            )
        ).scalar_one() == 1


# ---------------------------------------------------------------------------
# Wait-for-open: an event referencing a never-open call must not be committed
# ---------------------------------------------------------------------------
async def test_event_for_unknown_call_raises_wait_for_open(seeded):
    handler = CallIngestHandler()
    ghost_call = uuid.uuid4()
    event = {
        "callId": str(ghost_call),
        "externalEventId": "ghost-1",
        "eventTs": datetime.now(UTC).isoformat(),
        "type": "node_entered",
        "nodeId": "n_greeting",
    }
    async with seeded["factory"]() as db:
        with pytest.raises(WaitForOpenError):
            await handler.handle_topic(db, "talkflow.call.event.v1", event)
        # nothing persisted for a call that never opened
        assert (
            await db.execute(select(func.count()).select_from(Call).where(Call.id == ghost_call))
        ).scalar_one() == 0


# ---------------------------------------------------------------------------
# Redis live snapshot lifecycle
# ---------------------------------------------------------------------------
async def test_live_snapshot_redis_lifecycle(seeded):
    lead_id = seeded["lead_id"]
    campaign_id = await _campaign_id(seeded["factory"])
    call_id, _, events = _mk_events(lead_id, campaign_id)
    handler = CallIngestHandler()

    redis_client = get_redis()
    node_entered = next(ev for topic, ev in events if topic == "talkflow.call.event.v1")
    media_field = next(ev for topic, ev in events if topic == "talkflow.call.field.v1")
    closed_event = next(ev for topic, ev in events if topic == "talkflow.call.closed.v1")
    opened_event = next(ev for topic, ev in events if topic == "talkflow.call.opened.v1")

    # open -> snapshot + index
    await _ingest(handler, seeded["factory"], [("talkflow.call.opened.v1", opened_event)])
    assert await redis_client.exists(LIVE_SNAPSHOT_KEY.format(call_id)) == 1
    assert await redis_client.sismember(LIVE_INDEX_KEY, str(call_id)) == 1

    # node entered -> nodeName present in snapshot
    await _ingest(handler, seeded["factory"], [("talkflow.call.event.v1", node_entered)])
    snapshot = json.loads(await redis_client.get(LIVE_SNAPSHOT_KEY.format(call_id)))
    assert snapshot["nodeName"] == "Greeting"

    # field captures -> qualificationStatus visible in snapshot
    await _ingest(handler, seeded["factory"], [("talkflow.call.field.v1", media_field)])
    snapshot = json.loads(await redis_client.get(LIVE_SNAPSHOT_KEY.format(call_id)))
    assert snapshot["qualificationStatus"] == QualificationStatus.INCOMPLETE.value

    # closed -> removed from index and snapshot
    await _ingest(handler, seeded["factory"], [("talkflow.call.closed.v1", closed_event)])
    assert await redis_client.exists(LIVE_SNAPSHOT_KEY.format(call_id)) == 0
    assert await redis_client.sismember(LIVE_INDEX_KEY, str(call_id)) == 0


# ---------------------------------------------------------------------------
# STEP 17 - fixture-driven idempotency & resilience
# ---------------------------------------------------------------------------
async def test_replayed_events_create_nothing_new(seeded):
    """Replaying the whole fixture stream creates exactly one call, 8 turns."""
    lead_id = seeded["lead_id"]
    campaign_id = await _campaign_id(seeded["factory"])
    events = _load_fixture_events(lead_id, campaign_id)
    handler = CallIngestHandler()

    await _ingest(handler, seeded["factory"], events)
    await _ingest(handler, seeded["factory"], events)  # full replay

    async with seeded["factory"]() as db:
        assert (
            await db.execute(
                select(func.count()).select_from(Call).where(Call.id == FIXTURE_CALL_ID)
            )
        ).scalar_one() == 1
        assert (
            await db.execute(
                select(func.count())
                .select_from(TranscriptTurn)
                .where(TranscriptTurn.call_id == FIXTURE_CALL_ID)
            )
        ).scalar_one() == N_TURNS


async def test_out_of_order_events(seeded):
    """opened -> closed -> middle: the call stays completed, never reopened."""
    lead_id = seeded["lead_id"]
    campaign_id = await _campaign_id(seeded["factory"])
    events = _load_fixture_events(lead_id, campaign_id)
    handler = CallIngestHandler()

    opened, closed = events[0], events[-1]

    # 1. opened alone, then the closed arrives before everything in between.
    await _ingest(handler, seeded["factory"], [opened])
    await _ingest(handler, seeded["factory"], [closed])

    async with seeded["factory"]() as db:
        call = (await db.execute(select(Call).where(Call.id == FIXTURE_CALL_ID))).scalar_one()
        assert call.status == CallStatus.COMPLETED.value
        assert call.ended_at == datetime.fromisoformat(closed[1]["eventTs"])

    # 2. The middle events arrive late (nodes, transcripts, fields).
    await _ingest(handler, seeded["factory"], events[1:-1])

    async with seeded["factory"]() as db:
        call = (await db.execute(select(Call).where(Call.id == FIXTURE_CALL_ID))).scalar_one()
        # Terminal is terminal: nothing reopens it, ended_at is untouched.
        assert call.status == CallStatus.COMPLETED.value
        assert call.ended_at == datetime.fromisoformat(closed[1]["eventTs"])
        assert (
            await db.execute(
                select(func.count())
                .select_from(TranscriptTurn)
                .where(TranscriptTurn.call_id == FIXTURE_CALL_ID)
            )
        ).scalar_one() == N_TURNS


async def test_deduplication_on_external_event_id(seeded):
    """Re-sending one (call_id, external_event_id) is swallowed, no dup row."""
    lead_id = seeded["lead_id"]
    campaign_id = await _campaign_id(seeded["factory"])
    events = _load_fixture_events(lead_id, campaign_id)
    handler = CallIngestHandler()

    await _ingest(handler, seeded["factory"], events)

    # Re-send the SAME opened event (identical call_id + externalEventId) and
    # one transcript event: both must be swallowed, never surface as IntegrityError.
    opened = events[0][1]
    await _ingest(handler, seeded["factory"], [
        ("talkflow.call.opened.v1", dict(opened)),
        ("talkflow.call.transcript.v1", dict(events[2][1])),
    ])

    async with seeded["factory"]() as db:
        assert (
            await db.execute(
                select(func.count())
                .select_from(CallEvent)
                .where(CallEvent.call_id == FIXTURE_CALL_ID)
            )
        ).scalar_one() == len(events)
        assert (
            await db.execute(
                select(func.count())
                .select_from(TranscriptTurn)
                .where(TranscriptTurn.call_id == FIXTURE_CALL_ID)
            )
        ).scalar_one() == N_TURNS


# ---------------------------------------------------------------------------
# STEP 18 - the engine only persists finalized turns
# ---------------------------------------------------------------------------
async def test_streaming_partial_transcript_is_not_persisted(seeded):
    """A streaming (isFinal=False) transcript is skipped as a turn but audited."""
    lead_id = seeded["lead_id"]
    campaign_id = await _campaign_id(seeded["factory"])
    events = _load_fixture_events(lead_id, campaign_id)
    handler = CallIngestHandler()

    await _ingest(handler, seeded["factory"], [events[0]])  # opened only

    base = dict(events[2][1])  # the final bot greeting envelope
    partial = dict(
        base,
        externalEventId=f"partial-{uuid.uuid4()}",
        eventTs=(datetime.fromisoformat(base["eventTs"]) + timedelta(seconds=1)).isoformat(),
        isFinal=False,
    )
    await _ingest(handler, seeded["factory"], [("talkflow.call.transcript.v1", partial)])

    async with seeded["factory"]() as db:
        assert (
            await db.execute(
                select(func.count())
                .select_from(TranscriptTurn)
                .where(TranscriptTurn.call_id == FIXTURE_CALL_ID)
            )
        ).scalar_one() == 0
        # opened + the rejected streaming partial are both on the raw event log.
        assert (
            await db.execute(
                select(func.count())
                .select_from(CallEvent)
                .where(CallEvent.call_id == FIXTURE_CALL_ID)
            )
        ).scalar_one() == 2