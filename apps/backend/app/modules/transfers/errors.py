"""Transfers module error codes (Step 34)."""

from __future__ import annotations

from typing import Any

from app.packages.contracts.errors import (
    ConflictError,
    NotFoundError,
    register_error,
)

register_error("transfer.not_found", 404, "Transfer record not found.")
register_error(
    "transfer.already_claimed",
    409,
    "Transfer offer was already accepted by another verifier.",
)
register_error(
    "transfer.invalid_state", 409, "Transfer is not in a valid state for this action."
)


class TransferNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("transfer.not_found")


class TransferAlreadyClaimedError(ConflictError):
    def __init__(self) -> None:
        super().__init__("transfer.already_claimed")


class TransferInvalidStateError(ConflictError):
    def __init__(self, details: dict[str, Any] | None = None) -> None:
        super().__init__("transfer.invalid_state", details=details)
