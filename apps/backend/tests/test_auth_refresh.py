"""Refresh-token rotation, reuse detection and logout (blueprint 11.4).

The access JWT is deliberately short-lived, so these tests pin the behaviour
that makes that safe: login hands out an opaque refresh token, refresh rotates
it against the *same* session jti, presenting a rotated-out token kills the whole
family, and logout/revoke tear both cookies down.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
import pytest_asyncio
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.core.security import (
    decode_access_token,
    hash_password,
    hash_refresh_token,
)
from app.packages.db.models import RefreshToken, User, UserSession

PASSWORD = "correct-horse-battery-staple"
EMAIL = "refresh-test@phonova.io"


@pytest_asyncio.fixture
async def auth_db(engine):
    """Clean DB holding one APPROVED, active user with a real password hash."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await db.execute(
            text(
                "TRUNCATE TABLE outbox, refresh_tokens, user_sessions, "
                "user_roles, users, roles RESTART IDENTITY CASCADE"
            )
        )
        # A real Argon2id hash is required here (unlike the rest of the suite)
        # because this is the only test that actually logs in.
        user = User(
            id=uuid.uuid4(),
            email=EMAIL,
            username="refresh_tester",
            hashed_password=hash_password(PASSWORD),
            full_name="Refresh Tester",
            is_active=True,
            status="APPROVED",
        )
        db.add(user)
        await db.commit()
    return factory


async def _login(client) -> tuple[str, str]:
    """Log in and return ``(access_token, refresh_token)`` from the cookies."""
    response = await client.post(
        "/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return response.cookies["access_token"], response.cookies["refresh_token"]


@pytest.mark.asyncio
async def test_login_sets_access_and_refresh_cookies(client, auth_db):
    access, refresh = await _login(client)

    assert access and refresh
    assert access != refresh
    # The refresh token must be opaque, not a JWT.
    assert refresh.count(".") != 2

    async with auth_db() as db:
        record = await db.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(refresh)
            )
        )
        assert record is not None
        assert record.revoked_at is None
        assert record.session_token_id


@pytest.mark.asyncio
async def test_access_token_ttl_is_short_lived(client, auth_db):
    """Blueprint 11.4 pins the access JWT at 15 minutes.

    ``create_access_token`` stamps only ``exp`` (no ``iat``), so the lifetime is
    measured against the wall clock with a small tolerance.
    """
    before = datetime.now(UTC)
    access, _ = await _login(client)
    after = datetime.now(UTC)
    # PyJWT returns ``exp`` as a POSIX timestamp.
    exp = datetime.fromtimestamp(decode_access_token(access)["exp"], UTC)

    assert before + timedelta(minutes=14) <= exp <= after + timedelta(minutes=16)
    assert timedelta(minutes=settings.access_token_expire_minutes) == timedelta(
        minutes=15
    )


@pytest.mark.asyncio
async def test_refresh_rotates_and_reuses_the_session_jti(client, auth_db):
    access, refresh = await _login(client)
    original_jti = decode_access_token(access)["jti"]

    response = await client.post("/auth/refresh", cookies={"refresh_token": refresh})
    assert response.status_code == 200, response.text

    rotated_access = response.cookies["access_token"]
    rotated_refresh = response.cookies["refresh_token"]
    assert rotated_refresh != refresh, "the refresh token must be single-use"
    assert decode_access_token(rotated_access)["jti"] == original_jti, (
        "refresh must reuse the session jti, not orphan a new session row"
    )

    async with auth_db() as db:
        assert await db.scalar(
            select(func.count()).select_from(UserSession)
        ) == 1, "refresh must not create a second session row"
        old = await db.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(refresh)
            )
        )
        assert old is not None and old.revoked_at is not None
        assert old.replaced_by is not None
        assert await db.scalar(
            select(func.count())
            .select_from(RefreshToken)
            .where(RefreshToken.revoked_at.is_(None))
        ) == 1

    # The rotated access token authenticates a real request.
    me = await client.get("/auth/me", cookies={"access_token": rotated_access})
    assert me.status_code == 200, me.text
    assert me.json()["email"] == EMAIL


