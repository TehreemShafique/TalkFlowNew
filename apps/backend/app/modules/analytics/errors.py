"""Analytics module error codes (registered into the central registry)."""

from __future__ import annotations

from typing import Any

from app.packages.contracts.errors import ValidationError, register_error

register_error(
    "analytics.invalid_range",
    422,
    "The analytics date range is invalid (from must not be after to).",
)


class AnalyticsInvalidRangeError(ValidationError):
    def __init__(self, details: dict[str, Any] | None = None) -> None:
        super().__init__("analytics.invalid_range", details=details)
