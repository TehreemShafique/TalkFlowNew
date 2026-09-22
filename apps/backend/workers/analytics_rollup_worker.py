"""STEP 39 - analytics rollup worker (``apps/backend/workers``).

Every 60 seconds it folds the new call rows into the six ``agg_*`` tables with
the idempotent, watermark-advancing rollup in ``app/modules/analytics/rollup``.
One worker instance is enough for the pilot; the watermark table makes a second
instance safe (each pass is an UPSERT, so concurrent runs are still
snapshot-equal).

Run: ``python -m workers.analytics_rollup_worker``
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.core.config import settings
from app.core.database import async_session_factory
from app.core.logging import configure_logging, get_logger
from app.modules.analytics import rollup

log = get_logger("workers.analytics_rollup")

ROLLUP_INTERVAL_SECONDS = 60


async def _run_pass() -> None:
    started = datetime.now(UTC)
    async with async_session_factory() as db:
        advanced = await rollup.run(db)
    log.info(
        "analytics rollup pass complete",
        aggregates=len(advanced),
        seconds=(datetime.now(UTC) - started).total_seconds(),
    )


async def serve() -> None:
    log.info(
        "analytics rollup worker starting",
        interval_seconds=ROLLUP_INTERVAL_SECONDS,
        app_env=settings.app_env,
    )
    while True:
        try:
            await _run_pass()
        except Exception:
            log.exception("analytics rollup pass failed; retrying on next tick")
        await asyncio.sleep(ROLLUP_INTERVAL_SECONDS)


def main() -> None:
    configure_logging()
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        log.info("analytics rollup worker stopping")


if __name__ == "__main__":
    main()
