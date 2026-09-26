"""Async VICIdial Non-Agent API client (B3-1)."""

from __future__ import annotations

from typing import Self

import httpx

from app.packages.vicidial.credentials import (
    VicidialCredentials,
    get_vicidial_credentials,
)
from app.packages.vicidial.parser import VicidialResponse, parse_vicidial_response

_DEFAULT_TIMEOUT = 30.0


class VicidialClient:
    """HTTP client for the VICIdial Non-Agent API.

    All calls POST/GET ``function`` parameters to the configured
    ``non_agent_api.php`` endpoint and parse the plain-text response.
    """

    def __init__(
        self,
        credentials: VicidialCredentials | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._credentials = credentials or get_vicidial_credentials()
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    async def _session(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=_DEFAULT_TIMEOUT, transport=self._transport
            )
        return self._client

    def _base_params(self) -> dict[str, str]:
        return {
            "user": self._credentials.user,
            "pass": self._credentials.password,
            "source": self._credentials.source,
        }

    async def _call(self, function: str, **extra: str) -> VicidialResponse:
        params = self._base_params()
        params.update({"function": function})
        params.update(extra)
        session = await self._session()
        response = await session.get(self._credentials.url, params=params)
        response.raise_for_status()
        return parse_vicidial_response(response.text)

    async def check_version(self) -> str:
        """Return the VICIdial build version string (e.g. ``2.14-721a``)."""
        parsed = await self._call("version")
        if parsed.data:
            return parsed.data[0]
        return ""

    async def add_lead(
        self,
        phone_number: str,
        list_id: str,
        campaign_id: str,
        add_to_hopper: bool = True,
        vendor_lead_code: str | None = None,
    ) -> VicidialResponse:
        """Add a phone number to a VICIdial list.

        ``vendor_lead_code`` carries the TalkFlow lead identifier (``external_key``
        or lead UUID) so the dialer's CDR links back to the control plane without
        a separate lookup.  The returned ``VicidialResponse`` can be inspected
        with :func:`app.packages.vicidial.parser.extract_added_lead_id`.
        """
        params: dict[str, str] = {
            "phone_number": phone_number,
            "list_id": list_id,
            "campaign_id": campaign_id,
        }
        if add_to_hopper:
            params["add_to_hopper"] = "1"
        if vendor_lead_code:
            params["vendor_lead_code"] = vendor_lead_code
        return await self._call("add_lead", **params)

    async def update_lead(
        self, lead_id: int, status: str, user: str = "TALKFLOW"
    ) -> VicidialResponse:
        """Update the status of an existing lead."""
        return await self._call(
            "update_lead", lead_id=str(lead_id), status=status, user=user
        )

    async def add_dnc_phone(self, phone_number: str) -> VicidialResponse:
        """Add a phone number to the VICIdial DNC list."""
        return await self._call("add_dnc_phone", phone_number=phone_number)

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()
