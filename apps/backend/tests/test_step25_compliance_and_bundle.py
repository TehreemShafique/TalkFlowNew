"""Tests for STEP 25 — Compliance profiles and Redis bundle compilation."""

from __future__ import annotations

import json
import uuid

import pytest

from app.modules.compliance.policies import compile_script_bundle
from app.modules.compliance.service import publish_bundle_to_redis


class MemoryRedis:
    def __init__(self):
        self._store: dict[str, bytes] = {}

    async def set(self, key: str, value: str):
        self._store[key] = value.encode() if isinstance(value, str) else value

    async def get(self, key: str):
        return self._store.get(key)


@pytest.mark.asyncio
async def test_activation_publishes_bundle():
    """Version activation compiles and publishes bundle to Redis keys (Step 25)."""
    redis = MemoryRedis()
    campaign_id = uuid.uuid4()
    script_id = uuid.uuid4()
    version_id = uuid.uuid4()

    script_version_dict = {
        "id": version_id,
        "script_id": script_id,
        "version": 1,
        "entry_node_id": "n_greeting",
        "nodes": [
            {
                "id": "n_greeting",
                "prompt": "Hello",
                "transitions": [{"nextNodeId": "n_closing"}],
            },
            {
                "id": "n_closing",
                "prompt": "Goodbye",
                "terminal": True,
            },
        ],
    }

    bundle = compile_script_bundle(script_version_dict)
    await publish_bundle_to_redis(redis, campaign_id, version_id, bundle)

    ptr = await redis.get(f"cp:campaign:{campaign_id}:active_script")
    assert ptr is not None
    assert ptr.decode() == str(version_id)

    raw_bundle = await redis.get(f"cp:script:bundle:{version_id}")
    assert raw_bundle is not None
    parsed = json.loads(raw_bundle.decode())
    assert parsed["entryNodeId"] == "n_greeting"
    assert len(parsed["nodes"]) == 2


@pytest.mark.asyncio
async def test_inflight_calls_keep_their_bundle():
    """In-flight calls keep their compiled bundle in Redis when new version is activated (Step 25)."""
    redis = MemoryRedis()
    campaign_id = uuid.uuid4()

    v1_id = uuid.uuid4()
    v1_bundle = compile_script_bundle(
        {"id": v1_id, "script_id": uuid.uuid4(), "version": 1, "nodes": []}
    )
    await publish_bundle_to_redis(redis, campaign_id, v1_id, v1_bundle)
    bundle_before = await redis.get(f"cp:script:bundle:{v1_id}")

    v2_id = uuid.uuid4()
    v2_bundle = compile_script_bundle(
        {"id": v2_id, "script_id": uuid.uuid4(), "version": 2, "nodes": []}
    )
    await publish_bundle_to_redis(redis, campaign_id, v2_id, v2_bundle)

    # v1 bundle must still exist intact in Redis
    assert await redis.get(f"cp:script:bundle:{v1_id}") == bundle_before
