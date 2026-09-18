"""Exports module error codes (registered into the central registry)."""

from __future__ import annotations

from typing import Any

from app.packages.contracts.errors import (
    ConflictError,
    NotFoundError,
    ValidationError,
    register_error,
)

register_error("export.not_found", 404, "Export job not found.")
register_error("export.not_ready", 409, "Export artifact is not ready yet.")
register_error(
    "export.unsupported_report", 422, "This report type is not supported yet."
)
register_error(
    "export.filters_invalid",
    422,
    "The export filters are invalid.",
)


class ExportNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("export.not_found")


class ExportNotReadyError(ConflictError):
    def __init__(self, details: dict[str, Any] | None = None) -> None:
        super().__init__("export.not_ready", details=details)


class ExportUnsupportedReportError(ValidationError):
    def __init__(self, report: str, supported: list[str]) -> None:
        super().__init__(
            "export.unsupported_report",
            details={"report": report, "supported": sorted(supported)},
        )


class ExportFiltersInvalidError(ValidationError):
    def __init__(self, details: dict[str, Any] | None = None) -> None:
        super().__init__("export.filters_invalid", details=details)