"""Calls module error codes (registered into the central registry).

Mirrors the campaigns module: typed codes are registered at import time and
the domain exceptions subclass the shared hierarchy, so the single FastAPI
handler in ``app.main`` serializes every call error to the one envelope
(Rule R2 / blueprint section 10).
"""

from __future__ import annotations

from typing import Any

from app.packages.contracts.errors import (
    ConflictError,
    NotFoundError,
    ValidationError,
    register_error,
)

register_error("call.not_found", 404, "Call not found.")
register_error(
    "call.invalid_state",
    409,
    "Call is not in a state that permits this action.",
)
register_error(
    "call.invalid_disposition",
    422,
    "The disposition value is not permitted for this call.",
)


class CallNotFoundError(NotFoundError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__("call.not_found", message=message)


class CallInvalidStateError(ConflictError):
    def __init__(self, details: dict[str, Any] | None = None) -> None:
        super().__init__("call.invalid_state", details=details)


class CallInvalidDispositionError(ValidationError):
    def __init__(self, details: dict[str, Any] | None = None) -> None:
        super().__init__("call.invalid_disposition", details=details)