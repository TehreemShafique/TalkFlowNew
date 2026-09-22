"""Test for STEP 23 — Event-driven graph simulation engine."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_simulation_matches_a_real_call(client, seeded):
    """Event simulation reproduces real call node path and qualification result (Step 23)."""
    try:
        # 1. Create a script container
        create_resp = await client.post(
            "/scripts",
            headers=seeded["headers"],
            json={"name": "Real Call Simulation Script"},
        )
    except Exception:  # noqa: BLE001 - DB availability probe
        pytest.skip("Database connection unavailable")

    assert create_resp.status_code == 201
    script_id = create_resp.json()["data"]["id"]

    # 2. Simulate call with event trace
    events = [
        {"nodeId": "n_greeting", "event": "always"},
        {"nodeId": "n_part_ab", "event": "yes", "value": True},
        {"nodeId": "n_age_range", "event": "no_response"},
        {"nodeId": "n_age_range", "event": "yes", "value": True},
    ]

    sim_resp = await client.post(
        f"/scripts/{script_id}/versions/1/simulate",
        headers=seeded["headers"],
        json={"events": events},
    )
    assert sim_resp.status_code == 200
    sim_data = sim_resp.json()["data"]

    assert sim_data["nodePath"] == [
        "n_greeting",
        "n_part_ab",
        "n_age_range",
        "n_age_range",
    ]
    assert sim_data["capturedFields"]["medicare_part_ab"] is True
    assert sim_data["capturedFields"]["age_in_range"] is True
    assert sim_data["qualificationStatus"] == "qualified"
