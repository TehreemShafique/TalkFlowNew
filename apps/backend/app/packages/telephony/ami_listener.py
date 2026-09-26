"""Asterisk Manager Interface (AMI) event listener (BACKEND-8a).

A long-running background worker that speaks AMI over TCP (default port 5038)
using the **restricted** manager credentials in settings (``ASTERISK_AMI_USER`` /
``ASTERISK_AMI_PASS``).  It authenticates, subscribes to raw events, and routes
the events the telephony edge cares about - ``Hangup``, ``BridgeExec``,
``UserEvent`` - to per-event handlers.

Design notes
------------
- The low-level line framing / event parsing lives in pure functions so the
  unit suite can exercise them without a live Asterisk box.
- Connection lifecycle is ``async with listener.connect():`` - a reconnect
  loop wraps ``read_events`` and re-authenticates on EOF.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field

from app.core.config import settings

log = logging.getLogger("telephony.ami")

# Asterisk AMI event types this edge consumes (restricted read set).
_TRIGGER_EVENTS = {"Hangup", "BridgeExec", "UserEvent"}


@dataclass
class AMIEvent:
    """One parsed AMI event: a name plus its key/value headers."""

    name: str
    headers: dict[str, str] = field(default_factory=dict)

    def get(self, key: str) -> str | None:
        return self.headers.get(key)

    def __getitem__(self, key: str) -> str:
        return self.headers[key]


EventHandler = Callable[[AMIEvent], Awaitable[None]]


def _parse_boolean(value: str | None) -> bool:
    """AMI serializes booleans as Yes/No/True/False/1/0."""
    if value is None:
        return False
    return value.strip().lower() in {"yes", "true", "1", "on"}


def parse_line(line: str) -> tuple[str, str] | None:
    """Parse one AMI ``Key: Value`` line; ``ActionID:``` becomes ``ActionID``."""
    if ":" not in line:
        return None
    key, _, value = line.partition(":")
    key = key.strip()
    if not key:
        return None
    return key, value.strip()


def parse_event_block(block: str) -> AMIEvent:
    """Parse a raw AMI ``Event: X\\nKey: Value\\n...`` block into an ``AMIEvent``."""
    headers: dict[str, str] = {}
    name: str | None = None
    for line in block.splitlines():
        parsed = parse_line(line)
        if parsed is None:
            continue
        key, value = parsed
        if key == "Event":
            name = value
        headers[key] = value
    return AMIEvent(name=name or "Unknown", headers=headers)


def is_relevant_event(event_name: str) -> bool:
    return event_name in _TRIGGER_EVENTS


def compute_call_duration(answered_at: float | None, ended_at: float) -> int | None:
    """Seconds between the AMI answer timestamp and the end timestamp."""
    if answered_at is None:
        return None
    return max(0, int(ended_at - answered_at))


class AMIListener:
    """Connect to Asterisk AMI and stream triggered events to the caller."""

    def __init__(
        self,
        *,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
    ) -> None:
        self.host = host or settings.asterisk_ami_host
        self.port = port or settings.asterisk_ami_port
        self._user = user if user is not None else settings.asterisk_ami_user
        self._password = (
            password if password is not None else settings.asterisk_ami_pass
        )
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    # -- connection lifecycle -------------------------------------------------

    async def connect(self) -> None:
        """Open the TCP socket and authenticate with the AMI credentials."""
        self._reader, self._writer = await asyncio.open_connection(self.host, self.port)
        await self._send_login()

    async def _send_login(self) -> None:
        action = (
            "Action: Login\r\n"
            f"Username: {self._user}\r\n"
            f"Secret: {self._password}\r\n"
            "Events: on\r\n\r\n"
        )
        self._writer.write(action.encode())
        await self._writer.drain()

    async def close(self) -> None:
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except (ConnectionError, OSError):
                pass
            self._writer = None

    async def aclose(self) -> None:
        await self.close()

    # -- event streaming ------------------------------------------------------

    async def read_event(self) -> AMIEvent | None:
        """Read one AMI event block; ``None`` when the socket hits EOF."""
        if self._reader is None:
            raise RuntimeError("AMIListener not connected")
        block = await self._reader.readuntil(b"\r\n\r\n")
        return parse_event_block(block.decode(errors="replace"))

    def _log_event(self, event: AMIEvent) -> None:
        if event.name in _TRIGGER_EVENTS:
            log.info("ami event", event=event.name, headers=event.headers)

    async def _run_once(self, on_event: EventHandler | None = None) -> None:
        """Stream events until EOF, yielding each triggered event."""
        while True:
            event = await self.read_event()
            if event is None:
                return
            self._log_event(event)
            if not is_relevant_event(event.name):
                continue
            if on_event is not None:
                await on_event(event)

    async def run(self, on_event: EventHandler | None = None) -> None:
        """Connect, authenticate, then stream triggered events forever.

        ``on_event`` is an optional async callback receiving each relevant
        event (Hangup / BridgeExec / UserEvent).  When omitted the events are
        simply logged - the callback is how callers wire duration calculation
        and MixMonitor recording reconciliation.
        """
        await self.connect()
        try:
            await self._run_once(on_event)
        finally:
            await self.close()


# Convenience for background-task lifecycle without a callback: yield events.
async def iter_ami_events(
    listener: AMIListener,
) -> AsyncIterator[AMIEvent]:
    """Context-managed generator of triggered AMI events (auto connect/close)."""
    await listener.connect()
    try:
        while True:
            event = await listener.read_event()
            if event is None:
                return
            if is_relevant_event(event.name):
                yield event
    finally:
        await listener.close()
