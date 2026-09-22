"""STEP 15 - call ingest consumer worker (``apps/backend/workers``).

Consumes the AI Voice Bot's five ``talkflow.call.*.v1`` Kafka topics and
persists calls, transcripts, qualification evidence and performance metrics
into PostgreSQL, plus the live-call snapshot into Redis
(``cp:call:live:{call_id}`` / ``cp:calls:live:index``).

The worker is the *inbound* half of the events channel; the outbox dispatcher
owns the reverse direction (outbox -> Kafka).  The wire envelope is the
gateway's camelCase JSON; the stored rows use the calls-module snake_case.

Three non-negotiable rules (talkflow_backend.md section 6.2 / roadmap STEP 15):

1. **Dedupe** - every raw event is stored into ``call_events`` keyed by
   ``(call_id, external_event_id)`` under a savepoint, so a duplicate (replay /
   re-delivery / concurrent consumer) is acknowledged and skipped without
   poisoning the surrounding transaction.
2. **Idempotent open on ``channel_id``** - an ``opened`` event reuses the
   existing call for its channel instead of inserting a second row.  The dev
   ``calls`` table is range-partitioned, so a plain unique index on
   ``channel_id`` is impossible there and the lookup is the enforcement point.
3. **Reconcile by ``event_ts``** - a ``closed`` that beats the intermediate
   ``transcript`` / ``event`` messages never reopens the call and never rewinds
   ``ended_at``.  Terminal state is set once; everything else appends.

Run: ``python -m workers.call_ingest_worker``
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import aiokafka
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logging import configure_logging, get_logger
from app.core.redis import get_redis
from app.modules.calls import policies
from app.modules.calls.events import CallEventType, publish_call_event
from app.packages.contracts.enums import CallDirection, CallStatus, QualificationStatus
from app.packages.db.models import (
    Call,
    CallEvent,
    CallNodePath,
    CallPerformance,
    CallQualificationField,
    TranscriptTurn,
)

log = get_logger("workers.call_ingest")

TOPIC_OPENED = "talkflow.call.opened.v1"
TOPIC_EVENT = "talkflow.call.event.v1"
TOPIC_TRANSCRIPT = "talkflow.call.transcript.v1"
TOPIC_FIELD = "talkflow.call.field.v1"
TOPIC_CLOSED = "talkflow.call.closed.v1"

CALL_TOPICS: tuple[str, ...] = (
    TOPIC_OPENED,
    TOPIC_EVENT,
    TOPIC_TRANSCRIPT,
    TOPIC_FIELD,
    TOPIC_CLOSED,
)

LIVE_SNAPSHOT_KEY = "cp:call:live:{}"
LIVE_INDEX_KEY = "cp:calls:live:index"


class WaitForOpenError(RuntimeError):
    """An event referenced a call whose ``opened`` has not been ingested yet.

    Raised toward the daemon so the message is left uncommitted and redelivered
    once the open lands (out-of-order across topics is expected).
    """

    def __init__(self, call_id: uuid.UUID) -> None:
        super().__init__(str(call_id))
        self.call_id = call_id


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------
def _parse_ts(value: Any) -> datetime:
    """Accept the gateway's epoch float or an ISO-8601 string."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, tz=UTC)
    return datetime.fromisoformat(str(value))


def _event_ts(event: dict[str, Any]) -> datetime:
    try:
        return _parse_ts(event.get("eventTs"))
    except (TypeError, ValueError):
        return datetime.now(UTC)


def _opt_uuid(event: dict[str, Any], key: str) -> uuid.UUID | None:
    value = event.get(key)
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _opt_str(event: dict[str, Any], key: str) -> str | None:
    value = event.get(key)
    if value in (None, ""):
        return None
    return str(value)


def _opt_int(value: Any, default: int | None = None) -> int | None:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _opt_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _unwrap_field_value(value: Any) -> Any:
    """Undo the ``{"value": ...}`` envelope the worker persists for evidence."""
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def _event_type_from(topic: str, event: dict[str, Any]) -> str:
    """Canonical event name: prefer the gateway's explicit ``type``; fall back
    to the topic minus its ``talkflow.`` / ``.v1`` prefixes."""
    explicit = _opt_str(event, "type")
    if explicit:
        return explicit
    base = topic.removesuffix(".v1")
    return base.removeprefix("talkflow.") if base.startswith("talkflow.") else base


