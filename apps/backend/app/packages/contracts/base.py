"""Shared API contracts.

Single alias generator, every DTO enforces it, so the wire format is always
camelCase while the Python code is snake_case.  Response envelopes follow the
committed frontend contract (apps/dashboard, spec section 13)::

    single resource   {"data": {...}}
    collection        {"data": [...], "meta": {page, pageSize, total, totalPages}}
    error             {"error": {code, message, status, details, traceId}}
"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class APIBaseModel(BaseModel):
    """Pydantic model with the project-wide camelCase wire convention."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        extra="forbid",
    )


class DataResponse(APIBaseModel, Generic[T]):  # noqa: UP046 - generic alias kept for FastAPI response_model
    """Envelope for a single resource: ``{"data": <T>}``."""

    data: T


class PagedMeta(APIBaseModel):
    """Pagination metadata returned with every collection."""

    page: int
    page_size: int
    total: int
    total_pages: int
    sort: str | None = None
    order: str | None = None


class PagedResponse(APIBaseModel, Generic[T]):  # noqa: UP046 - generic alias kept for FastAPI response_model
    """Collection envelope: ``{"data": [<T>], "meta": {...}}``.

    Rendered directly (not double-wrapped) so the browser receives the exact
    shape the dashboard's paginated tables consume.
    """

    data: list[T]
    meta: PagedMeta


class ErrorDetails(APIBaseModel):
    code: str
    message: str
    status: int
    details: dict[str, Any] | None = None
    trace_id: str


class ErrorBody(APIBaseModel):
    error: ErrorDetails


def camelize(value: str) -> str:
    """Public alias generator helper used by schemas that opt into camelCase."""
    return to_camel(value)