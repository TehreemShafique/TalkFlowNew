"""Scripts module domain errors."""

from __future__ import annotations

from app.packages.contracts.errors import (
    ConflictError,
    NotFoundError,
    ValidationError,
    register_error,
)

SCRIPT_NOT_FOUND = "script.not_found"
SCRIPT_VERSION_NOT_FOUND = "script.version_not_found"
SCRIPT_INVALID_TRANSITION = "script.invalid_transition"
SCRIPT_VERSION_NOT_EDITABLE = "script.version_not_editable"
SCRIPT_INVALID_NODE_GRAPH = "script.invalid_node_graph"
SCRIPT_VERSION_CONFLICT = "script.version_conflict"

register_error(SCRIPT_NOT_FOUND, 404, "Script not found.")
register_error(SCRIPT_VERSION_NOT_FOUND, 404, "Script version not found.")
register_error(
    SCRIPT_INVALID_TRANSITION, 409, "Invalid state transition for script version."
)
register_error(
    SCRIPT_VERSION_NOT_EDITABLE,
    409,
    "Script version is immutable once submitted or approved.",
)
register_error(SCRIPT_INVALID_NODE_GRAPH, 422, "Script node graph is invalid.")
register_error(SCRIPT_VERSION_CONFLICT, 409, "Script was modified by another user.")


class ScriptNotFoundError(NotFoundError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(SCRIPT_NOT_FOUND, message=message)


class ScriptVersionNotFoundError(NotFoundError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(SCRIPT_VERSION_NOT_FOUND, message=message)


class ScriptInvalidTransitionError(ConflictError):
    def __init__(self, frm: str, to: str) -> None:
        super().__init__(
            SCRIPT_INVALID_TRANSITION,
            message=f"Cannot transition script version from '{frm}' to '{to}'.",
            details={"fromStatus": frm, "toStatus": to},
        )


class ScriptVersionNotEditableError(ConflictError):
    def __init__(self, status: str) -> None:
        super().__init__(
            SCRIPT_VERSION_NOT_EDITABLE,
            message=f"Script version with status '{status}' cannot be edited; create a new draft version.",
            details={"status": status},
        )


class ScriptInvalidNodeGraphError(ValidationError):
    def __init__(self, problems: list[str]) -> None:
        super().__init__(
            SCRIPT_INVALID_NODE_GRAPH,
            message="Script node graph failed structural validation.",
            details={"problems": problems},
        )


class ScriptVersionConflictError(ConflictError):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(SCRIPT_VERSION_CONFLICT, message=message)
