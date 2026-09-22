"""Telephony adapter factory (Step 31)."""

from __future__ import annotations

from app.core.config import settings
from app.packages.telephony.manual import ManualDialAdapter
from app.packages.telephony.protocol import TelephonyAdapter


def build_adapter(name: str | None = None) -> TelephonyAdapter:
    """Build and return a configured TelephonyAdapter.

    Defaults to ManualDialAdapter unless explicitly configured otherwise.
    VICIdial sync is deferred to Phase 8 / ai-gateway integration.
    """
    adapter_name = (
        name or getattr(settings, "telephony_adapter", None) or "manual"
    ).lower()
    if adapter_name == "manual":
        return ManualDialAdapter()
    return ManualDialAdapter()
