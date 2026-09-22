"""Telephony adapter protocol (Step 31)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ExternalLeadRef:
    """Reference identifier returned by a telephony adapter."""

    system: str
    external_id: str


@dataclass(frozen=True, slots=True)
class TelephonyLead:
    """Minimal lead data passed into telephony adapters."""

    id: str
    phone_normalized: str
    external_key: str
    first_name: str | None = None
    last_name: str | None = None


@runtime_checkable
class TelephonyAdapter(Protocol):
    """Abstraction for telephony dialers (Manual, VICIdial, WebRTC)."""

    async def dial(self, lead: TelephonyLead) -> ExternalLeadRef: ...

    async def hangup(self, call_id: str) -> bool: ...
