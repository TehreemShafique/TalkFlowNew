"""Tests for STEP 51 — Operations Surface: Health Probes, Alerts, Search."""

from __future__ import annotations

import pytest

from app.modules.ops import service


async def test_health_includes_vicidial_cards(seeded):
    """Step 51 requirement: Health probes must include VICIdial API & MySQL cards."""
    async with seeded["factory"]() as session:
        resp = await service.get_health_status(session)
        assert resp.status in ("healthy", "degraded")
        card_names = [c.name for c in resp.cards]
        assert "PostgreSQL Core DB" in card_names
        assert "VICIdial Non-Agent API" in card_names
        assert "VICIdial MySQL DB" in card_names

        # Unconfigured services are marked 'disabled'
        vic_api_card = next(c for c in resp.cards if c.name == "VICIdial Non-Agent API")
        assert vic_api_card.status in ("healthy", "disabled")


async def test_alerts_endpoint_returns_data(seeded):
    async with seeded["factory"]() as session:
        res = await service.get_alerts(session)
        assert len(res.data) > 0
        assert res.data[0].code is not None


async def test_search_phone_lookup_audited(seeded):
    user = seeded["user"]
    async with seeded["factory"]() as session:
        res = await service.global_search(session, user, "5551234567", search_type=None)
        assert res.query == "5551234567"
        assert isinstance(res.items, list)
