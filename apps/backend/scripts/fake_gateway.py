"""STEP 16 - fake gateway simulator (``apps/backend/scripts``).

Stems the AI Voice Bot's wire contract without Asterisk / the AI-Gateway: it
generates believable call executions and publishes them onto the five
``talkflow.call.*.v1`` Kafka topics that the STEP 15 ingest consumer worker
consumes, so the whole control-plane pipeline (Postgres + Redis + calls API)
can be exercised end to end.

Run::

    python -m scripts.fake_gateway --outcome qualified --count 10
    python -m scripts.fake_gateway --outcome opted_out --speed 0

The module is split into three pieces so the test suite can drive the same code
paths without a live broker:

- ``build_scenario``  - pure event generation for one call (a ``CallScenario``).
- ``emit_calls``      - send built scenarios through any ``AIOKafkaProducer``-
                       compatible transport (real producer in the CLI, a
                       recording stub in the tests; ``--speed`` paces the sends).
- ``main``            - the CLI: resolves campaign / lead ids, builds ``count``
                       calls and emits them to Kafka.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import aiokafka
from sqlalchemy import select

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logging import configure_logging, get_logger
from app.packages.contracts.enums import CampaignStatus
from app.packages.db.models import Campaign
from workers.call_ingest_worker import (
    TOPIC_CLOSED,
    TOPIC_EVENT,
    TOPIC_FIELD,
    TOPIC_OPENED,
    TOPIC_TRANSCRIPT,
)

log = get_logger("scripts.fake_gateway")


# One conversational beat: the bot (or caller) says a line on a script node,
# and optionally captures a qualification field from that exchange.
@dataclass(frozen=True)
class Beat:
    node_id: str
    node_name: str
    speaker: str
    text: str
    field: tuple[str, str, bool] | None = None  # (field, label, captured value)


_GREETING = "Hi, how are you doing today? This is Adriana."
_PITCH = (
    "I'm calling because your health and groceries benefit have not been "
    "claimed yet, and they're about to close out."
)
_PART_AB = "So do you currently have Medicare Part A and B?"
_AGE_RANGE = "And are you between the age of 60 to 87?"


class Outcome(StrEnum):
    """The five simulator run scenarios (CLI ``--outcome`` choices)."""

    QUALIFIED = "qualified"
    DISQUALIFIED_NO_PART_AB = "disqualified_no_part_ab"
    DISQUALIFIED_AGE = "disqualified_age"
    OPTED_OUT = "opted_out"
    SILENCE = "silence"


_SCENARIOS: dict[Outcome, list[Beat]] = {
    Outcome.QUALIFIED: [
        Beat("n_greeting", "Greeting", "bot", _GREETING),
        Beat("n_pitch", "Pitch", "bot", _PITCH),
        Beat("n_part_ab", "Part A & B", "bot", _PART_AB),
        Beat(
            "n_part_ab",
            "Part A & B",
            "user",
            "yes I do",
            ("medicare_part_ab", "Has Part A & B", True),
        ),
        Beat("n_age_range", "Age Range", "bot", _AGE_RANGE),
        Beat(
            "n_age_range",
            "Age Range",
            "user",
            "yeah I'm 71",
            ("age_in_range", "Age in range", True),
        ),
        Beat("n_confirm", "Confirm", "bot", "Alright, great."),
        Beat(
            "n_transfer",
            "Transfer",
            "bot",
            "Now let me bring the senior on the line. Please stay on the line.",
        ),
    ],
    Outcome.DISQUALIFIED_NO_PART_AB: [
        Beat("n_greeting", "Greeting", "bot", _GREETING),
        Beat("n_pitch", "Pitch", "bot", _PITCH),
        Beat("n_part_ab", "Part A & B", "bot", _PART_AB),
        Beat(
            "n_part_ab",
            "Part A & B",
            "user",
            "No I only have Part A",
            ("medicare_part_ab", "Has Part A & B", False),
        ),
        Beat(
            "n_dq",
            "Disqualify",
            "bot",
            "I understand \u2014 thank you for your time. Have a good day.",
        ),
    ],
    Outcome.DISQUALIFIED_AGE: [
        Beat("n_greeting", "Greeting", "bot", _GREETING),
        Beat("n_pitch", "Pitch", "bot", _PITCH),
        Beat("n_part_ab", "Part A & B", "bot", _PART_AB),
        Beat(
            "n_part_ab",
            "Part A & B",
            "user",
            "yes I do",
            ("medicare_part_ab", "Has Part A & B", True),
        ),
        Beat("n_age_range", "Age Range", "bot", _AGE_RANGE),
        Beat(
            "n_age_range",
            "Age Range",
            "user",
            "No I'm 55",
            ("age_in_range", "Age in range", False),
        ),
    ],
    Outcome.OPTED_OUT: [
        Beat("n_greeting", "Greeting", "bot", _GREETING),
        Beat("n_pitch", "Pitch", "bot", _PITCH),
        Beat("n_pitch", "Pitch", "user", "Take me off your list!"),
        Beat(
            "n_opt_out",
            "Opt Out",
            "bot",
            "I understand. I'll remove you from our list. Have a good day.",
        ),
    ],
    Outcome.SILENCE: [
        Beat("n_greeting", "Greeting", "bot", _GREETING),
        Beat("n_pitch", "Pitch", "bot", _PITCH),
    ],
}

_CLOSURES: dict[Outcome, dict[str, Any]] = {
    Outcome.QUALIFIED: {
        "proposedDisposition": "qualified_transferred",
        "durationSeconds": 24,
        "talkTimeSeconds": 16,
    },
    Outcome.DISQUALIFIED_NO_PART_AB: {
        "proposedDisposition": "disqualified_no_part_ab",
        "durationSeconds": 16,
        "talkTimeSeconds": 11,
    },
    Outcome.DISQUALIFIED_AGE: {
        "proposedDisposition": "disqualified_age_range",
        "durationSeconds": 18,
        "talkTimeSeconds": 13,
    },
    Outcome.OPTED_OUT: {
        "proposedDisposition": "opted_out",
        "durationSeconds": 13,
        "talkTimeSeconds": 8,
    },
    Outcome.SILENCE: {
        "proposedDisposition": "silence_no_response",
        "durationSeconds": 12,
        "talkTimeSeconds": 5,
    },
}

_PERFORMANCE: dict[str, Any] = {
    "vadMs": 18,
    "sttMs": 240,
    "decideMs": 9,
    "ttsTtfaMs": 410,
    "totalTurnMs": 690,
}


@dataclass
class CallScenario:
    """One simulated call: identity + its ordered ``(topic, event)`` stream."""

    call_id: uuid.UUID
    channel_id: str
    reference: str
    outcome: str
    events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)


def build_scenario(
    outcome: str | Outcome,
    *,
    campaign_id: uuid.UUID,
    lead_id: uuid.UUID,
    seq: int = 1,
    call_id: uuid.UUID | None = None,
    script_version_id: uuid.UUID | None = None,
    rule_set_version_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> CallScenario:
    """Generate the full event stream for one call of the given ``outcome``.

    The body of each event matches the gateway's camelCase wire shape consumed
    by ``workers.call_ingest_worker.CallIngestHandler``.  ``event_ts`` and
    ``external_event_id`` are derived only from the stable inputs, so replaying
    the same scenario is idempotent for the ingest worker (rule 1).
    """
    outcome = Outcome(outcome)
    now = now or datetime.now(UTC)
    call_id = call_id or uuid.uuid4()
    reference = f"TF-SIM-{seq:04d}"
    # Channel / script / rule-set ids are derived from the stable inputs so a
    # rebuilt stream for the same call is byte-identical (idempotent replay for
    # the ingest worker).  These are placeholder module references until the
    # ``scripts`` / ``rule_sets`` modules land (see ``apps/backend/remain.md``).
    channel_id = f"{int(now.timestamp())}.{call_id.hex[:6]}"
    script_version_id = script_version_id or uuid.uuid5(
        uuid.NAMESPACE_URL, f"talkflow/script-version/{call_id}"
    )
    rule_set_version_id = rule_set_version_id or uuid.uuid5(
        uuid.NAMESPACE_URL, f"talkflow/rule-set-version/{call_id}"
    )
    beats = _SCENARIOS[outcome]
    clock = 0.0

    def ev(**kw: Any) -> dict[str, Any]:
        nonlocal clock
        clock += 1.0
        return {
            "callId": str(call_id),
            "externalEventId": f"{call_id}-{int(clock):03d}",
            "eventTs": (now + timedelta(seconds=clock)).isoformat(),
            **kw,
        }

    events: list[tuple[str, dict[str, Any]]] = [
        (
            TOPIC_OPENED,
            ev(
                reference=reference,
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
                attemptNumber=1,
            ),
        )
    ]

    for index, beat in enumerate(beats):
        start_ms = index * 2500
        events.append(
            (
                TOPIC_EVENT,
                ev(type="node_entered", nodeId=beat.node_id, nodeName=beat.node_name),
            )
        )
        events.append(
            (
                TOPIC_TRANSCRIPT,
                ev(
                    speaker=beat.speaker,
                    text=beat.text,
                    startMs=start_ms,
                    endMs=start_ms + 2000,
                    nodeId=beat.node_id,
                    nodeName=beat.node_name,
                    confidence=0.95,
                    isFinal=True,
                ),
            )
        )
        if beat.field is not None:
            field_name, label, value = beat.field
            events.append(
                (
                    TOPIC_FIELD,
                    ev(
                        field=field_name,
                        label=label,
                        value=value,
                        valueType="boolean",
                        nodeId=beat.node_id,
                        confidence=0.95,
                    ),
                )
            )

    closure = _CLOSURES[outcome]
    events.append(
        (
            TOPIC_CLOSED,
            ev(
                status="completed",
                proposedDisposition=closure["proposedDisposition"],
                durationSeconds=closure["durationSeconds"],
                talkTimeSeconds=closure["talkTimeSeconds"],
                performance={**_PERFORMANCE, "turnCount": len(beats)},
            ),
        )
    )

    return CallScenario(
        call_id=call_id,
        channel_id=channel_id,
        reference=reference,
        outcome=outcome.value,
        events=events,
    )


async def emit_calls(
    producer: Any,
    scenarios: list[CallScenario],
    *,
    speed: float = 1.0,
) -> int:
    """Publish every scenario's events via ``producer``; return message count.

    ``producer`` needs ``start`` / ``stop`` / ``flush`` and a coroutine
    ``send(topic, value=None, key=None)`` (duck-typed - the CLI passes a real
    ``aiokafka.AIOKafkaProducer``, tests pass a recording stub).  ``speed`` is
    a wall-clock multiplier over the simulated ~2.5s-per-beat real pace
    (``0.0`` means "emit immediately").
    """
    per_message_pace = 2.5
    delay = per_message_pace / speed if speed and speed > 0 else 0.0
    sent = 0
    for scenario in scenarios:
        key = str(scenario.call_id).encode("utf-8")
        for topic, event in scenario.events:
            await producer.send(topic, value=event, key=key)
            sent += 1
            if delay:
                await asyncio.sleep(delay)
    await producer.flush()
    return sent


def _build_producer(bootstrap_servers: str) -> aiokafka.AIOKafkaProducer:
    return aiokafka.AIOKafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
    )


async def _active_campaign_id() -> uuid.UUID | None:
    async with async_session_factory() as db:
        value = (
            await db.execute(
                select(Campaign.id)
                .where(Campaign.status == CampaignStatus.ACTIVE.value)
                .limit(1)
            )
        ).scalar_one_or_none()
        return value


async def _run(args: argparse.Namespace, bootstrap_servers: str) -> int:
    if args.campaign_id:
        campaign_id = uuid.UUID(args.campaign_id)
    else:
        campaign_id = await _active_campaign_id()
        if campaign_id is None:
            log.error(
                "fake_gateway: no active campaign found - pass --campaign-id",
            )
            return 2
    lead_id = uuid.UUID(args.lead_id) if args.lead_id else uuid.uuid4()

    producer = _build_producer(bootstrap_servers)
    await producer.start()
    try:
        scenarios = [
            build_scenario(
                args.outcome,
                campaign_id=campaign_id,
                lead_id=lead_id,
                seq=index + 1,
            )
            for index in range(args.count)
        ]
        total = await emit_calls(producer, scenarios, speed=args.speed)
    finally:
        await producer.stop()

    for scenario in scenarios:
        log.info(
            "fake_gateway: call emitted",
            reference=scenario.reference,
            call_id=str(scenario.call_id),
            channel_id=scenario.channel_id,
            outcome=scenario.outcome,
            messages=len(scenario.events),
        )
    log.info(
        "fake_gateway: batch complete",
        count=len(scenarios),
        messages=total,
        outcome=args.outcome,
        bootstrap=bootstrap_servers,
    )
    return 0


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(
        description=__doc__.split("---")[0].strip(),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--campaign-id",
        default=None,
        help="Campaign UUID to place calls against (default: first ACTIVE campaign).",
    )
    parser.add_argument(
        "--lead-id",
        default=None,
        help="Lead UUID the calls belong to (default: generate one).",
    )
    parser.add_argument(
        "--outcome",
        choices=[outcome.value for outcome in Outcome],
        default=Outcome.QUALIFIED.value,
        help="Scenario to simulate.",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Wall-clock multiplier over the ~2.5s-per-beat pace (0.0 = emit all immediately).",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Number of calls to simulate.",
    )
    parser.add_argument(
        "--bootstrap-servers",
        default=None,
        help="Kafka bootstrap servers (default: settings.kafka_bootstrap_servers).",
    )
    args = parser.parse_args()
    bootstrap_servers = args.bootstrap_servers or settings.kafka_bootstrap_servers
    raise SystemExit(asyncio.run(_run(args, bootstrap_servers)))


if __name__ == "__main__":
    main()
