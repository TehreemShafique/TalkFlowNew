"""Analytics service - reads pre-aggregated tables only (Step 39).

Every function takes the caller's resolved ``Scope`` (Rule R5) rather than
deriving one, so the tenant filter can never be forgotten at a call site.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics import repository as repo
from app.modules.analytics.policies import (
    Scope,
    contact_rate,
    qualification_rate,
    transfer_success,
    verifier_close_rate,
)
from app.modules.analytics.schemas import (
    AnalyticsDateQuery,
    AnalyticsSummaryDTO,
    BotAggDTO,
    CampaignAggDTO,
    ComplianceAggDTO,
    PerformanceAggDTO,
    ScriptVersionAggDTO,
    SourceAggDTO,
)
from app.packages.contracts.base import DataResponse

#: Telemetry lookback when the caller states no range.
PERFORMANCE_DEFAULT_DAYS = 30


def _fmt_pct(num: float, denom: float) -> str:
    if not denom:
        return "0.0%"
    return f"{round((num / denom) * 100, 1)}%"


async def get_summary(
    session: AsyncSession, scope: Scope, query: AnalyticsDateQuery
) -> DataResponse[AnalyticsSummaryDTO]:
    c_rollups = await repo.get_campaign_rollups(
        session, scope, query.from_date, query.to_date, query.campaign_id
    )

    tot = sum(r.total_calls for r in c_rollups)
    ans = sum(r.answered for r in c_rollups)
    cnt = sum(r.contacted for r in c_rollups)
    qual = sum(r.qualified for r in c_rollups)
    tx = sum(r.transferred for r in c_rollups)
    v_acc = sum(r.verifier_accepted for r in c_rollups)
    disq = sum(r.disqualified for r in c_rollups)

    dur_sum = sum((r.avg_duration or 0) * r.total_calls for r in c_rollups)
    avg_dur = round(dur_sum / tot, 1) if tot > 0 else 0.0

    dto = AnalyticsSummaryDTO(
        total_calls=tot,
        answered_calls=ans,
        contacted_calls=cnt,
        qualified_calls=qual,
        transferred_calls=tx,
        verifier_accepted=v_acc,
        disqualified_calls=disq,
        answer_rate=_fmt_pct(ans, tot),
        qual_rate=_fmt_pct(qual, cnt or tot),
        transfer_rate=_fmt_pct(tx, qual or tot),
        avg_duration_sec=avg_dur,
    )
    return DataResponse(data=dto)


async def get_campaign_analytics(
    session: AsyncSession, scope: Scope, query: AnalyticsDateQuery
) -> DataResponse[list[CampaignAggDTO]]:
    rows = await repo.get_campaign_rollups(
        session, scope, query.from_date, query.to_date, query.campaign_id
    )
    dtos = [
        CampaignAggDTO(
            date=r.date,
            campaign_id=r.campaign_id,
            campaign_name=None,
            total_calls=r.total_calls,
            answered=r.answered,
            contacted=r.contacted,
            qualified=r.qualified,
            transferred=r.transferred,
            verifier_accepted=r.verifier_accepted,
            disqualified=r.disqualified,
            answer_rate=_fmt_pct(r.answered, r.total_calls),
            qual_rate=_fmt_pct(r.qualified, r.contacted or r.total_calls),
            transfer_rate=_fmt_pct(r.transferred, r.qualified or r.total_calls),
            avg_duration=round(float(r.avg_duration or 0), 1),
        )
        for r in rows
    ]
    return DataResponse(data=dtos)


async def get_script_analytics(
    session: AsyncSession, scope: Scope, query: AnalyticsDateQuery
) -> DataResponse[list[ScriptVersionAggDTO]]:
    rows = await repo.get_script_version_rollups(
        session, scope, query.from_date, query.to_date
    )
    dtos = [
        ScriptVersionAggDTO(
            date=r.date,
            script_version_id=r.script_version_id,
            script_name=None,
            version=None,
            total_calls=r.total_calls,
            answered=r.answered,
            contacted=r.contacted,
            qualified=r.qualified,
            transferred=r.transferred,
            disqualified=r.disqualified,
            qual_rate=_fmt_pct(r.qualified, r.contacted or r.total_calls),
            avg_duration=round(float(r.avg_duration or 0), 1),
        )
        for r in rows
    ]
    return DataResponse(data=dtos)


async def get_source_analytics(
    session: AsyncSession, scope: Scope, query: AnalyticsDateQuery
) -> DataResponse[list[SourceAggDTO]]:
    rows = await repo.get_source_rollups(
        session, scope, query.from_date, query.to_date
    )
    dtos = [
        SourceAggDTO(
            date=r.date,
            source=r.source,
            vendor_name=r.source,
            total_calls=r.total_calls,
            answered=r.answered,
            contacted=r.contacted,
            qualified=r.qualified,
            transferred=r.transferred,
            verifier_accepted=r.verifier_accepted,
            disqualified=r.disqualified,
            contact_rate=_fmt_pct(r.contacted, r.answered or r.total_calls),
            qual_yield=_fmt_pct(r.qualified, r.contacted or r.total_calls),
        )
        for r in rows
    ]
    return DataResponse(data=dtos)


async def get_bot_analytics(
    session: AsyncSession, scope: Scope, query: AnalyticsDateQuery
) -> DataResponse[list[BotAggDTO]]:
    rows = await repo.get_bot_rollups(session, scope, query.from_date, query.to_date)
    dtos = [
        BotAggDTO(
            date=r.date,
            agent_alias=r.agent_alias,
            total_calls=r.total_calls,
            answered=r.answered,
            contacted=r.contacted,
            qualified=r.qualified,
            transferred=r.transferred,
            disqualified=0,
            avg_duration=round(float(r.avg_duration or 0), 1),
        )
        for r in rows
    ]
    return DataResponse(data=dtos)


async def get_compliance_analytics(
    session: AsyncSession, scope: Scope, query: AnalyticsDateQuery
) -> DataResponse[list[ComplianceAggDTO]]:
    rows = await repo.get_compliance_rollups(
        session, scope, query.from_date, query.to_date
    )
    # The rollup stores one row per disqualification reason; the report collapses
    # the reasons back into a single per-campaign day (docs/metrics.md).
    merged: dict[tuple, ComplianceAggDTO] = {}
    for r in rows:
        key = (r.date, r.campaign_id)
        dto = merged.get(key)
        if dto is None:
            dto = ComplianceAggDTO(
                date=r.date,
                campaign_id=r.campaign_id,
                total_calls=r.total_calls,
                disclaimers_read=0,
                opt_outs=0,
                violations=0,
                compliance_rate="0.0%",
            )
            merged[key] = dto
        dto.disclaimers_read += r.answered
        dto.opt_outs += r.opted_out
        dto.violations += r.disqualified
        dto.compliance_rate = _fmt_pct(
            dto.total_calls - dto.violations, dto.total_calls
        )
    return DataResponse(data=list(merged.values()))


def _window_start(query: AnalyticsDateQuery) -> datetime:
    if query.from_date:
        return datetime.combine(query.from_date, time.min, tzinfo=UTC)
    today = datetime.now(UTC).date()
    return datetime.combine(
        today - timedelta(days=PERFORMANCE_DEFAULT_DAYS), time.min, tzinfo=UTC
    )


def _window_end(query: AnalyticsDateQuery) -> datetime:
    if query.to_date:
        # ``to`` is inclusive on the wire, so the half-open bound is the next day.
        return datetime.combine(
            query.to_date + timedelta(days=1), time.min, tzinfo=UTC
        )
    return datetime.now(UTC)


async def get_performance_analytics(
    session: AsyncSession, scope: Scope, query: AnalyticsDateQuery
) -> DataResponse[list[PerformanceAggDTO]]:
    """Latency percentiles per day and LLM provider (docs/metrics.md)."""
    rows = await repo.get_performance_rollups(
        session, scope, _window_start(query), _window_end(query)
    )
    dtos = [
        PerformanceAggDTO(
            date=r.date,
            provider=r.provider,
            samples=r.samples,
            p50_turn_ms=round(float(r.p50_turn_ms), 1),
            p95_turn_ms=round(float(r.p95_turn_ms), 1),
            p99_turn_ms=round(float(r.p99_turn_ms), 1),
        )
        for r in rows
    ]
    return DataResponse(data=dtos)