@pytest.mark.asyncio
async def test_reusing_a_rotated_out_token_revokes_the_family(client, auth_db):
    _, refresh = await _login(client)
    first = await client.post("/auth/refresh", cookies={"refresh_token": refresh})
    assert first.status_code == 200
    current = first.cookies["refresh_token"]

    replay = await client.post("/auth/refresh", cookies={"refresh_token": refresh})
    assert replay.status_code == 401
    body = replay.json()
    assert body["error"]["code"] == "auth.not_authenticated"
    assert "reuse" in body["error"]["message"].lower()

    # Reuse is treated as compromise: the successor dies too.
    after = await client.post("/auth/refresh", cookies={"refresh_token": current})
    assert after.status_code == 401


@pytest.mark.asyncio
async def test_expired_refresh_token_is_rejected(client, auth_db):
    _, refresh = await _login(client)
    async with auth_db() as db:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == hash_refresh_token(refresh))
            .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await db.commit()

    response = await client.post("/auth/refresh", cookies={"refresh_token": refresh})
    assert response.status_code == 401
    assert "expired" in response.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_unknown_refresh_token_is_rejected(client, auth_db):
    response = await client.post("/auth/refresh", cookies={"refresh_token": "nope"})
    assert response.status_code == 401
    assert "not recognized" in response.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_refresh_without_cookie_is_rejected(client, auth_db):
    response = await client.post("/auth/refresh")
    assert response.status_code == 401
    assert "missing" in response.json()["error"]["message"].lower()


@pytest.mark.asyncio
async def test_revoking_a_session_also_kills_its_refresh_token(client, auth_db):
    """A revoked login must not be resurrectable from a stale refresh cookie."""
    access, refresh = await _login(client)
    jti = decode_access_token(access)["jti"]

    async with auth_db() as db:
        session = await db.scalar(
            select(UserSession).where(UserSession.token_id == jti)
        )
        assert session is not None
        revoke = await client.post(f"/auth/sessions/{session.id}/revoke")
        assert revoke.status_code == 200, revoke.text

    response = await client.post("/auth/refresh", cookies={"refresh_token": refresh})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_both_cookies(client, auth_db):
    access, refresh = await _login(client)

    response = await client.post(
        "/auth/logout", cookies={"access_token": access, "refresh_token": refresh}
    )
    assert response.status_code == 200

    set_cookies = response.headers.get_list("set-cookie")
    assert any(c.startswith(f"{settings.cookie_name}=") for c in set_cookies)
    assert any(c.startswith(f"{settings.cookie_refresh_name}=") for c in set_cookies)

    async with auth_db() as db:
        record = await db.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_refresh_token(refresh)
            )
        )
        assert record is not None and record.revoked_at is not None


@pytest.mark.asyncio
async def test_refresh_rejects_a_disabled_account(client, auth_db):
    _, refresh = await _login(client)
    async with auth_db() as db:
        await db.execute(
            update(User).where(User.email == EMAIL).values(is_active=False)
        )
        await db.commit()

    response = await client.post("/auth/refresh", cookies={"refresh_token": refresh})
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_refresh_token_is_never_stored_in_the_clear(client, auth_db):
    """Only the digest may reach the database."""
    _, refresh = await _login(client)
    async with auth_db() as db:
        rows = list((await db.scalars(select(RefreshToken))).all())
        stored = {r.token_hash for r in rows}
        assert refresh not in stored
        assert hash_refresh_token(refresh) in stored
        assert all(len(h) == 64 for h in stored)


def test_refresh_cookie_is_httponly_and_strict():
    """The cookie attributes are part of the security contract, not a detail."""
    source = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "app"
        / "core"
        / "security.py"
    ).read_text(encoding="utf-8")

    body = source.split("def set_refresh_cookie", 1)[1].split("def ", 1)[0]
    assert "httponly=True" in body
    assert "samesite=_REFRESH_SAMESITE" in body
    assert "secure=settings.cookie_secure" in body


def test_jwt_decode_still_uses_the_session_secret():
    """Refresh work must not have disturbed the access-token signing key."""
    token = jwt.encode(
        {"sub": EMAIL, "jti": "x", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    assert decode_access_token(token)["sub"] == EMAIL
