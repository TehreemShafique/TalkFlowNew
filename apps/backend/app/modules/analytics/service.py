"""Analytics service - queries exclusively agg_* pre-aggregated tables (Step 39)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics import repository as repo
from app.modules.analytics.schemas import (
    AnalyticsDateQuery,
    AnalyticsSummaryDTO,
    BotAggDTO,
    CampaignAggDTO,
    ComplianceAggDTO,
    ScriptVersionAggDTO,
    SourceAggDTO,
)
from app.packages.contracts.base import DataResponse


def _fmt_pct(num: int | float, denom: int | float) -> str:
    if not denom:
        return "0.0%"
    return f"{round((num / denom) * 100, 1)}%"


async def get_summary(
    session: AsyncSession, query: AnalyticsDateQuery
) -> DataResponse[AnalyticsSummaryDTO]:
    c_rollups = await repo.get_campaign_rollups(
        session, query.from_date, query.to_date, query.campaign_id
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
        qual_rate=_fmt_pct(qual, ans or tot),
        transfer_rate=_fmt_pct(tx, qual or tot),
        avg_duration_sec=avg_dur,
    )
    return DataResponse(data=dto)


async def get_campaign_analytics(
    session: AsyncSession, query: AnalyticsDateQuery
) -> DataResponse[list[CampaignAggDTO]]:
    rows = await repo.get_campaign_rollups(
        session, query.from_date, query.to_date, query.campaign_id
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
            qual_rate=_fmt_pct(r.qualified, r.answered or r.total_calls),
            transfer_rate=_fmt_pct(r.transferred, r.qualified or r.total_calls),
            avg_duration=round(float(r.avg_duration or 0), 1),
        )
        for r in rows
    ]
    return DataResponse(data=dtos)


async def get_script_analytics(
    session: AsyncSession, query: AnalyticsDateQuery
) -> DataResponse[list[ScriptVersionAggDTO]]:
    rows = await repo.get_script_version_rollups(session, query.from_date, query.to_date)
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
            qual_rate=_fmt_pct(r.qualified, r.answered or r.total_calls),
            avg_duration=round(float(r.avg_duration or 0), 1),
        )
        for r in rows
    ]
    return DataResponse(data=dtos)


async def get_source_analytics(
    session: AsyncSession, query: AnalyticsDateQuery
) -> DataResponse[list[SourceAggDTO]]:
    rows = await repo.get_source_rollups(session, query.from_date, query.to_date)
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
            contact_rate=_fmt_pct(r.contacted, r.total_calls),
            qual_yield=_fmt_pct(r.qualified, r.contacted or r.total_calls),
        )
        for r in rows
    ]
    return DataResponse(data=dtos)


async def get_bot_analytics(
    session: AsyncSession, query: AnalyticsDateQuery
) -> DataResponse[list[BotAggDTO]]:
    rows = await repo.get_bot_rollups(session, query.from_date, query.to_date)
    dtos = [
        BotAggDTO(
            date=r.date,
            agent_alias=r.agent_alias,
            total_calls=r.total_calls,
            answered=r.answered,
            contacted=r.contacted,
            qualified=r.qualified,
            transferred=r.transferred,
            disqualified=r.disqualified,
            avg_duration=round(float(r.avg_duration or 0), 1),
        )
        for r in rows
    ]
    return DataResponse(data=dtos)


async def get_compliance_analytics(
    session: AsyncSession, query: AnalyticsDateQuery
) -> DataResponse[list[ComplianceAggDTO]]:
    rows = await repo.get_compliance_rollups(session, query.from_date, query.to_date)
    dtos = [
        ComplianceAggDTO(
            date=r.date,
            campaign_id=r.campaign_id,
            total_calls=r.total_calls,
            disclaimers_read=r.disclaimers_read,
            opt_outs=r.opt_outs,
            violations=r.violations,
            compliance_rate=_fmt_pct(r.disclaimers_read, r.total_calls),
        )
        for r in rows
    ]
    return DataResponse(data=dtos)
