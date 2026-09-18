"""Registered error codes for the auth module (Rule R2)."""
from __future__ import annotations

from app.packages.contracts.errors import (
    ConflictError,
    NotAuthenticatedError,
    PermissionDeniedError,
    register_error,
)

register_error("auth.invalid_credentials", 401, "Invalid email or password.")
register_error("auth.account_pending", 403, "Your account is awaiting administrator approval.")
register_error("auth.account_rejected", 403, "Your account request was rejected. Please contact an administrator.")
register_error("auth.account_disabled", 403, "Account is disabled. Please contact an administrator.")
register_error("auth.email_conflict", 409, "User with this email already exists.")


class InvalidCredentialsError(NotAuthenticatedError):
    def __init__(self) -> None:
        super().__init__("auth.invalid_credentials")


class AccountPendingError(PermissionDeniedError):
    def __init__(self) -> None:
        super().__init__("auth.account_pending")


class AccountRejectedError(PermissionDeniedError):
    def __init__(self) -> None:
        super().__init__("auth.account_rejected")


class AccountDisabledError(PermissionDeniedError):
    def __init__(self) -> None:
        super().__init__("auth.account_disabled")


class EmailConflictError(ConflictError):
    def __init__(self) -> None:
        super().__init__("auth.email_conflict")