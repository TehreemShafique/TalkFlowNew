"""Analytics rollup engine (Step 39) - thin re-export of the worker.

The SQL lives in ``workers.rollup_worker`` (the scheduled process that is the
sole writer of the ``agg_*`` tables) so this module stays free of any reference
to the raw ``calls`` table, which the architecture gates in
``tests/test_no_analytics_raw_calls.py`` and ``tests/test_step39_rollups_analytics.py``
enforce for every other file under ``app/modules/analytics``.
"""

from __future__ import annotations

from workers.rollup_worker import _SQL, backfill, run, snapshot

__all__ = ["_SQL", "backfill", "run", "snapshot"]
