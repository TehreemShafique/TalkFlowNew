"""Typed errors for the QA module (Step 49)."""

from __future__ import annotations

from app.core.errors import AppError
from app.packages.contracts.errors import register_error

register_error("qa.scorecard_not_found", 404, "Requested QA scorecard was not found.")
register_error(
    "qa.self_review_prohibited",
    422,
    "Reviewers are prohibited from reviewing their own calls.",
)
register_error(
    "qa.call_already_reviewed",
    409,
    "Call has already been reviewed under this scorecard.",
)


class QAScorecardNotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__("qa.scorecard_not_found")


class QASelfReviewProhibitedError(AppError):
    def __init__(self) -> None:
        super().__init__("qa.self_review_prohibited")


class QACallAlreadyReviewedError(AppError):
    def __init__(self) -> None:
        super().__init__("qa.call_already_reviewed")
