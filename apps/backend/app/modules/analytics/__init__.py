"""Analytics module - read-only PRD reports over pre-aggregated tables.

Endpoints never touch the raw ``calls`` table (docs/metrics.md); the rollup
worker (``analytics.rollup`` + ``workers/analytics_rollup_worker``) is the sole
writer of the six ``agg_*`` tables.  Access requires ``analytics.view`` (Rule
R4); every repository read carries an explicit scope (Rule R5).
"""

from app.modules.analytics.errors import AnalyticsInvalidRangeError

__all__ = ["AnalyticsInvalidRangeError"]
