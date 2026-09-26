"""Tests for B3-1 — VICIdial Non-Agent API client, parser, and methods."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.packages.vicidial.client import VicidialClient
from app.packages.vicidial.credentials import VicidialCredentials
from app.packages.vicidial.methods import add_dnc, add_lead, update_lead_status
from app.packages.vicidial.parser import parse_vicidial_response

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "vicidial"


def load_fixture(name: str) -> str:
    path = FIXTURES_DIR / name
    return path.read_text(encoding="utf-8")


def mock_transport(fixture: str) -> httpx.MockTransport:
    """Return a transport serving a single fixture file for any request."""
    body = load_fixture(fixture)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    return httpx.MockTransport(handler)


@pytest.mark.parametrize(
    "fixture,success,data,notices,error",
    [
        ("version.txt", True, ["2.14-721a", "BUILD: 190822-1925"], [], None),
        (
            "add_lead_success.txt",
            True,
            ["add_lead LEAD HAS BEEN ADDED - 10001", "13125550000"],
            [],
            None,
        ),
        (
            "add_lead_hopper_notice.txt",
            True,
            ["add_lead LEAD HAS BEEN ADDED - 10002"],
            ["NOT ADDED TO HOPPER, OUTSIDE OF LOCAL TIME"],
            None,
        ),
        (
            "add_lead_dup.txt",
            False,
            None,
            [],
            "add_lead LEAD NOT ADDED - DUPLICATE PHONE NUMBER IN LIST",
        ),
        (
            "dnc_add.txt",
            True,
            ["add_dnc_phone PHONE NUMBER ADDED TO DNC - 13125550000"],
            [],
            None,
        ),
    ],
)
def test_parse_vicidial_response(
    fixture: str, success: bool, data, notices: list[str], error: str | None
):
    body = load_fixture(fixture)
    parsed = parse_vicidial_response(body)
    assert parsed.success is success
    assert parsed.data == data
    assert parsed.notices == notices
    assert parsed.error == error
    assert parsed.raw_body == body


def test_parse_hopper_notice_captures_success_and_notice():
    """SUCCESS on line 1 + NOTICE on line 2 must both be captured."""
    body = load_fixture("add_lead_hopper_notice.txt")
    parsed = parse_vicidial_response(body)
    assert parsed.success is True
    assert parsed.data == ["add_lead LEAD HAS BEEN ADDED - 10002"]
    assert parsed.notices == ["NOT ADDED TO HOPPER, OUTSIDE OF LOCAL TIME"]
    assert parsed.error is None


def test_parse_empty_body():
    parsed = parse_vicidial_response("")
    assert parsed.success is False
    assert parsed.data is None
    assert parsed.notices == []
    assert parsed.error is None


def make_client(fixture: str) -> VicidialClient:
    credentials = VicidialCredentials(
        url="http://vicidial.test/vicidial/non_agent_api.php",
        user="talkflow_api",
        password="s3cret",
        source="talkflow",
    )
    return VicidialClient(credentials, transport=mock_transport(fixture))


@pytest.mark.asyncio
async def test_check_version():
    async with make_client("version.txt") as client:
        version = await client.check_version()
    assert version == "2.14-721a"


@pytest.mark.asyncio
async def test_add_lead_success():
    async with make_client("add_lead_success.txt") as client:
        parsed = await client.add_lead(
            "13125550000", list_id="1001", campaign_id="TEST_CAMP"
        )
    assert parsed.success is True
    assert parsed.error is None
    assert "13125550000" in (parsed.data or [])


@pytest.mark.asyncio
async def test_add_lead_hopper_notice():
    async with make_client("add_lead_hopper_notice.txt") as client:
        parsed = await client.add_lead(
            "13125550001", list_id="1001", campaign_id="TEST_CAMP"
        )
    assert parsed.success is True
    assert parsed.data == ["add_lead LEAD HAS BEEN ADDED - 10002"]
    assert parsed.notices == ["NOT ADDED TO HOPPER, OUTSIDE OF LOCAL TIME"]


@pytest.mark.asyncio
async def test_add_lead_duplicate_error():
    async with make_client("add_lead_dup.txt") as client:
        parsed = await client.add_lead(
            "13125550002", list_id="1001", campaign_id="TEST_CAMP"
        )
    assert parsed.success is False
    assert parsed.error is not None
    assert "DUPLICATE" in parsed.error


@pytest.mark.asyncio
async def test_update_lead_status():
    async with make_client("add_lead_success.txt") as client:
        parsed = await client.update_lead(10001, "SALECLOSED", user="TALKFLOW")
    assert parsed.success is True


@pytest.mark.asyncio
async def test_add_dnc_phone():
    async with make_client("dnc_add.txt") as client:
        parsed = await client.add_dnc_phone("13125550000")
    assert parsed.success is True
    assert parsed.error is None


@pytest.mark.asyncio
async def test_http_error_raises():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    credentials = VicidialCredentials(
        url="http://vicidial.test/vicidial/non_agent_api.php",
        user="talkflow_api",
        password="s3cret",
        source="talkflow",
    )
    async with VicidialClient(
        credentials, transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.check_version()


@pytest.mark.asyncio
async def test_methods_add_lead_uses_defaults():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.url.params))
        return httpx.Response(200, text=load_fixture("add_lead_success.txt"))

    transport = httpx.MockTransport(handler)
    parsed = await add_lead("13125550000", transport=transport)
    assert parsed.success is True
    assert captured["list_id"] == "1001"
    assert captured["campaign_id"] == "TEST_CAMP"
    assert captured["add_to_hopper"] == "1"


@pytest.mark.asyncio
async def test_methods_update_lead_status():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=load_fixture("add_lead_success.txt"))

    transport = httpx.MockTransport(handler)
    parsed = await update_lead_status(10001, "SALECLOSED", transport=transport)
    assert parsed.success is True


@pytest.mark.asyncio
async def test_methods_add_dnc():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=load_fixture("dnc_add.txt"))

    transport = httpx.MockTransport(handler)
    parsed = await add_dnc("13125550000", transport=transport)
    assert parsed.success is True
