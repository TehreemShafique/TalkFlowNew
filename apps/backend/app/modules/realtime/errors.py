"""Realtime error definitions (Step 33)."""

from __future__ import annotations

from typing import Any

from app.packages.contracts.errors import ValidationError, register_error

register_error("realtime.auth_timeout", 4008, "Authentication timeout.")
register_error("realtime.forbidden_channel", 4003, "Channel subscription forbidden.")


class RealtimeAuthTimeoutError(ValidationError):
    def __init__(self, details: dict[str, Any] | None = None) -> None:
        super().__init__("realtime.auth_timeout", details=details)
