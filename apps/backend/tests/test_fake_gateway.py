"""STEP 16 - fake gateway simulator end-to-end tests.

Runs the simulator's scenario generator through a recording producer stub (the
CLI would emit onto live Kafka), feeds the captured ``talkflow.call.*.v1``
events into the STEP 15 ``CallIngestHandler`` against the suite Postgres engine
(reusing its no-broker harness), and then verifies the calls API reflects a
fully simulated call: CDR row, 8-turn transcript, latency performance and the
traversed script-path.
"""

from __future__ import annotations

import uuid

import pytest
from pytest_asyncio import fixture as async_fixture
from sqlalchemy import func, select

from app.core.redis import get_redis
from app.packages.contracts.enums import QualificationStatus
from app.packages.db.models import (
    Call,
    CallNodePath,
    CallPerformance,
    CallQualificationField,
    Campaign,
    TranscriptTurn,
)
from scripts.fake_gateway import (
    TOPIC_CLOSED,
    TOPIC_EVENT,
    TOPIC_FIELD,
    TOPIC_OPENED,
    TOPIC_TRANSCRIPT,
    Outcome,
    build_scenario,
    emit_calls,
)
from workers.call_ingest_worker import CallIngestHandler

_GREETING = "Hi, how are you doing today? This is Adriana."
_TRANSFER = "Now let me bring the senior on the line. Please stay on the line."
_QUALIFIED_NODES = [
    "n_greeting",
    "n_pitch",
    "n_part_ab",
    "n_part_ab",
    "n_age_range",
    "n_age_range",
    "n_confirm",
    "n_transfer",
]