# Ms -> snake_case column name for the performance snapshot.
_PERFORMANCE_COLUMNS: dict[str, str] = {
    "vadMs": "vad_ms",
    "sttMs": "stt_ms",
    "decideMs": "decide_ms",
    "llmTtftMs": "llm_ttft_ms",
    "llmTotalMs": "llm_total_ms",
    "ttsTtfaMs": "tts_ttfa_ms",
    "ttsTotalMs": "tts_total_ms",
    "totalTurnMs": "total_turn_ms",
}


def _snapshot(
    call: Call, *, node_name: str | None = None, node_id: str | None = None
) -> dict[str, Any]:
    """CamelCase live snapshot for ``cp:call:live:{call_id}``."""
    return {
        "callId": str(call.id),
        "reference": call.reference or str(call.id),
        "channelId": call.channel_id,
        "campaignId": str(call.campaign_id) if call.campaign_id else None,
        "leadId": str(call.lead_id) if call.lead_id else None,
        "agentAlias": call.agent_alias_used,
        "didUsed": call.did_used,
        "callerIdUsed": call.caller_id_used,
        "direction": call.direction,
        "status": call.status,
        "liveState": policies.live_state(call.status),
        "nodeId": node_id,
        "nodeName": node_name,
        "attemptNumber": call.attempt_number or 1,
        "startedAt": call.started_at.isoformat() if call.started_at else None,
        "durationSeconds": call.duration_seconds,
        "qualificationStatus": call.qualification_status,
    }


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
class CallIngestHandler:
    """Per-topic ingest handlers.

    Handlers take an explicit ``AsyncSession`` (the suite binds its own
    engine - tests never need a live broker).  The daemon wraps this class with
    a transaction per message and commits Kafka offsets only for a fully
    handled batch, so retryable failures (incl. ``WaitForOpenError``) are
    redelivered; poison (undecodable) messages are acked and skipped.
    """

    async def handle_topic(
        self, session: AsyncSession, topic: str, event: dict[str, Any]
    ) -> None:
        call_id = _opt_uuid(event, "callId")
        external_event_id = _opt_str(event, "externalEventId")
        if call_id is None or not external_event_id:
            log.warning("ingest: event missing identity envelope", topic=topic)
            return

        if topic == TOPIC_OPENED:
            await self.handle_opened(session, event, call_id, external_event_id)
            return

        call = (
            await session.execute(select(Call).where(Call.id == call_id))
        ).scalar_one_or_none()
        if call is None:
            raise WaitForOpenError(call_id)

        event_type = _event_type_from(topic, event)
        ts = _event_ts(event)
        if not await self._record_event(
            session, call.id, external_event_id, event_type, event, ts
        ):
            return  # duplicate - already recorded (ack + skip)

        if topic == TOPIC_EVENT:
            await self.handle_state_event(session, call, event, ts)
        elif topic == TOPIC_TRANSCRIPT:
            await self.handle_transcript(session, call, event, ts)
        elif topic == TOPIC_FIELD:
            await self.handle_field(session, call, event, ts)
        elif topic == TOPIC_CLOSED:
            await self.handle_closed(session, call, event, ts)

    # ---- opened.v1 --------------------------------------------------------
    async def handle_opened(
        self,
        session: AsyncSession,
        event: dict[str, Any],
        call_id: uuid.UUID,
        external_event_id: str,
    ) -> Call:
        channel_id = _opt_str(event, "channelId")
        if channel_id:
            existing = (
                await session.execute(select(Call).where(Call.channel_id == channel_id))
            ).scalar_one_or_none()
            if existing is not None:
                # Rule 2: the channel already opened; reuse it.  Quarantine the
                # caller-supplied id (do not overwrite the ingested row's key).
                await self._record_event(
                    session,
                    existing.id,
                    external_event_id,
                    "call.opened",
                    event,
                    _event_ts(event),
                )
                await self._write_live_snapshot(existing)
                return existing

        ts = _event_ts(event)
        call = Call(
            id=call_id,
            # keep the gateway's callId as the registry primary key
            reference=_opt_str(event, "reference") or str(call_id),
            direction=_opt_str(event, "direction") or CallDirection.OUTBOUND.value,
            status=CallStatus.IN_PROGRESS.value,
            qualification_status=QualificationStatus.PENDING.value,
            lead_id=_opt_uuid(event, "leadId"),
            campaign_id=_opt_uuid(event, "campaignId"),
            script_id=_opt_uuid(event, "scriptId"),
            script_version_id=_opt_uuid(event, "scriptVersionId"),
            rule_set_version_id=_opt_uuid(event, "ruleSetVersionId"),
            channel_id=channel_id,
            vicidial_call_id=_opt_str(event, "vicidialCallId"),
            vicidial_lead_id=_opt_str(event, "vicidialLeadId"),
            vicidial_list_id=_opt_str(event, "vicidialListId"),
            caller_number=_opt_str(event, "callerNumber"),
            caller_state=_opt_str(event, "callerState"),
            did_used=_opt_str(event, "didUsed"),
            caller_id_used=_opt_str(event, "callerIdUsed"),
            agent_alias_used=_opt_str(event, "agentAlias") or "Adriana",
            attempt_number=_opt_int(event.get("attemptNumber"), 1) or 1,
            started_at=ts,
            answered_at=ts,
        )
        session.add(call)
        await session.flush()
        await self._record_event(
            session, call.id, external_event_id, "call.opened", event, ts
        )
        await self._write_live_snapshot(call)
        return call

    # ---- event.v1 (node traversal) ---------------------------------------
    async def handle_state_event(
        self, session: AsyncSession, call: Call, event: dict[str, Any], ts: datetime
    ) -> None:
        if event.get("type") != "node_entered":
            return  # raw event is already stored; nothing else to persist

        seq = await self._next_seq(
            session, call.id, CallNodePath.call_id, CallNodePath.seq
        )
        session.add(
            CallNodePath(
                call_id=call.id,
                seq=seq,
                node_id=_opt_str(event, "nodeId") or "unknown",
                node_type=_opt_str(event, "nodeType"),
                node_name=_opt_str(event, "nodeName"),
                entered_at=ts,
                meta=(event.get("context") or {}),
            )
        )
        await session.flush()
        await self._update_live_snapshot(
            call,
            node_id=_opt_str(event, "nodeId"),
            node_name=_opt_str(event, "nodeName") or _opt_str(event, "nodeId"),
        )

    # ---- transcript.v1 ----------------------------------------------------
    async def handle_transcript(
        self, session: AsyncSession, call: Call, event: dict[str, Any], ts: datetime
    ) -> None:
        if event.get("isFinal") is False:
            return

        text = str(event.get("text") or "")
        seq = await self._next_seq(
            session, call.id, TranscriptTurn.call_id, TranscriptTurn.seq
        )
        stmt = pg_insert(TranscriptTurn.__table__).values(
            id=uuid.uuid4(),
            call_id=call.id,
            speaker=_opt_str(event, "speaker") or "unknown",
            seq=seq,
            text=text,
            start_ts_ms=_opt_int(event.get("startMs")),
            end_ts_ms=_opt_int(event.get("endMs")),
            node_id=_opt_str(event, "nodeId"),
            confidence=_opt_float(event.get("confidence")),
            redacted=bool(event.get("redacted", False)),
        )
        await session.execute(stmt)

    # ---- field.v1 ----------------------------------------------------------
    async def handle_field(
        self, session: AsyncSession, call: Call, event: dict[str, Any], ts: datetime
    ) -> None:
        field = _opt_str(event, "field")
        if not field:
            return

        session.add(
            CallQualificationField(
                call_id=call.id,
                field=field,
                label=_opt_str(event, "label"),
                value={
                    "value": event.get("value"),
                    "valueType": _opt_str(event, "valueType"),
                    "nodeId": _opt_str(event, "nodeId"),
                },
                captured_at=ts,
                transcript_ref=_opt_str(event, "transcriptRef"),
                confidence=_opt_float(event.get("confidence")),
            )
        )
        await session.flush()
        await self._reevaluate_qualification(session, call)

    # ---- closed.v1 --------------------------------------------------------
    async def handle_closed(
        self, session: AsyncSession, call: Call, event: dict[str, Any], ts: datetime
    ) -> None:
        # Rule 3: once a call is terminal it must never be reopened, and a
        # replayed / late ``closed`` with an earlier event_ts never rewinds it.
        if call.status in policies.TERMINAL_STATUSES:
            return

        proposed = _opt_str(event, "proposedDisposition")
        call.status = (
            CallStatus.FAILED.value
            if event.get("status") == CallStatus.FAILED.value
            else CallStatus.COMPLETED.value
        )
        if call.ended_at is None or ts > call.ended_at:
            call.ended_at = ts
        call.duration_seconds = _opt_int(
            event.get("durationSeconds"), call.duration_seconds
        )
        call.talk_time_seconds = _opt_int(
            event.get("talkTimeSeconds"), default=call.talk_time_seconds
        )
        if proposed and proposed != call.disposition:
            call.disposition = proposed
            qual, reason = policies.qualification_result(proposed)
            if qual:
                call.qualification_status = qual
                call.disqualification_reason = reason
            vici = policies.to_vicidial_status(proposed)
            if vici:
                call.vicidial_status = vici

        performance = event.get("performance")
        if isinstance(performance, dict) and performance:
            await self._upsert_performance(session, call.id, performance)

        await publish_call_event(
            session,
            call_id=call.id,
            reference=call.reference or str(call.id),
            event_type=CallEventType.COMPLETED,
            payload={
                "status": call.status,
                "eventTs": ts.isoformat(),
                "disposition": call.disposition,
                "durationSeconds": call.duration_seconds,
                "talkTimeSeconds": call.talk_time_seconds,
                "qualificationStatus": call.qualification_status,
                "performance": performance,
            },
        )
        await session.flush()
        await self._remove_live_snapshot(call)

    # ---- shared persistence helpers ---------------------------------------
    async def _record_event(
        self,
        session: AsyncSession,
        call_id: uuid.UUID,
        external_event_id: str,
        event_type: str,
        event: dict[str, Any],
        ts: datetime,
    ) -> bool:
        """Persist the raw event; ``True`` when newly recorded, ``False`` on dedupe."""
        exists = (
            await session.execute(
                select(1)
                .select_from(CallEvent)
                .where(
                    CallEvent.call_id == call_id,
                    CallEvent.external_event_id == external_event_id,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if exists:
            log.info(
                "ingest: duplicate event skipped",
                call_id=str(call_id),
                external_event_id=external_event_id,
            )
            return False

        payload = {
            k: v
            for k, v in event.items()
            if k not in ("callId", "externalEventId", "eventTs")
        }
        try:
            async with session.begin_nested():
                session.add(
                    CallEvent(
                        call_id=call_id,
                        external_event_id=external_event_id,
                        type=event_type,
                        payload=payload or None,
                        event_ts=ts,
                    )
                )
                await session.flush()
            return True
        except IntegrityError:
            # Rule 1: a racy consumer won the unique key first.
            log.info(
                "ingest: event deduped by unique index",
                call_id=str(call_id),
                external_event_id=external_event_id,
            )
            return False

    async def _next_seq(
        self,
        session: AsyncSession,
        call_id: uuid.UUID,
        id_column: Any,
        seq_column: Any,
    ) -> int:
        current = (
            await session.execute(
                select(func.coalesce(func.max(seq_column), 0)).where(
                    id_column == call_id
                )
            )
        ).scalar_one()
        return int(current) + 1

    async def _reevaluate_qualification(
        self, session: AsyncSession, call: Call
    ) -> None:
        rows = (
            (
                await session.execute(
                    select(CallQualificationField).where(
                        CallQualificationField.call_id == call.id
                    )
                )
            )
            .scalars()
            .all()
        )
        evidence = {row.field: _unwrap_field_value(row.value) for row in rows}
        status, reason = policies.evaluate_qualification(evidence)
        if (
            status.value == call.qualification_status
            and reason == call.disqualification_reason
        ):
            return
        call.qualification_status = status.value
        call.disqualification_reason = reason
        await self._update_live_snapshot(call)

    async def _upsert_performance(
        self, session: AsyncSession, call_id: uuid.UUID, performance: dict
    ) -> None:
        values: dict[str, Any] = {}
        turn_count = _opt_int(performance.get("turnCount"))
        if turn_count is not None:
            values["turn_count"] = turn_count
        for wire, column in _PERFORMANCE_COLUMNS.items():
            num = _opt_float(performance.get(wire))
            if num is not None:
                values[column] = num
        for column, wire in (
            ("stt_provider", "sttProvider"),
            ("tts_provider", "ttsProvider"),
            ("llm_provider", "llmProvider"),
        ):
            provider = _opt_str(performance, wire)
            if provider is not None:
                values[column] = provider
        if not values:
            return
        row = (
            await session.execute(
                select(CallPerformance).where(CallPerformance.call_id == call_id)
            )
        ).scalar_one_or_none()
        if row is None:
            session.add(CallPerformance(call_id=call_id, **values))
        else:
            for name, value in values.items():
                setattr(row, name, value)
        await session.flush()

    # ---- Redis live snapshot ----------------------------------------------
    async def _write_live_snapshot(
        self,
        call: Call,
        *,
        node_id: str | None = None,
        node_name: str | None = None,
    ) -> None:
        try:
            client = get_redis()
            snap = _snapshot(call, node_id=node_id, node_name=node_name)
            await client.set(LIVE_SNAPSHOT_KEY.format(call.id), json.dumps(snap))
            await client.sadd(LIVE_INDEX_KEY, str(call.id))
        except Exception as exc:  # noqa: BLE001 - Redis is best-effort
            log.warning(
                "ingest: redis live write failed", call_id=str(call.id), error=str(exc)
            )

    async def _update_live_snapshot(
        self,
        call: Call,
        *,
        node_id: str | None = None,
        node_name: str | None = None,
    ) -> None:
        try:
            client = get_redis()
            key = LIVE_SNAPSHOT_KEY.format(call.id)
            raw = await client.get(key)
            snap = json.loads(raw) if raw else _snapshot(call)
            snap["status"] = call.status
            snap["liveState"] = policies.live_state(call.status)
            if call.qualification_status:
                snap["qualificationStatus"] = call.qualification_status
            if node_id is not None:
                snap["nodeId"] = node_id
            if node_name is not None:
                snap["nodeName"] = node_name
            await client.set(key, json.dumps(snap))
        except Exception as exc:  # noqa: BLE001 - Redis is best-effort
            log.warning(
                "ingest: redis live update failed", call_id=str(call.id), error=str(exc)
            )

    async def _remove_live_snapshot(self, call: Call) -> None:
        try:
            client = get_redis()
            await client.delete(LIVE_SNAPSHOT_KEY.format(call.id))
            await client.srem(LIVE_INDEX_KEY, str(call.id))
        except Exception as exc:  # noqa: BLE001 - Redis is best-effort
            log.warning(
                "ingest: redis live remove failed", call_id=str(call.id), error=str(exc)
            )


# ---------------------------------------------------------------------------
# Daemon
# ---------------------------------------------------------------------------
def _build_consumer() -> aiokafka.AIOKafkaConsumer:
    return aiokafka.AIOKafkaConsumer(
        *CALL_TOPICS,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_call_ingest_group,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        session_timeout_ms=120_000,
        max_poll_interval_ms=300_000,
        max_poll_records=100,
    )


def _decode(value: bytes | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        decoded = json.loads(value.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    return decoded if isinstance(decoded, dict) else None


async def _process_message(
    handler: CallIngestHandler, message: aiokafka.ConsumerRecord
) -> bool:
    """Apply one message transactionally; ``True`` = handled, ``False`` = retry."""
    event = _decode(message.value)
    if event is None:
        log.warning(
            "ingest: poison message acked and skipped",
            topic=message.topic,
            offset=message.offset,
        )
        return True
    try:
        async with async_session_factory() as session:
            await handler.handle_topic(session, message.topic, event)
            await session.commit()
        return True
    except WaitForOpenError as exc:
        log.info(
            "ingest: waiting for open before consuming event",
            call_id=str(exc),
            topic=message.topic,
            offset=message.offset,
        )
        return False
    except Exception as exc:  # redeliver on any ingest failure
        log.exception(
            "ingest: message handling failed (offset left uncommitted)",
            topic=message.topic,
            offset=message.offset,
            error=str(exc),
        )
        return False


async def run_worker(stop_event: asyncio.Event | None = None) -> None:
    handler = CallIngestHandler()
    consumer = _build_consumer()
    await consumer.start()
    log.info(
        "call ingest worker started",
        topics=CALL_TOPICS,
        group=settings.kafka_call_ingest_group,
        bootstrap=settings.kafka_bootstrap_servers,
    )
    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            try:
                batch = await consumer.getmany(timeout_ms=1_000, max_records=100)
            except Exception as exc:  # noqa: BLE001 - transient broker errors poll again
                log.warning("ingest: poll failed", error=str(exc))
                await asyncio.sleep(1)
                continue
            if not batch:
                continue

            batch_ok = True
            for messages in batch.values():
                for message in messages:
                    if not await _process_message(handler, message):
                        batch_ok = False
                        break
                if not batch_ok:
                    break
            if batch_ok:
                await consumer.commit()  # commit only a fully handled batch
    finally:
        await consumer.stop()


def main() -> None:
    configure_logging()
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
