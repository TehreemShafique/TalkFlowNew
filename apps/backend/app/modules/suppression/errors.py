"""Suppression module error codes (registered into the central registry)."""

from __future__ import annotations

from typing import Any

from app.packages.contracts.errors import (
    ConflictError,
    NotFoundError,
    ValidationError,
    register_error,
)

register_error("suppression.not_found", 404, "Suppression entry not found.")
register_error(
    "suppression.duplicate",
    409,
    "This number already has an active suppression entry.",
)
register_error(
    "suppression.invalid_phone", 422, "The phone number is not a valid US number."
)
register_error("suppression.import_empty", 422, "The CSV contains no data rows.")
register_error(
    "suppression.import_missing_phone_column",
    422,
    "The CSV has no column that maps to the phone number.",
)
register_error(
    "suppression.file_too_large",
    422,
    "The CSV exceeds the maximum upload size.",
)
register_error(
    "suppression.removal_invalid",
    422,
    "Removal requires confirm_removal=='CONFIRM_REMOVAL' and valid rationale.",
)


class SuppressionNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("suppression.not_found")


class SuppressionDuplicateError(ConflictError):
    def __init__(self, phone: str) -> None:
        super().__init__(
            "suppression.duplicate", details={"phone": _display_phone(phone)}
        )


class SuppressionInvalidPhoneError(ValidationError):
    def __init__(self, details: dict[str, Any] | None = None) -> None:
        super().__init__("suppression.invalid_phone", details=details)


class SuppressionImportEmptyError(ValidationError):
    def __init__(self, details: dict[str, Any] | None = None) -> None:
        super().__init__("suppression.import_empty", details=details)


class SuppressionMissingPhoneColumnError(ValidationError):
    def __init__(self) -> None:
        super().__init__("suppression.import_missing_phone_column")


class SuppressionFileTooLargeError(ValidationError):
    def __init__(self, details: dict[str, Any] | None = None) -> None:
        super().__init__("suppression.file_too_large", details=details)


class SuppressionRemovalInvalidError(ValidationError):
    def __init__(self, details: dict[str, Any] | None = None) -> None:
        super().__init__("suppression.removal_invalid", details=details)


def _display_phone(phone: str) -> str:
    return phone if len(phone) <= 4 else f"{phone[-4:]} (last four)"
