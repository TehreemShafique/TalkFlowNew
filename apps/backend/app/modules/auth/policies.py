"""Login admission policy - a user may authenticate only when APPROVED."""
from __future__ import annotations

from app.packages.contracts.enums import UserStatus

# Admission decision per account status (Rule R6 - deny by default).
_LOGIN_RULES: dict[str, tuple[bool, str | None]] = {
    UserStatus.APPROVED.value: (True, None),
    UserStatus.PENDING.value: (False, "pending"),
    UserStatus.REJECTED.value: (False, "rejected"),
}


def can_login(user_status: str, is_active: bool) -> tuple[bool, str | None]:
    """Validate a user may authenticate.

    Returns ``(allowed, reason)`` where ``reason`` is populated only when the
    login must be denied (Rule R6 - deny by default, message is user-facing).
    """
    if not is_active:
        return False, "disabled"
    return _LOGIN_RULES.get(user_status, (False, "pending"))