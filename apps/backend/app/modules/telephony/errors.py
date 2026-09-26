"""Telephony module error codes (registered into the central registry)."""

from __future__ import annotations

from app.packages.contracts.errors import (
    NotAuthenticatedError,
    register_error,
)

# B2-A header-token authentication for VICIdial webhooks.
register_error("telephony.unauthorized", 401, "Invalid telephony webhook token.")
register_error(
    "telephony.webhook_payload_missing",
    422,
    "Webhook payload is missing required fields.",
)

TelephonyUnauthorizedError = NotAuthenticatedError  # code "telephony.unauthorized"
