"""WebSocket realtime endpoint implementation (/api/v1/ws) (Step 33 & Step 36)."""

from __future__ import annotations

import asyncio
import json

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.core.context import UserContext
from app.core.database import async_session_factory
from app.core.dependencies import fetch_user_by_email
from app.core.permissions import permissions_for_roles
from app.core.security import decode_access_token
from app.modules.realtime.manager import (
    PING_INTERVAL_SECONDS,
    manager,
)

logger = structlog.get_logger("realtime.router")

router = APIRouter(tags=["realtime"])

AUTH_TIMEOUT_SECONDS = 5.0


async def _resolve_user_context(token: str) -> UserContext | None:
    try:
        payload = decode_access_token(token)
        email = payload.get("sub")
        if not email:
            return None

        async with async_session_factory() as db:
            user = await fetch_user_by_email(db, email)
            if not user or not user.is_active:
                return None
            role_names = [r.name for r in user.roles] if user.roles else []
            permissions = permissions_for_roles(role_names)
            role_name = role_names[0] if role_names else "agent"

        return UserContext(
            user_id=user.id,
            tenant_id=None,
            permissions=permissions,
            role=role_name,
        )
    except Exception as exc:  # noqa: BLE001 - token resolution failure falls back to None
        logger.warning("ws token resolution failed", error=str(exc))
        return None


@router.websocket("/ws")
@router.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    session_id = await manager.register_socket(websocket)
    logger.info("ws client connected", session_id=session_id)

    user: UserContext | None = None

    # Step 2: First frame within 5s MUST be auth frame
    try:
        auth_msg = await asyncio.wait_for(
            websocket.receive_text(), timeout=AUTH_TIMEOUT_SECONDS
        )
        data = json.loads(auth_msg)
        if data.get("type") != "auth" or not data.get("token"):
            await websocket.send_text(
                json.dumps({"type": "error", "code": "auth.missing_token"})
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            await manager.unregister_socket(session_id)
            return

        user = await _resolve_user_context(data["token"])
        if not user:
            await websocket.send_text(
                json.dumps({"type": "error", "code": "auth.invalid_token"})
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            await manager.unregister_socket(session_id)
            return

        await manager.authenticate_session(session_id, user)
        await websocket.send_text(
            json.dumps(
                {"type": "auth_ok", "role": user.role, "userId": str(user.user_id)}
            )
        )
    except TimeoutError:
        logger.warning("ws auth timeout", session_id=session_id)
        try:
            await websocket.send_text(
                json.dumps({"type": "error", "code": "auth.timeout"})
            )
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        except Exception:  # noqa: BLE001, S110 - close is best-effort
            pass
        await manager.unregister_socket(session_id)
        return
    except Exception as exc:  # noqa: BLE001 - already logged below
        logger.warning("ws auth error", session_id=session_id, error=str(exc))
        await manager.unregister_socket(session_id)
        return

    # Background task for sending outbound queue frames and pings
    async def outbound_loop():
        session = manager.active_sessions.get(session_id)
        if not session:
            return

        while True:
            try:
                # Wait for queue frame or timeout to send ping
                frame = await asyncio.wait_for(
                    session.outbound_queue.get(), timeout=PING_INTERVAL_SECONDS
                )
                await websocket.send_text(json.dumps(frame))
                session.outbound_queue.task_done()
            except TimeoutError:
                # Send heartbeat ping frame
                session.missed_pings += 1
                if session.missed_pings > 2:
                    logger.warning("ws ping timeout, closing", session_id=session_id)
                    await websocket.close(code=status.WS_1001_GOING_AWAY)
                    break
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:  # noqa: BLE001 - socket teardown path
                    break

    outbound_task = asyncio.create_task(outbound_loop())

    # Inbound receiver loop
    try:
        while True:
            msg_text = await websocket.receive_text()
            msg = json.loads(msg_text)
            msg_type = msg.get("type")

            if msg_type == "pong" or msg_type == "ping":
                await manager.record_pong(session_id)
                if msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

            elif msg_type == "subscribe":
                channels = msg.get("channels", [])
                allowed, forbidden = await manager.subscribe_channels(
                    session_id, channels
                )
                if forbidden:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "error",
                                "code": "auth.forbidden",
                                "details": {"forbiddenChannels": forbidden},
                            }
                        )
                    )
                else:
                    await websocket.send_text(
                        json.dumps({"type": "subscribed", "channels": allowed})
                    )
    except WebSocketDisconnect:
        logger.info("ws disconnected", session_id=session_id)
    except Exception as exc:  # noqa: BLE001 - already logged below
        logger.warning("ws receive loop error", session_id=session_id, error=str(exc))
    finally:
        outbound_task.cancel()
        await manager.unregister_socket(session_id)
