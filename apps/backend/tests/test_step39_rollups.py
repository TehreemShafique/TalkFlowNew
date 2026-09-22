"""STEP 39 - rollup idempotency and watermark incremental behaviour.

DB-gated integration tests (they need PostgreSQL, like the rest of the
integration suite).  The rollup worker (``workers/analytics_rollup_worker``) is
the ONLY writer of the six ``agg_*`` tables; these tests prove the two STEP 39
guarantees:

- **idempotency** - re-running a window (or a full-day backfill) yields an
  identical ``agg_*`` snapshot;
- **incremental watermarking** - a second ``run()`` with no new calls leaves the
  aggregate bytes untouched.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.modules.analytics import rollup
from app.packages.db.models import (
    AGG_LABEL_UNSET,
    AggCampaignDaily,
    calls_table,
)

_DAY = date(2026, 9, 20)


async def _seed_calls(session) -> None:
    """Insert a deterministic single-day call set through the projection.

    Only the columns exported by ``calls_table`` are written; the rest of the
    real table takes its server defaults (NULL), which the rollup folds with
    COALESCE into the ``_unassigned`` buckets.
    """
    campaign_id = uuid.uuid4()
    lead_id = uuid.uuid4()
    started = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
    rows = [
        {
            "id": uuid.uuid4(),
            "tenant_id": None,
            "started_at": started + timedelta(seconds=i),
            "duration_seconds": 20 + (i % 3) * 10,
            "disposition": "IQA-8000-007" if i < 6 else "NA",
            "qualification_status": "qualified" if i < 4 else "disqualified",
            "disqualification_reason": "opted_out" if i == 6 else None,
            "lead_id": lead_id,
            "campaign_id": campaign_id,
            "verifier_id": uuid.uuid4() if i < 2 else None,
        }
        for i in range(8)
    ]
    await session.execute(calls_table.insert().values(rows))
    await session.commit()


async def _count_total(session) -> int:
    rows = await session.execute(select(AggCampaignDaily.total_calls))
    return sum(r.total_calls for r in rows)


async def test_backfill_is_idempotent(seeded) -> None:
    async with seeded["factory"]() as db:
        await _seed_calls(db)
        await rollup.backfill(db, _DAY)
        first = await rollup.snapshot(db, AggCampaignDaily.__tablename__)
        await rollup.backfill(db, _DAY)
        second = await rollup.snapshot(db, AggCampaignDaily.__tablename__)
        assert first == second
        assert await _count_total(db) == 8


async def test_run_is_incremental_and_watermark_advances(seeded) -> None:
    async with seeded["factory"]() as db:
        await _seed_calls(db)
        now = datetime(2026, 9, 20, 13, 0, tzinfo=UTC)
        advanced = await rollup.run(db, upto=now)
        assert set(advanced) == set(rollup._SQL)

        first = await rollup.snapshot(db, AggCampaignDaily.__tablename__)
        advanced_again = await rollup.run(db, upto=now)
        second = await rollup.snapshot(db, AggCampaignDaily.__tablename__)
        assert advanced_again == {name: now for name in rollup._SQL}
        assert first == second


async def test_rollup_is_tenant_unset_in_global_space(seeded) -> None:
    """Current calls carry tenant_id NULL; the global aggregates keep the
    ``_unassigned`` sentinel so unrestricted principals still see them."""
    async with seeded["factory"]() as db:
        await _seed_calls(db)
        await rollup.run(db, upto=datetime(2026, 9, 20, 13, 0, tzinfo=UTC))
        row = await db.get(
            AggCampaignDaily,
            (date(2026, 9, 20), AGG_LABEL_UNSET, uuid.UUID(int=0)),
        )
        assert row is not None
        assert row.total_calls == 8


async def test_dashboard_counters_have_no_watermark_window(seeded) -> None:
    """agg_dashboard_counters is a pure replay of the current state, so it
    can never skew from the incremental window logic."""
    async with seeded["factory"]() as db:
        await _seed_calls(db)
        assert ":watermark" not in rollup._SQL["agg_dashboard_counters"]
        assert "FROM calls" in rollup._SQL["agg_dashboard_counters"]
