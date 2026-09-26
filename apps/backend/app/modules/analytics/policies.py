"""Analytics policies - pure metric definitions (ADR-03: zero I/O).

The dashboard, and this module's DTO assembly, share one source of truth for
how a KPI is derived (blueprint §14.4, docs/metrics.md).  Everything here is a
pure function over plain integers so the rate math is exhaustively testable
without a database.

A rate whose denominator is zero is ``0.0`` — never ``NaN``, never a
ZeroDivisionError — and every rate is rounded to 4dp so repeated HTTP reads are
stable.
"""

from __future__ import annotations

from typing import Any

from app.core.context import UserContext
from app.core.permissions import ADMIN_ROLE_NAMES

_RATE_SCALE = 10_000

#: The explicit read scope every repository query must be handed (Rule R5).
#: ``{}`` means unrestricted; ``{"tenant_id": ...}`` narrows to one tenant.
Scope = dict[str, Any]


def scope_unlimited(user: UserContext) -> bool:
    """Warehouse reads are unrestricted for Master Admin / DevOps IT (Rule R5)."""
    return user.role in ADMIN_ROLE_NAMES


def resolve_scope_constraints(user: UserContext) -> dict[str, Any]:
    """Return the explicit scope filter to enforce (Rule R5, no default).

    Unrestricted principals read every tenant's aggregates; everyone else is
    narrowed to their assigned tenant id, so cross-tenant analytics reads are
    structurally impossible.
    """
    constraints: dict[str, Any] = {}
    if not scope_unlimited(user) and user.scope.tenant_id:
        constraints["tenant_id"] = user.scope.tenant_id
    return constraints


def safe_ratio(numerator: int, denominator: int) -> float:
    """``numerator / denominator`` with a zero-denominator guard."""
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def contact_rate(contacted: int, answered: int) -> float:
    """Contact rate: conversation-layer outcomes / telephony-answered."""
    return safe_ratio(contacted, answered)


def qualification_rate(qualified: int, contacted: int) -> float:
    """Qualification rate: qualified / contacted."""
    return safe_ratio(qualified, contacted)


def transfer_success(transferred: int, qualified: int) -> float:
    """Transfer success: transfer.completed / qualified."""
    return safe_ratio(transferred, qualified)


def verifier_close_rate(verifier_accepted: int, transferred: int) -> float:
    """Verifier close rate: verifier.sale / transfer.completed."""
    return safe_ratio(verifier_accepted, transferred)


__all__ = [
    "Scope",
    "contact_rate",
    "qualification_rate",
    "resolve_scope_constraints",
    "safe_ratio",
    "scope_unlimited",
    "transfer_success",
    "verifier_close_rate",
]
