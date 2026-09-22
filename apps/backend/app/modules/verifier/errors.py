"""Verifier module error codes (Step 35)."""

from __future__ import annotations

from typing import Any

from app.packages.contracts.errors import (
    ConflictError,
    NotFoundError,
    register_error,
)

register_error(
    "verifier.call_not_found", 404, "No active call found for this verifier."
)
register_error("verifier.accept_failed", 409, "Failed to accept transfer offer.")


class VerifierCallNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("verifier.call_not_found")


class VerifierAcceptFailedError(ConflictError):
    def __init__(self, details: dict[str, Any] | None = None) -> None:
        super().__init__("verifier.accept_failed", details=details)
