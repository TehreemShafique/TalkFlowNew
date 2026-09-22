"""Central error-code registry and the single exception hierarchy.

Every module registers its typed error codes through :func:`register_error`
at import time (see ``app/modules/recordings/errors.py```).  A single
exception hierarchy, one FastAPI handler, one error envelope
(``contracts.base.ErrorBody``) guarantee consistent wire errors (Rule R2 /
blueprint section 10).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ErrorDefinition:
    """Immutable description of one registered error code."""

    code: str
    http_status: int
    message: str


_ERROR_REGISTRY: dict[str, ErrorDefinition] = {}


def register_error(code: str, http_status: int, message: str) -> str:
    """Register a typed error code.  Idempotent so module re-imports are safe."""
    if code not in _ERROR_REGISTRY:
        _ERROR_REGISTRY[code] = ErrorDefinition(
            code=code, http_status=http_status, message=message
        )
    return code


def get_error_definition(code: str) -> ErrorDefinition:
    try:
        return _ERROR_REGISTRY[code]
    except KeyError as exc:  # pragma: no cover - programmer error, fail loudly
        raise ValueError(f"Unregistered error code: {code!r}") from exc


def all_error_codes() -> set[str]:
    return set(_ERROR_REGISTRY)


def register_core_errors() -> None:
    """Register cross-cutting codes the control plane always needs."""
    register_error("auth.not_authenticated", 401, "Authentication is required.")
    register_error(
        "auth.permission_denied", 403, "You lack permission for this action."
    )
    register_error("validation.invalid_input", 422, "The request payload is invalid.")
    register_error(
        "resource.conflict", 409, "The request conflicts with current state."
    )


class TalkFlowError(Exception):
    """Base class for every operational error.  Always carries a registered code."""

    def __init__(
        self,
        code: str,
        *,
        message: str | None = None,
        http_status: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        definition = get_error_definition(code)
        self.code: str = definition.code
        self.http_status: int = http_status or definition.http_status
        self.message: str = message or definition.message
        self.details: dict[str, Any] = details or {}
        super().__init__(f"{self.code}: {self.message}")

    def to_envelope(self, trace_id: str) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "status": self.http_status,
                "details": self.details or None,
                "traceId": trace_id,
            }
        }


class NotFoundError(TalkFlowError):
    """maps to HTTP 404"""


class ConflictError(TalkFlowError):
    """maps to HTTP 409"""


class GoneError(TalkFlowError):
    """maps to HTTP 410 - resource existed but is permanently unavailable."""


class PermissionDeniedError(TalkFlowError):
    """maps to HTTP 403"""


class NotAuthenticatedError(TalkFlowError):
    """maps to HTTP 401"""


class ServiceUnavailableError(TalkFlowError):
    """maps to HTTP 503"""


class ValidationError(TalkFlowError):
    """maps to HTTP 422"""
