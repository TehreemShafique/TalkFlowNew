"""Leads module error codes (registered into the central registry).

Codes follow the ``lead.*`` namespace; import wizard failures carry a
``details.reason`` discriminator so the frontend can branch the retry UX.
"""

from __future__ import annotations

from typing import Any

from app.packages.contracts.errors import (
    ConflictError,
    NotFoundError,
    ValidationError,
    register_error,
)

register_error("lead.not_found", 404, "Lead not found.")
register_error("lead.campaign_not_found", 404, "Referenced campaign does not exist.")
register_error("lead.import_job_not_found", 404, "Import job not found.")
register_error("lead.import_no_errors", 404, "This import produced no error report.")
register_error(
    "lead.import_invalid_state",
    409,
    "Import job is not in the state this action requires.",
)
register_error(
    "lead.import_no_mapping",
    409,
    "Save the column mapping before committing the import.",
)
register_error(
    "lead.import_mapping_invalid",
    422,
    "The column mapping does not assign the required 'phone' field.",
)
register_error("lead.import_rows_empty", 422, "The CSV contains no data rows.")
register_error(
    "lead.import_file_too_large",
    422,
    "The CSV exceeds the maximum upload size.",
)
register_error(
    "lead.invalid_phone",
    422,
    "The phone number is not a valid US number.",
)


class LeadNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("lead.not_found")


class CampaignNotFoundError(NotFoundError):
    def __init__(self, campaign_id: Any) -> None:
        super().__init__(
            "lead.campaign_not_found", details={"campaign_id": str(campaign_id)}
        )


class ImportJobNotFoundError(NotFoundError):
    def __init__(self, job_id: Any) -> None:
        super().__init__("lead.import_job_not_found", details={"job_id": str(job_id)})


class ImportNoErrorsError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("lead.import_no_errors")


class ImportInvalidStateError(ConflictError):
    def __init__(self, details: dict[str, Any] | None = None) -> None:
        super().__init__("lead.import_invalid_state", details=details)


class ImportNoMappingError(ConflictError):
    def __init__(self) -> None:
        super().__init__("lead.import_no_mapping")


class ImportMappingInvalidError(ValidationError):
    def __init__(self, missing: list[str]) -> None:
        super().__init__(
            "lead.import_mapping_invalid", details={"missing": sorted(missing)}
        )


class ImportEmptyError(ValidationError):
    def __init__(self) -> None:
        super().__init__("lead.import_rows_empty", details={"reason": "csv_empty"})


class ImportFileTooLargeError(ValidationError):
    def __init__(self, details: dict[str, Any] | None = None) -> None:
        super().__init__("lead.import_file_too_large", details=details)


class LeadInvalidPhoneError(ValidationError):
    def __init__(self) -> None:
        super().__init__("lead.invalid_phone")
