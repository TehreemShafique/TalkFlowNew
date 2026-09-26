"""60-second incremental watermark rollup worker (STEP 39).

The only writer of the six ``agg_*`` pre-aggregation tables.  Each statement is
an idempotent ``ON CONFLICT ... DO UPDATE`` UPSERT over the half-open window
``started_at >= :watermark AND started_at < :now``, so re-running a pass (or
backfilling a whole day) leaves the aggregate snapshot byte-identical.

``agg_dashboard_counters`` is the one exception: it is a pure replay of current
state rather than a windowed fold, so it carries no ``:watermark`` bound.

Definitions are traced one-for-one in ``docs/metrics.md``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.packages.db.models import (
    AGG_LABEL_UNSET,
    AGG_UUID_UNSET,
    AggBotDaily,
    AggCampaignDaily,
    AggComplianceDaily,
    AggDashboardCounters,
    AggScriptVersionDaily,
    AggSourceDaily,
)

#: Watermark rows are global (one pass folds every tenant), so the tenant key of
#: the watermark ledger is the same ``_unassigned`` sentinel the aggregates use.
GLOBAL_TENANT = AGG_LABEL_UNSET

#: A watermark this old means "never rolled up", so the first pass folds the
#: entire retained history.
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

# Sentinels are inlined into the SQL instead of bound as parameters: they are
# compile-time constants, and a ``:param::uuid`` cast is not a bind SQLAlchemy's
# ``text()`` is able to parse.
_LABEL = AGG_LABEL_UNSET
_UUID = AGG_UUID_UNSET

_AGG_MODELS: dict[str, Any] = {
    AggCampaignDaily.__tablename__: AggCampaignDaily,
    AggScriptVersionDaily.__tablename__: AggScriptVersionDaily,
    AggSourceDaily.__tablename__: AggSourceDaily,
    AggBotDaily.__tablename__: AggBotDaily,
    AggComplianceDaily.__tablename__: AggComplianceDaily,
    AggDashboardCounters.__tablename__: AggDashboardCounters,
}

_SQL: dict[str, str] = {
    AggCampaignDaily.__tablename__: f"""
        INSERT INTO agg_campaign_daily (date, tenant_id, campaign_id, total_calls,
               answered, contacted, qualified, transferred, verifier_accepted,
               disqualified, avg_duration)
        SELECT date(started_at),
               COALESCE(tenant_id, '{_LABEL}'),
               COALESCE(campaign_id, '{_UUID}'::uuid),
               count(*),
               count(*) FILTER (WHERE answered_at IS NOT NULL),
               count(*) FILTER (WHERE disposition IS NOT NULL),
               count(*) FILTER (WHERE qualification_status = 'qualified'),
               count(*) FILTER (WHERE transfer_status = 'completed'),
               count(*) FILTER (WHERE verifier_id IS NOT NULL),
               count(*) FILTER (WHERE qualification_status = 'disqualified'),
               avg(duration_seconds)
        FROM calls
        WHERE started_at >= :watermark AND started_at < :now
        GROUP BY 1, 2, 3
        ON CONFLICT (date, tenant_id, campaign_id) DO UPDATE SET
            total_calls = EXCLUDED.total_calls,
            answered = EXCLUDED.answered,
            contacted = EXCLUDED.contacted,
            qualified = EXCLUDED.qualified,
            transferred = EXCLUDED.transferred,
            verifier_accepted = EXCLUDED.verifier_accepted,
            disqualified = EXCLUDED.disqualified,
            avg_duration = EXCLUDED.avg_duration
    """,
    AggScriptVersionDaily.__tablename__: f"""
        INSERT INTO agg_script_version_daily (date, tenant_id, script_version_id,
               total_calls, answered, contacted, qualified, transferred,
               disqualified, avg_duration)
        SELECT date(started_at),
               COALESCE(tenant_id, '{_LABEL}'),
               COALESCE(script_version_id, '{_UUID}'::uuid),
               count(*),
               count(*) FILTER (WHERE answered_at IS NOT NULL),
               count(*) FILTER (WHERE disposition IS NOT NULL),
               count(*) FILTER (WHERE qualification_status = 'qualified'),
               count(*) FILTER (WHERE transfer_status = 'completed'),
               count(*) FILTER (WHERE qualification_status = 'disqualified'),
               avg(duration_seconds)
        FROM calls
        WHERE started_at >= :watermark AND started_at < :now
        GROUP BY 1, 2, 3
        ON CONFLICT (date, tenant_id, script_version_id) DO UPDATE SET
            total_calls = EXCLUDED.total_calls,
            answered = EXCLUDED.answered,
            contacted = EXCLUDED.contacted,
            qualified = EXCLUDED.qualified,
            transferred = EXCLUDED.transferred,
            disqualified = EXCLUDED.disqualified,
            avg_duration = EXCLUDED.avg_duration
    """,
    AggSourceDaily.__tablename__: f"""
        INSERT INTO agg_source_daily (date, tenant_id, source, total_calls, answered,
               contacted, qualified, transferred, verifier_accepted, disqualified)
        SELECT date(c.started_at),
               COALESCE(c.tenant_id, '{_LABEL}'),
               COALESCE(l.source, '{_LABEL}'),
               count(*),
               count(*) FILTER (WHERE c.answered_at IS NOT NULL),
               count(*) FILTER (WHERE c.disposition IS NOT NULL),
               count(*) FILTER (WHERE c.qualification_status = 'qualified'),
               count(*) FILTER (WHERE c.transfer_status = 'completed'),
               count(*) FILTER (WHERE c.verifier_id IS NOT NULL),
               count(*) FILTER (WHERE c.qualification_status = 'disqualified')
        FROM calls c
        LEFT JOIN leads l ON l.id = c.lead_id
        WHERE c.started_at >= :watermark AND c.started_at < :now
        GROUP BY 1, 2, 3
        ON CONFLICT (date, tenant_id, source) DO UPDATE SET
            total_calls = EXCLUDED.total_calls,
            answered = EXCLUDED.answered,
            contacted = EXCLUDED.contacted,
            qualified = EXCLUDED.qualified,
            transferred = EXCLUDED.transferred,
            verifier_accepted = EXCLUDED.verifier_accepted,
            disqualified = EXCLUDED.disqualified
    """,
    AggBotDaily.__tablename__: f"""
        INSERT INTO agg_bot_daily (date, tenant_id, agent_alias, total_calls, answered,
               contacted, qualified, transferred, avg_talk_time_seconds, avg_duration)
        SELECT date(started_at),
               COALESCE(tenant_id, '{_LABEL}'),
               COALESCE(agent_alias_used, '{_LABEL}'),
               count(*),
               count(*) FILTER (WHERE answered_at IS NOT NULL),
               count(*) FILTER (WHERE disposition IS NOT NULL),
               count(*) FILTER (WHERE qualification_status = 'qualified'),
               count(*) FILTER (WHERE transfer_status = 'completed'),
               avg(talk_time_seconds),
               avg(duration_seconds)
        FROM calls
        WHERE started_at >= :watermark AND started_at < :now
        GROUP BY 1, 2, 3
        ON CONFLICT (date, tenant_id, agent_alias) DO UPDATE SET
            total_calls = EXCLUDED.total_calls,
            answered = EXCLUDED.answered,
            contacted = EXCLUDED.contacted,
            qualified = EXCLUDED.qualified,
            transferred = EXCLUDED.transferred,
            avg_talk_time_seconds = EXCLUDED.avg_talk_time_seconds,
            avg_duration = EXCLUDED.avg_duration
    """,
    AggComplianceDaily.__tablename__: f"""
        INSERT INTO agg_compliance_daily (date, tenant_id, campaign_id, reason,
               total_calls, answered, contacted, qualified, disqualified, opted_out,
               qa_autofail)
        SELECT date(started_at),
               COALESCE(tenant_id, '{_LABEL}'),
               COALESCE(campaign_id, '{_UUID}'::uuid),
               COALESCE(NULLIF(disqualification_reason, ''), '{_LABEL}'),
               count(*),
               count(*) FILTER (WHERE answered_at IS NOT NULL),
               count(*) FILTER (WHERE disposition IS NOT NULL),
               count(*) FILTER (WHERE qualification_status = 'qualified'),
               count(*) FILTER (WHERE qualification_status = 'disqualified'),
               count(*) FILTER (WHERE disqualification_reason = 'opted_out'),
               count(*) FILTER (WHERE qa_status = 'auto_fail')
        FROM calls
        WHERE started_at >= :watermark AND started_at < :now
        GROUP BY 1, 2, 3, 4
        ON CONFLICT (date, tenant_id, campaign_id, reason) DO UPDATE SET
            total_calls = EXCLUDED.total_calls,
            answered = EXCLUDED.answered,
            contacted = EXCLUDED.contacted,
            qualified = EXCLUDED.qualified,
            disqualified = EXCLUDED.disqualified,
            opted_out = EXCLUDED.opted_out,
            qa_autofail = EXCLUDED.qa_autofail
    """,
    # Pure replay of current state, never windowed: no :watermark on purpose.
    # ``CAST`` is required: date_trunc is overloaded, and a bare bind parameter
    # leaves the second argument untyped so Postgres cannot pick an overload.
    AggDashboardCounters.__tablename__: """
        INSERT INTO agg_dashboard_counters (tenant_id, captured_at, total_calls,
               calls_today, answered_today, qualified_today, active_campaigns,
               enabled_scripts, suppression_count, live_calls)
        SELECT :tenant_id,
               CAST(:now AS timestamptz),
               (SELECT count(*) FROM calls),
               (SELECT count(*) FROM calls
                 WHERE started_at >= date_trunc('day', CAST(:now AS timestamptz))),
               (SELECT count(*) FROM calls
                 WHERE started_at >= date_trunc('day', CAST(:now AS timestamptz))
                   AND answered_at IS NOT NULL),
               (SELECT count(*) FROM calls
                 WHERE started_at >= date_trunc('day', CAST(:now AS timestamptz))
                   AND qualification_status = 'qualified'),
               (SELECT count(*) FROM campaigns WHERE status = 'active'),
               (SELECT count(*) FROM scripts WHERE status = 'active'),
               (SELECT count(*) FROM suppression_entries WHERE removed_at IS NULL),
               (SELECT count(*) FROM calls
                 WHERE status IN ('in_progress', 'transferring'))
        ON CONFLICT (tenant_id) DO UPDATE SET
            captured_at = EXCLUDED.captured_at,
            total_calls = EXCLUDED.total_calls,
            calls_today = EXCLUDED.calls_today,
            answered_today = EXCLUDED.answered_today,
            qualified_today = EXCLUDED.qualified_today,
            active_campaigns = EXCLUDED.active_campaigns,
            enabled_scripts = EXCLUDED.enabled_scripts,
            suppression_count = EXCLUDED.suppression_count,
            live_calls = EXCLUDED.live_calls
    """,
}


async def _read_watermark(session: AsyncSession, aggregate_name: str) -> datetime:
    row = await session.execute(
        text(
            "SELECT watermark FROM agg_rollup_watermark "
            "WHERE tenant_id = :tenant_id AND aggregate_name = :aggregate_name"
        ),
        {"tenant_id": GLOBAL_TENANT, "aggregate_name": aggregate_name},
    )
    stored = row.scalar_one_or_none()
    return stored if stored is not None else _EPOCH


async def _write_watermark(
    session: AsyncSession, aggregate_name: str, watermark: datetime
) -> None:
    await session.execute(
        text(
            "INSERT INTO agg_rollup_watermark (tenant_id, aggregate_name, watermark) "
            "VALUES (:tenant_id, :aggregate_name, :watermark) "
            "ON CONFLICT (tenant_id, aggregate_name) DO UPDATE SET "
            "watermark = EXCLUDED.watermark"
        ),
        {
            "tenant_id": GLOBAL_TENANT,
            "aggregate_name": aggregate_name,
            "watermark": watermark,
        },
    )


def _params(window_start: datetime, window_end: datetime) -> dict[str, Any]:
    return {
        "watermark": window_start,
        "now": window_end,
        "tenant_id": GLOBAL_TENANT,
    }


async def _fold(
    session: AsyncSession, window_start: datetime, window_end: datetime
) -> dict[str, int]:
    """UPSERT every aggregate over ``[window_start, window_end)``."""
    rows: dict[str, int] = {}
    params = _params(window_start, window_end)
    for name, sql in _SQL.items():
        result = await session.execute(text(sql), params)
        rows[name] = result.rowcount
    return rows


async def run(
    session: AsyncSession, upto: datetime | None = None
) -> dict[str, datetime]:
    """Advance every aggregate to ``upto`` (default: now); return the new watermark."""
    window_end = upto or datetime.now(UTC)
    advanced: dict[str, datetime] = {}
    for name, sql in _SQL.items():
        window_start = await _read_watermark(session, name)
        await session.execute(text(sql), _params(window_start, window_end))
        await _write_watermark(session, name, window_end)
        advanced[name] = window_end
    await session.commit()
    return advanced


async def backfill(session: AsyncSession, day: date) -> dict[str, int]:
    """Re-fold one whole calendar day. Idempotent: the UPSERT converges."""
    window_start = datetime.combine(day, time.min, tzinfo=UTC)
    window_end = window_start + timedelta(days=1)
    rows = await _fold(session, window_start, window_end)
    await session.commit()
    return rows


async def snapshot(session: AsyncSession, table_name: str) -> dict[tuple, tuple]:
    """Deterministic ``{primary key: all columns}`` view of one aggregate.

    Used by the STEP 39 tests to prove a replayed pass leaves the table
    unchanged, so it must expose every column and never depend on row order.
    """
    model = _AGG_MODELS[table_name]
    table = model.__table__
    rows = (await session.execute(select(model))).scalars().all()
    columns = [column.key for column in table.columns]
    primary_key = [column.key for column in table.primary_key]
    return {
        tuple(getattr(row, key) for key in primary_key): tuple(
            getattr(row, key) for key in columns
        )
        for row in rows
    }
