"""Suppression / DNC register module (spec section 19.4, §14 SUPPRESSION).

One row per suppression event; removal is a soft delete (``removed_at``) that
keeps the audit trail, and the partial unique index guarantees one ACTIVE entry
per number.  Additions/removals are also reflected onto the ``leads`` master
registry (``suppressed`` flag) through the shared projection.
"""

from app.modules.suppression.router import router

__all__ = ["router"]