"""Analytics module events.

The analytics module is read-only: it never publishes outbox events or audit
rows.  Aggregate writes belong exclusively to the rollup worker
(``analytics.rollup``); this module exists so the module skeleton matches the
rest of the tree while making the "no writes from analytics" invariant
explicit.
"""
