"""Connection manager & event fanout for WebSocket clients (Step 33 & Step 36)."""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import WebSocket

from app.core.context import UserContext
from app.core.permissions import sees_full_phi
from app.core.redis import get_redis
from app.core.security import mask_sensitive_payload

logger = structlog.get_logger("realtime.manager")

MAX_OUTBOUND_QUEUE_SIZE = 100
PING_INTERVAL_SECONDS = 30
MAX_MISSED_PINGS = 2
PRESENCE_TTL_SECONDS = 45


@dataclass
class ClientSession:
    socket: WebSocket
    user: UserContext | None = None
    channels: set[str] = field(default_factory=set)
    last_applied_seq: int = -1
    outbound_queue: asyncio.Queue = field(
        default_factory=lambda: asyncio.Queue(maxsize=MAX_OUTBOUND_QUEUE_SIZE)
    )
    missed_pings: int = 0
    authenticated_at: datetime | None = None


_IN_MEMORY_PRESENCE: dict[str, str] = {}


class ConnectionManager:
    """Manages active WebSockets, authorization gates, and per-subscriber fanout."""

    def __init__(self) -> None:
        self.active_sessions: dict[str, ClientSession] = {}

    async def register_socket(self, socket: WebSocket) -> str:
        session_id = str(uuid.uuid4())
        session = ClientSession(socket=socket)
        self.active_sessions[session_id] = session
        return session_id

    async def unregister_socket(self, session_id: str) -> None:
        session = self.active_sessions.pop(session_id, None)
        if session and session.user and session.user.role == "VERIFIER":
            await self._expire_verifier_presence(session.user.user_id)

    async def authenticate_session(self, session_id: str, user: UserContext) -> bool:
        session = self.active_sessions.get(session_id)
        if not session:
            return False
        session.user = user
        session.authenticated_at = datetime.now(UTC)
        if user.role == "VERIFIER":
            await self._refresh_verifier_presence(user.user_id)
        return True

    async def subscribe_channels(
        self, session_id: str, requested_channels: list[str]
    ) -> tuple[list[str], list[str]]:
        """Validate channel permissions and attach to session.

        Returns (allowed_channels, forbidden_channels).
        VERIFIER role is forbidden from calls.live.
        """
        session = self.active_sessions.get(session_id)
        if not session or not session.user:
            return [], requested_channels

        allowed: list[str] = []
        forbidden: list[str] = []

        for channel in requested_channels:
            if channel == "calls.live" and session.user.role == "VERIFIER":
                forbidden.append(channel)
            else:
                session.channels.add(channel)
                allowed.append(channel)

        return allowed, forbidden

    async def record_pong(self, session_id: str) -> None:
        session = self.active_sessions.get(session_id)
        if session:
            session.missed_pings = 0
            if session.user and session.user.role == "VERIFIER":
                await self._refresh_verifier_presence(session.user.user_id)

    async def _refresh_verifier_presence(self, verifier_id: uuid.UUID | str) -> None:
        vid_str = str(verifier_id)
        _IN_MEMORY_PRESENCE[vid_str] = "available"
        try:
            redis_client = get_redis()
            key = f"cp:verifier:{vid_str}:availability"
            await redis_client.set(key, "available", ex=PRESENCE_TTL_SECONDS)
        except Exception as exc:  # noqa: BLE001 - presence is best-effort
            logger.warning(
                "presence refresh failed", verifier_id=vid_str, error=str(exc)
            )

    async def _expire_verifier_presence(self, verifier_id: uuid.UUID | str) -> None:
        vid_str = str(verifier_id)
        _IN_MEMORY_PRESENCE.pop(vid_str, None)
        try:
            redis_client = get_redis()
            key = f"cp:verifier:{vid_str}:availability"
            await redis_client.delete(key)
        except Exception as exc:  # noqa: BLE001 - presence is best-effort
            logger.warning(
                "presence expire failed", verifier_id=vid_str, error=str(exc)
            )

    def _mask_payload_pii(
        self, payload: dict[str, Any], user: UserContext | None
    ) -> dict[str, Any]:
        """Redact PII/PHI for subscribers without the privileged PHI roles."""
        if not user:
            return mask_sensitive_payload(payload)
        if sees_full_phi(user.role, user.permissions):
            return payload
        return mask_sensitive_payload(payload)

    async def fanout_event(
        self, channel: str, event_type: str, raw_payload: dict[str, Any], seq: int
    ) -> None:
        """Deliver event to all authorized subscribers of channel with seq and queue overflow protection."""
        for session_id, session in list(self.active_sessions.items()):
            if channel not in session.channels:
                continue

            # Drop frame if client already applied greater or equal seq
            if seq > 0 and seq <= session.last_applied_seq:
                continue

            masked_data = self._mask_payload_pii(raw_payload, session.user)
            frame = {
                "type": "event",
                "channel": channel,
                "eventType": event_type,
                "seq": seq,
                "data": masked_data,
            }

            try:
                session.outbound_queue.put_nowait(frame)
                session.last_applied_seq = seq
            except asyncio.QueueFull:
                # On overflow emit resync_required rather than growing memory
                logger.warning("outbound queue overflow", session_id=session_id)
                resync_frame = {"type": "resync_required", "reason": "queue_overflow"}
                try:
                    await session.socket.send_text(json.dumps(resync_frame))
                except Exception:  # noqa: BLE001, S110 - best-effort resync signal
                    pass


manager = ConnectionManager()