class RecordingProducer:
    """Duck-typed stand-in for ``aiokafka.AIOKafkaProducer`` that records sends."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict, bytes | None]] = []

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def flush(self) -> None: ...

    async def send(
        self, topic: str, value: dict | None = None, key: bytes | None = None
    ) -> None:
        self.sent.append((topic, value or {}, key))


@async_fixture(autouse=True)
async def _flush_cp_keys():
    """Every fake-gateway test starts (and ends) with a clean cp:* namespace."""
    client = get_redis()
    async for key in client.scan_iter(match="cp:*"):
        await client.delete(key)
    yield
    async for key in get_redis().scan_iter(match="cp:*"):
        await get_redis().delete(key)


async def _ingest(factory, scenario) -> None:
    handler = CallIngestHandler()
    async with factory() as db:
        for topic, event in scenario.events:
            await handler.handle_topic(db, topic, event)
        await db.commit()


async def _campaign_id(factory) -> uuid.UUID:
    async with factory() as db:
        return (await db.execute(select(Campaign.id).limit(1))).scalar_one()


# ---------------------------------------------------------------------------
# Full pipeline: producer -> ingest handler -> calls API
# ---------------------------------------------------------------------------
async def test_fake_gateway_qualified_call_pipeline(client, seeded):
    campaign_id = await _campaign_id(seeded["factory"])
    scenario = build_scenario(
        Outcome.QUALIFIED,
        campaign_id=campaign_id,
        lead_id=seeded["lead_id"],
        seq=1,
    )

    producer = RecordingProducer()
    sent = await emit_calls(producer, [scenario], speed=0.0)

    assert sent == len(scenario.events) == 20
    assert [topic for topic, _, _ in producer.sent] == [
        topic for topic, _ in scenario.events
    ]
    call_key = str(scenario.call_id).encode("utf-8")
    assert all(key == call_key for _, _, key in producer.sent)

    await _ingest(seeded["factory"], scenario)

    # --- CDR: GET /calls surfaces the simulated call -------------------------
    resp = await client.get(
        "/calls", params={"search": "TF-SIM-0001"}, headers=seeded["headers"]
    )
    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert len(rows) == 1
    call = rows[0]
    assert call["id"] == str(scenario.call_id)
    assert call["reference"] == "TF-SIM-0001"
    assert call["status"] == "completed"
    assert call["disposition"] == "qualified_transferred"
    assert call["agentAliasUsed"] == "Adriana"
    assert call["campaignName"] == "Medicare Advantage 2026"
    assert call["leadId"] == str(seeded["lead_id"])
    assert call["qualification"]["status"] == QualificationStatus.QUALIFIED.value
    assert call["endedAt"] is not None

    # --- Transcript: all 8 turns of the qualified dialogue -------------------
    resp = await client.get(
        f"/calls/{scenario.call_id}/transcript", headers=seeded["headers"]
    )
    assert resp.status_code == 200
    turns = resp.json()["data"]
    assert len(turns) == 8
    assert turns[0]["text"] == _GREETING
    assert turns[0]["speaker"] == "bot"
    assert turns[-1]["text"] == _TRANSFER
    assert [turn["nodeId"] for turn in turns] == _QUALIFIED_NODES
    assert all(turn["isFinal"] is True for turn in turns)

    # --- Performance: captured latency metrics -------------------------------
    resp = await client.get(
        f"/calls/{scenario.call_id}/performance", headers=seeded["headers"]
    )
    assert resp.status_code == 200
    perf = resp.json()["data"]
    assert perf["vadMs"] == 18
    assert perf["sttMs"] == 240
    assert perf["decideMs"] == 9
    assert perf["ttsTtfaMs"] == 410
    assert perf["totalTurnMs"] == 690
    assert perf["turnCount"] == 8

    # --- Script path: node sequence the call traversed -----------------------
    resp = await client.get(
        f"/calls/{scenario.call_id}/script-path", headers=seeded["headers"]
    )
    assert resp.status_code == 200
    nodes = resp.json()["data"]
    assert len(nodes) == 8
    assert [node["nodeId"] for node in nodes] == _QUALIFIED_NODES
    assert [node["nodeName"] for node in nodes] == [
        "Greeting",
        "Pitch",
        "Part A & B",
        "Part A & B",
        "Age Range",
        "Age Range",
        "Confirm",
        "Transfer",
    ]
    assert nodes[0]["enteredAt"] is not None


# ---------------------------------------------------------------------------
# Outcome matrix: every scenario lands the expected rows + disposition
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("outcome", "turns", "fields", "disposition", "qual_status"),
    [
        (Outcome.QUALIFIED, 8, 2, "qualified_transferred", "qualified"),
        (
            Outcome.DISQUALIFIED_NO_PART_AB,
            5,
            1,
            "disqualified_no_part_ab",
            "disqualified",
        ),
        (Outcome.DISQUALIFIED_AGE, 6, 2, "disqualified_age_range", "disqualified"),
        (Outcome.OPTED_OUT, 4, 0, "opted_out", "pending"),
        (Outcome.SILENCE, 2, 0, "silence_no_response", "pending"),
    ],
)
async def test_fake_gateway_outcome_ingest_counts(
    seeded, outcome, turns, fields, disposition, qual_status
):
    campaign_id = await _campaign_id(seeded["factory"])
    scenario = build_scenario(
        outcome,
        campaign_id=campaign_id,
        lead_id=seeded["lead_id"],
        seq=1,
    )

    producer = RecordingProducer()
    await emit_calls(producer, [scenario], speed=0.0)
    assert len(producer.sent) == len(scenario.events)

    # Events are already in topic order; force them through the ingest worker.
    handler = CallIngestHandler()
    async with seeded["factory"]() as db:
        for topic, event in scenario.events:
            await handler.handle_topic(db, topic, event)
        await db.commit()

        call = (
            await db.execute(select(Call).where(Call.id == scenario.call_id))
        ).scalar_one()
        assert call.status == "completed"
        assert call.disposition == disposition
        assert call.qualification_status == qual_status
        assert (
            await db.execute(
                select(func.count())
                .select_from(TranscriptTurn)
                .where(TranscriptTurn.call_id == scenario.call_id)
            )
        ).scalar_one() == turns
        assert (
            await db.execute(
                select(func.count())
                .select_from(CallNodePath)
                .where(CallNodePath.call_id == scenario.call_id)
            )
        ).scalar_one() == turns
        assert (
            await db.execute(
                select(func.count())
                .select_from(CallQualificationField)
                .where(CallQualificationField.call_id == scenario.call_id)
            )
        ).scalar_one() == fields
        assert (
            await db.execute(
                select(func.count())
                .select_from(CallPerformance)
                .where(CallPerformance.call_id == scenario.call_id)
            )
        ).scalar_one() == 1


# ---------------------------------------------------------------------------
# Determinism / idempotency of the generated stream (replay-safe)
# ---------------------------------------------------------------------------
async def test_fake_gateway_scenario_replay_is_identical(seeded):
    from datetime import UTC, datetime

    campaign_id = await _campaign_id(seeded["factory"])
    kwargs = {
        "campaign_id": campaign_id,
        "lead_id": seeded["lead_id"],
        "seq": 7,
        "call_id": uuid.uuid4(),
        "now": datetime(2026, 9, 18, 12, 0, tzinfo=UTC),
    }
    first = build_scenario(Outcome.OPTED_OUT, **kwargs)
    second = build_scenario(Outcome.OPTED_OUT, **kwargs)

    assert first.call_id == second.call_id
    assert first.reference == "TF-SIM-0007"
    assert [ev for _, ev in first.events] == [ev for _, ev in second.events]
    # The opener event carries the soft module references the pipeline stores.
    opened = next(ev for topic, ev in first.events if topic == TOPIC_OPENED)
    assert opened.get("scriptVersionId")
    assert opened.get("ruleSetVersionId")
    assert opened["campaignId"] == str(campaign_id)
    assert opened["agentAlias"] == "Adriana"
    assert opened["direction"] == "outbound"


def test_fake_gateway_scenario_topics_are_the_ingest_topics():
    topics = {
        topic
        for topic, _ in build_scenario(
            Outcome.QUALIFIED,
            campaign_id=uuid.uuid4(),
            lead_id=uuid.uuid4(),
        ).events
    }
    assert topics == {
        TOPIC_OPENED,
        TOPIC_EVENT,
        TOPIC_TRANSCRIPT,
        TOPIC_FIELD,
        TOPIC_CLOSED,
    }
