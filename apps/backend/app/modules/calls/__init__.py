"""Calls module - ledger of dialed calls plus transcript/event/performance data.

Importing this package registers the module's error codes and exposes the
router used by ``app.main``.  Same 8-file layout as every other module
(schemas, policies, service, repository, events, errors, router).
"""

from app.modules.calls.router import router

__all__ = ["router"]