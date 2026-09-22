"""Manual telephony adapter implementation (Step 31)."""

from __future__ import annotations

import structlog

from app.packages.telephony.protocol import (
    ExternalLeadRef,
    TelephonyAdapter,
    TelephonyLead,
)

logger = structlog.get_logger("telephony.manual")


class ManualDialAdapter(TelephonyAdapter):
    """Fallback manual dialer adapter.

    Logs dial requests and returns an ExternalLeadRef pointing to the lead's external_key.
    """

    async def dial(self, lead: TelephonyLead) -> ExternalLeadRef:
        logger.info(
            "manual dial requested", lead_id=lead.id, external_key=lead.external_key
        )
        return ExternalLeadRef(system="manual", external_id=lead.external_key)

    async def hangup(self, call_id: str) -> bool:
        logger.info("manual hangup requested", call_id=call_id)
        return True
