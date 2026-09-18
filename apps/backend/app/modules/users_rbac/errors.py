"""Registered error codes for user/RBAC administration (Rule R2)."""
from __future__ import annotations

from app.packages.contracts.errors import (
    ConflictError,
    PermissionDeniedError,
    ValidationError,
    register_error,
)

register_error("user.not_found", 404, "User not found.")
register_error("user.already_approved", 400, "User is already approved.")
register_error("user.already_rejected", 400, "User is already rejected.")
register_error("user.unknown_role", 400, "One or more role names are unknown.")
register_error("user.role_not_assignable", 400, "Role cannot be assigned during approval.")
register_error("user.username_conflict", 409, "User with this username already exists.")
register_error("user.email_conflict", 409, "User with this email already exists.")
register_error("user.master_restricted", 403, "Only a MASTER_ADMIN can grant the MASTER_ADMIN role.")
register_error("user.master_removal", 400, "Cannot remove the MASTER_ADMIN role from an administrator account.")
register_error("user.single_master", 400, "Another account already holds the MASTER_ADMIN role.")
register_error("user.self_delete", 400, "You cannot delete your own account.")
register_error("user.missing_perm", 403, "Insufficient role permissions.")


class UserNotFoundError(ValidationError):
    def __init__(self) -> None:
        super().__init__("user.not_found")


class AlreadyApprovedError(ValidationError):
    def __init__(self) -> None:
        super().__init__("user.already_approved")


class AlreadyRejectedError(ValidationError):
    def __init__(self) -> None:
        super().__init__("user.already_rejected")


class UnknownRoleError(ValidationError):
    def __init__(self) -> None:
        super().__init__("user.unknown_role")


class RoleNotAssignableError(ValidationError):
    def __init__(self, role_names: list[str]) -> None:
        super().__init__(
            "user.role_not_assignable",
            details={"roles": sorted(role_names)},
        )


class UsernameConflictError(ConflictError):
    def __init__(self) -> None:
        super().__init__("user.username_conflict")


class EmailConflictError(ConflictError):
    def __init__(self) -> None:
        super().__init__("user.email_conflict")


class MasterRestrictedError(PermissionDeniedError):
    def __init__(self) -> None:
        super().__init__("user.master_restricted")


class MasterRemovalError(ValidationError):
    def __init__(self) -> None:
        super().__init__("user.master_removal")


class SingleMasterError(ValidationError):
    def __init__(self) -> None:
        super().__init__("user.single_master")


class SelfDeleteError(ValidationError):
    def __init__(self) -> None:
        super().__init__("user.self_delete")