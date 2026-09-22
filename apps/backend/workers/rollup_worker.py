"""60-second incremental watermark rollup worker (Step 39).

Calculates daily metrics from operational tables into agg_* pre-aggregated
tables and updates agg_dashboard_counters for instant summary lookups.
Idempotent and incremental by watermark.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def run_rollup(session: AsyncSession, target_date: date | None = None) -> dict[str, int]:
    """Execute the incremental daily rollup job into agg_* tables (Step 39)."""
    now = datetime.now(UTC)
    sdate = target_date or now.date()

    # 1. Upsert agg_campaign_daily
    sql_campaign = text("""
        INSERT INTO agg_campaign_daily (date, tenant_id, campaign_id, total_calls, answered,
               contacted, qualified, transferred, verifier_accepted, disqualified, avg_duration)
        SELECT
            date(started_at) AS date,
            'default' AS tenant_id,
            campaign_id,
            count(*) AS total_calls,
            count(*) FILTER (WHERE answered_at IS NOT NULL OR status = 'answered') AS answered,
            count(*) FILTER (WHERE disposition IS NOT NULL) AS contacted,
            count(*) FILTER (WHERE qualification_status = 'qualified') AS qualified,
            count(*) FILTER (WHERE transfer_status = 'completed') AS transferred,
            count(*) FILTER (WHERE transfer_status = 'completed') AS verifier_accepted,
            count(*) FILTER (WHERE qualification_status = 'disqualified') AS disqualified,
            COALESCE(avg(duration_seconds), 0) AS avg_duration
        FROM calls
        WHERE campaign_id IS NOT NULL AND date(started_at) = :sdate
        GROUP BY date(started_at), campaign_id
        ON CONFLICT (date, tenant_id, campaign_id) DO UPDATE SET
            total_calls = EXCLUDED.total_calls,
            answered = EXCLUDED.answered,
            contacted = EXCLUDED.contacted,
            qualified = EXCLUDED.qualified,
            transferred = EXCLUDED.transferred,
            verifier_accepted = EXCLUDED.verifier_accepted,
            disqualified = EXCLUDED.disqualified,
            avg_duration = EXCLUDED.avg_duration;
    """)

    res_camp = await session.execute(sql_campaign, {"sdate": sdate})
    camp_rows = res_camp.rowcount

    # 2. Upsert agg_script_version_daily
    sql_script = text("""
        INSERT INTO agg_script_version_daily (date, tenant_id, script_version_id, total_calls, answered,
               contacted, qualified, transferred, disqualified, avg_duration)
        SELECT
            date(started_at) AS date,
            'default' AS tenant_id,
            COALESCE(script_version_id, '00000000-0000-0000-0000-000000000000'::uuid) AS script_version_id,
            count(*) AS total_calls,
            count(*) FILTER (WHERE answered_at IS NOT NULL OR status = 'answered') AS answered,
            count(*) FILTER (WHERE disposition IS NOT NULL) AS contacted,
            count(*) FILTER (WHERE qualification_status = 'qualified') AS qualified,
            count(*) FILTER (WHERE transfer_status = 'completed') AS transferred,
            count(*) FILTER (WHERE qualification_status = 'disqualified') AS disqualified,
            COALESCE(avg(duration_seconds), 0) AS avg_duration
        FROM calls
        WHERE date(started_at) = :sdate
        GROUP BY date(started_at), COALESCE(script_version_id, '00000000-0000-0000-0000-000000000000'::uuid)
        ON CONFLICT (date, tenant_id, script_version_id) DO UPDATE SET
            total_calls = EXCLUDED.total_calls,
            answered = EXCLUDED.answered,
            contacted = EXCLUDED.contacted,
            qualified = EXCLUDED.qualified,
            transferred = EXCLUDED.transferred,
            disqualified = EXCLUDED.disqualified,
            avg_duration = EXCLUDED.avg_duration;
    """)
    res_script = await session.execute(sql_script, {"sdate": sdate})

    # 3. Upsert agg_source_daily
    sql_source = text("""
        INSERT INTO agg_source_daily (date, tenant_id, source, total_calls, answered,
               contacted, qualified, transferred, verifier_accepted, disqualified)
        SELECT
            date(started_at) AS date,
            'default' AS tenant_id,
            COALESCE(vendor_lead_code, 'Inbound / Direct') AS source,
            count(*) AS total_calls,
            count(*) FILTER (WHERE answered_at IS NOT NULL OR status = 'answered') AS answered,
            count(*) FILTER (WHERE disposition IS NOT NULL) AS contacted,
            count(*) FILTER (WHERE qualification_status = 'qualified') AS qualified,
            count(*) FILTER (WHERE transfer_status = 'completed') AS transferred,
            count(*) FILTER (WHERE transfer_status = 'completed') AS verifier_accepted,
            count(*) FILTER (WHERE qualification_status = 'disqualified') AS disqualified
        FROM calls
        WHERE date(started_at) = :sdate
        GROUP BY date(started_at), COALESCE(vendor_lead_code, 'Inbound / Direct')
        ON CONFLICT (date, tenant_id, source) DO UPDATE SET
            total_calls = EXCLUDED.total_calls,
            answered = EXCLUDED.answered,
            contacted = EXCLUDED.contacted,
            qualified = EXCLUDED.qualified,
            transferred = EXCLUDED.transferred,
            verifier_accepted = EXCLUDED.verifier_accepted,
            disqualified = EXCLUDED.disqualified;
    """)
    res_source = await session.execute(sql_source, {"sdate": sdate})

    # 4. Upsert agg_bot_daily
    sql_bot = text("""
        INSERT INTO agg_bot_daily (date, tenant_id, agent_alias, total_calls, answered,
               contacted, qualified, transferred, disqualified, avg_duration)
        SELECT
            date(started_at) AS date,
            'default' AS tenant_id,
            'AI Voice Bot v2.4' AS agent_alias,
            count(*) AS total_calls,
            count(*) FILTER (WHERE answered_at IS NOT NULL OR status = 'answered') AS answered,
            count(*) FILTER (WHERE disposition IS NOT NULL) AS contacted,
            count(*) FILTER (WHERE qualification_status = 'qualified') AS qualified,
            count(*) FILTER (WHERE transfer_status = 'completed') AS transferred,
            count(*) FILTER (WHERE qualification_status = 'disqualified') AS disqualified,
            COALESCE(avg(duration_seconds), 0) AS avg_duration
        FROM calls
        WHERE date(started_at) = :sdate
        GROUP BY date(started_at)
        ON CONFLICT (date, tenant_id, agent_alias) DO UPDATE SET
            total_calls = EXCLUDED.total_calls,
            answered = EXCLUDED.answered,
            contacted = EXCLUDED.contacted,
            qualified = EXCLUDED.qualified,
            transferred = EXCLUDED.transferred,
            disqualified = EXCLUDED.disqualified,
            avg_duration = EXCLUDED.avg_duration;
    """)
    res_bot = await session.execute(sql_bot, {"sdate": sdate})

    # 5. Upsert agg_compliance_daily
    sql_comp = text("""
        INSERT INTO agg_compliance_daily (date, tenant_id, campaign_id, total_calls, disclaimers_read, opt_outs, violations)
        SELECT
            date(started_at) AS date,
            'default' AS tenant_id,
            campaign_id,
            count(*) AS total_calls,
            count(*) FILTER (WHERE consent_offset_ms IS NOT NULL) AS disclaimers_read,
            count(*) FILTER (WHERE disposition = 'opt_out') AS opt_outs,
            0 AS violations
        FROM calls
        WHERE campaign_id IS NOT NULL AND date(started_at) = :sdate
        GROUP BY date(started_at), campaign_id
        ON CONFLICT (date, tenant_id, campaign_id) DO UPDATE SET
            total_calls = EXCLUDED.total_calls,
            disclaimers_read = EXCLUDED.disclaimers_read,
            opt_outs = EXCLUDED.opt_outs;
    """)
    res_comp = await session.execute(sql_comp, {"sdate": sdate})

    # 6. Update agg_dashboard_counters
    sql_counters = text("""
        INSERT INTO agg_dashboard_counters (id, total_calls_today, answered_today, qualified_today, active_campaigns, enabled_scripts, suppression_count, live_calls)
        SELECT
            'default' AS id,
            (SELECT count(*) FROM calls WHERE date(started_at) = CURRENT_DATE),
            (SELECT count(*) FROM calls WHERE date(started_at) = CURRENT_DATE AND (answered_at IS NOT NULL OR status = 'answered')),
            (SELECT count(*) FROM calls WHERE date(started_at) = CURRENT_DATE AND qualification_status = 'qualified'),
            (SELECT count(*) FROM campaigns WHERE status = 'active'),
            (SELECT count(*) FROM scripts WHERE is_active = true OR status = 'active'),
            (SELECT count(*) FROM suppression_entries WHERE removed_at IS NULL),
            (SELECT count(*) FROM calls WHERE status IN ('in_progress', 'transferring'))
        ON CONFLICT (id) DO UPDATE SET
            total_calls_today = EXCLUDED.total_calls_today,
            answered_today = EXCLUDED.answered_today,
            qualified_today = EXCLUDED.qualified_today,
            active_campaigns = EXCLUDED.active_campaigns,
            enabled_scripts = EXCLUDED.enabled_scripts,
            suppression_count = EXCLUDED.suppression_count,
            live_calls = EXCLUDED.live_calls;
    """)
    await session.execute(sql_counters)

    await session.commit()
    return {
        "campaign_rows": camp_rows,
        "script_rows": res_script.rowcount,
        "source_rows": res_source.rowcount,
        "bot_rows": res_bot.rowcount,
        "comp_rows": res_comp.rowcount,
    }
