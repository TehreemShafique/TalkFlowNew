"""High-level VICIdial Non-Agent API helpers (B3-1)."""

from __future__ import annotations

import httpx

from app.packages.vicidial.client import VicidialClient
from app.packages.vicidial.credentials import get_vicidial_credentials
from app.packages.vicidial.parser import VicidialResponse


async def add_lead(
    phone_number: str,
    add_to_hopper: bool = True,
    list_id: str | None = None,
    campaign_id: str | None = None,
    *,
    vendor_lead_code: str | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> VicidialResponse:
    """Add a lead using the configured default list and campaign."""
    credentials = get_vicidial_credentials()
    resolved_list = list_id or credentials.default_list_id
    resolved_campaign = campaign_id or credentials.default_campaign_id
    async with VicidialClient(credentials, transport=transport) as client:
        return await client.add_lead(
            phone_number,
            list_id=resolved_list,
            campaign_id=resolved_campaign,
            add_to_hopper=add_to_hopper,
            vendor_lead_code=vendor_lead_code,
        )


async def update_lead_status(
    lead_id: int,
    status: str,
    user: str = "TALKFLOW",
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> VicidialResponse:
    """Update a lead's status to a new disposition."""
    async with VicidialClient(transport=transport) as client:
        return await client.update_lead(lead_id, status, user=user)


async def add_dnc(
    phone_number: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> VicidialResponse:
    """Add a phone number to the VICIdial DNC list."""
    async with VicidialClient(transport=transport) as client:
        return await client.add_dnc_phone(phone_number)
