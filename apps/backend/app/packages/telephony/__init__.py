"""Telephony package seam (Step 31)."""

from app.packages.telephony.factory import build_adapter
from app.packages.telephony.manual import ManualDialAdapter
from app.packages.telephony.protocol import (
    ExternalLeadRef,
    TelephonyAdapter,
    TelephonyLead,
)

__all__ = [
    "ExternalLeadRef",
    "ManualDialAdapter",
    "TelephonyAdapter",
    "TelephonyLead",
    "build_adapter",
]
