"""RP-27 security regression tests for the recordings surface.

Covers the seven controls in scope:

* object storage encryption (SSE headers) + TLS-only endpoints,
* TLS 1.3 floor and HTTPS enforcement for HTTP/WebSocket traffic,
* realtime PII/PHI masking (phone / MBI / health fields),
* RBAC audio gates on the exact ``recordings:*`` permissions,
* short-lived playback URLs and single-use download grants,
* centralized, append-only audit logging for every grant use.
"""

from __future__ import annotations

import inspect
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import jwt
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core import audit as core_audit
from app.core.config import settings
from app.core.permissions import (
    PERM_RECORDING_DOWNLOAD,
    PERM_RECORDING_FILE_DOWNLOAD,
    PERM_RECORDING_PLAY,
    PERM_RECORDING_READ,
    has_permission,
    permissions_for_roles,
    sees_full_phi,
)
from app.core.redis import DownloadTokenStore
from app.core.security import (
    PHI_REDACTED,
    decode_signed_grant,
    mask_mbi_last_four,
    mask_phone,
    mask_phone_last_four,
    mask_sensitive_payload,
)
from app.core.tls import (
    TLSPolicyError,
    assert_encrypted_endpoint,
    assert_tls_version,
    database_tls_enabled,
    is_tls_version_acceptable,
    server_side_encryption_enabled,
)
from app.modules.realtime.manager import ConnectionManager
from app.modules.recordings.policies import (
    PERM_RECORDING_DOWNLOAD_FILE,
    RecordingPolicy,
)
from app.modules.recordings.policies import (
    PERM_RECORDING_READ as POLICY_READ,
)
from app.packages.db.models import audit_log_table
from app.packages.storage.provider import (
    LocalStorageProvider,
    S3StorageProvider,
    clamp_presign_ttl,
)

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "c5d6e7f8a9b0_rp27_audit_log_immutability.py"
)


# ---------------------------------------------------------------------------
# PII / PHI masking
# ---------------------------------------------------------------------------


def test_phone_mask_never_leaks_area_code():
    assert mask_phone("+1 (850) 555-4586") == "***-***-4586"
    assert mask_phone_last_four("18505554586") == "***-***-4586"
    assert "555" not in mask_phone("18505554586")


def test_mbi_mask_keeps_last_four_only():
    assert mask_mbi_last_four("1EG4-TE5-MK11") == "XXXX-XXXX-4511"
    assert "EG4" not in mask_mbi_last_four("1EG4-TE5-MK11")


def test_health_fields_are_redacted():
    masked = mask_sensitive_payload(
        {
            "dob": "1960-01-01",
            "health_conditions": "diabetes",
            "diagnosis_code": "E11.9",
            "ssn": "123-45-6789",
        }
    )
    assert masked == {
        key: PHI_REDACTED
        for key in ("dob", "health_conditions", "diagnosis_code", "ssn")
    }


def test_payload_masking_is_recursive():
    masked = mask_sensitive_payload(
        {
            "caller": {"number": "+13125551234"},
            "queue": [{"phone": "18505554586"}, {"mbi": "1-2-3-4567"}],
            "campaign": "Medicare",
        }
    )
    assert masked["caller"]["number"] == "***-***-1234"
    assert masked["queue"][0]["phone"] == "***-***-4586"
    assert masked["queue"][1]["mbi"] == "XXXX-XXXX-4567"
    assert masked["campaign"] == "Medicare"


def test_masking_does_not_mutate_the_source_payload():
    payload = {"caller": {"number": "+13125551234"}}
    mask_sensitive_payload(payload)
    assert payload["caller"]["number"] == "+13125551234"


@pytest.mark.parametrize("role", ["MASTER_ADMIN", "COMPLIANCE_OFFICER"])
def test_privileged_roles_reach_unmasked_phi(role):
    assert sees_full_phi(role, set()) is True
    assert sees_full_phi("VIEWER", set()) is False
    assert sees_full_phi("VIEWER", {"pii.view_full"}) is True


def test_realtime_fanout_masks_for_unprivileged_subscriber():
    manager = ConnectionManager()
    payload = {"caller": {"number": "+13125551234"}, "mbi": "1-2-3-4567"}

    viewer = SimpleNamespace(role="VIEWER", permissions={"recording.view"})
    masked = manager._mask_payload_pii(payload, viewer)  # type: ignore[arg-type]
    assert masked["caller"]["number"] == "***-***-1234"
    assert masked["mbi"] == "XXXX-XXXX-4567"

    officer = SimpleNamespace(role="COMPLIANCE_OFFICER", permissions=set())
    assert manager._mask_payload_pii(payload, officer) is payload  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


def test_rbac_uses_exact_recording_permission_names():
    assert PERM_RECORDING_READ == "recordings:read"
    assert PERM_RECORDING_FILE_DOWNLOAD == "recordings:download"
    assert POLICY_READ == "recordings:read"
    assert PERM_RECORDING_DOWNLOAD_FILE == "recordings:download"


def test_legacy_permission_names_remain_accepted():
    assert has_permission({PERM_RECORDING_PLAY}, PERM_RECORDING_READ) is True
    assert has_permission({PERM_RECORDING_DOWNLOAD}, PERM_RECORDING_FILE_DOWNLOAD)
    assert has_permission(set(), PERM_RECORDING_READ) is False


def test_roles_that_may_reach_audio():
    for role in ("MASTER_ADMIN", "COMPLIANCE_OFFICER", "CAMPAIGN_MANAGER", "QA"):
        perms = permissions_for_roles([role])
        assert has_permission(perms, PERM_RECORDING_READ), role
        assert has_permission(perms, PERM_RECORDING_FILE_DOWNLOAD), role
    viewer = permissions_for_roles(["VIEWER"])
    assert has_permission(viewer, PERM_RECORDING_READ)
    assert not has_permission(viewer, PERM_RECORDING_FILE_DOWNLOAD)


def test_recordings_service_uses_alias_aware_policy():
    viewer = SimpleNamespace(role="VIEWER", permissions={PERM_RECORDING_PLAY})
    assert RecordingPolicy.can_play(viewer) is True  # type: ignore[arg-type]
    assert RecordingPolicy.can_download(viewer) is False  # type: ignore[arg-type]


async def test_require_permission_gate_accepts_legacy_aliases():
    from app.core.dependencies import RequirePermission
    from app.packages.contracts.errors import (
        PermissionDeniedError,
        register_core_errors,
    )

    register_core_errors()

    user = SimpleNamespace(
        role="VIEWER", user_id=uuid.uuid4(), permissions={PERM_RECORDING_PLAY}
    )
    gate = RequirePermission(PERM_RECORDING_READ)
    assert await gate(user) is not None  # type: ignore[arg-type]

    user.permissions = set()
    with pytest.raises(PermissionDeniedError) as denied:
        await gate(user)  # type: ignore[arg-type]
    assert "auth.permission_denied" in str(denied.value)


# ---------------------------------------------------------------------------
# Storage encryption + presigned URL hardening
# ---------------------------------------------------------------------------


def test_sse_enabled_by_default_and_requires_key_for_kms(monkeypatch):
    monkeypatch.setattr(settings, "storage_s3_server_side_encryption", "AES256")
    monkeypatch.setattr(settings, "storage_s3_kms_key_id", "")
    assert server_side_encryption_enabled() is True

    monkeypatch.setattr(settings, "storage_s3_server_side_encryption", "aws:kms")
    assert server_side_encryption_enabled() is False
    monkeypatch.setattr(settings, "storage_s3_kms_key_id", "alias/talkflow")
    assert server_side_encryption_enabled() is True

    monkeypatch.setattr(settings, "storage_s3_server_side_encryption", "")
    assert server_side_encryption_enabled() is False


def test_s3_put_signs_server_side_encryption_headers(monkeypatch):
    monkeypatch.setattr(settings, "storage_s3_endpoint", "https://r2.example.com")
    monkeypatch.setattr(settings, "storage_s3_bucket", "talkflow-audio")
    monkeypatch.setattr(settings, "storage_s3_access_key", "AKIAEXAMPLE")
    monkeypatch.setattr(settings, "storage_s3_secret_key", "secret")
    monkeypatch.setattr(settings, "storage_s3_server_side_encryption", "AES256")
    provider = S3StorageProvider()

    assert provider._encryption_headers() == {"x-amz-server-side-encryption": "AES256"}
    _url, headers = provider._sign(
        method="PUT",
        key="rec/1.wav",
        ttl_seconds=60,
        extra_headers=provider._encryption_headers(),
    )
    assert headers["x-amz-server-side-encryption"] == "AES256"

    monkeypatch.setattr(settings, "storage_s3_server_side_encryption", "aws:kms")
    monkeypatch.setattr(settings, "storage_s3_kms_key_id", "alias/talkflow")
    kms_provider = S3StorageProvider()
    assert kms_provider._encryption_headers() == {
        "x-amz-server-side-encryption": "aws:kms",
        "x-amz-server-side-encryption-aws-kms-key-id": "alias/talkflow",
    }


def test_plaintext_storage_endpoint_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "storage_s3_endpoint", "http://minio.example.com")
    monkeypatch.setattr(settings, "storage_s3_bucket", "b")
    monkeypatch.setattr(settings, "storage_s3_access_key", "AKIA")
    monkeypatch.setattr(settings, "storage_s3_secret_key", "s")
    with pytest.raises(TLSPolicyError):
        S3StorageProvider()

    monkeypatch.setattr(settings, "storage_s3_endpoint", "http://localhost:9000")
    assert S3StorageProvider().endpoint == "http://localhost:9000"


def test_presigned_ttls_are_clamped_to_policy_windows():
    assert clamp_presign_ttl(86_400, "stream") == settings.playback_url_ttl_seconds
    assert settings.playback_url_ttl_seconds == 300
    assert settings.download_token_ttl_minutes * 60 == 900
    assert clamp_presign_ttl(0, "stream") == 1
    assert clamp_presign_ttl(10**9, "stream") == 300


def test_local_playback_and_download_grants_have_separate_routes(tmp_path):
    provider = LocalStorageProvider(root=tmp_path, public_base="https://cp.example.com")

    stream_url = provider.build_access_url(
        storage_key="rec/1.wav", purpose="stream", ttl_seconds=300
    )
    assert stream_url.startswith("https://cp.example.com/api/v1/recordings/stream/")

    download_url = provider.build_access_url(
        storage_key="rec/1.wav", purpose="download", ttl_seconds=900
    )
    assert download_url.startswith("https://cp.example.com/api/v1/recordings/download/")

    payload = decode_signed_grant(download_url.rsplit("/", 1)[1])
    assert payload["purpose"] == "download"
    assert payload["exp"] - payload["iat"] == 900
    assert payload["sub"] == "rec/1.wav"


def test_local_provider_blocks_path_traversal(tmp_path):
    provider = LocalStorageProvider(root=tmp_path, public_base="https://cp.example.com")
    with pytest.raises(ValueError):
        provider._path("../../etc/passwd")


def test_download_grant_rejects_incomplete_payloads():
    now = datetime.now(UTC)
    token = jwt.encode(
        {"sub": "rec/1.wav", "purpose": "download", "exp": now + timedelta(minutes=5)},
        settings.jwt_access_secret,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(jwt.PyJWTError):
        decode_signed_grant(token)


# ---------------------------------------------------------------------------
# Single-use consumption
# ---------------------------------------------------------------------------


class _FakeRedis:
    def __init__(self) -> None:
        self.keys: set[str] = set()

    async def set(self, key: str, value: str, *, nx: bool = False, ex: int = 0):
        if nx and key in self.keys:
            return None
        self.keys.add(key)
        return True


class _BrokenRedis:
    async def set(self, *args, **kwargs):
        raise ConnectionError("redis down")


async def test_download_token_is_consumed_once():
    store = DownloadTokenStore(client=_FakeRedis())  # type: ignore[arg-type]
    assert await store.consume("jti-1") is True
    assert await store.consume("jti-1") is False


async def test_download_token_stays_single_use_without_redis():
    store = DownloadTokenStore(client=_BrokenRedis())  # type: ignore[arg-type]
    assert await store.consume("jti-2") is True
    assert await store.consume("jti-2") is False


# ---------------------------------------------------------------------------
# TLS posture
# ---------------------------------------------------------------------------


def test_tls_floor_rejects_older_versions():
    assert settings.require_tls_1_3 is True
    assert is_tls_version_acceptable("TLSv1.3") is True
    assert is_tls_version_acceptable("TLSv1.2") is False
    assert is_tls_version_acceptable(None) is False
    with pytest.raises(TLSPolicyError):
        assert_tls_version("TLSv1.2")


def test_database_tls_detection():
    assert database_tls_enabled("postgresql+asyncpg://u:p@h:5432/db?ssl=require")
    assert database_tls_enabled("postgresql+asyncpg://u:p@h:5432/db?sslmode=require")
    assert not database_tls_enabled("postgresql+asyncpg://u:p@h:5432/db")


def test_plaintext_endpoints_are_rejected_outside_loopback():
    assert_encrypted_endpoint("https://api.example.com", label="public base url")
    assert_encrypted_endpoint("http://localhost:8001", label="public base url")
    with pytest.raises(TLSPolicyError):
        assert_encrypted_endpoint("http://api.example.com", label="public base url")


# ---------------------------------------------------------------------------
# Centralized, append-only audit log
# ---------------------------------------------------------------------------


def test_audit_writer_is_the_single_entry_point():
    params = inspect.signature(core_audit.write_audit).parameters
    assert {
        "actor_id",
        "actor_role",
        "action",
        "resource_type",
        "resource_id",
        "result",
        "details",
    } <= set(params)
    source = inspect.getsource(core_audit.write_audit)
    assert "trace_id()" in source


def test_recordings_service_delegates_to_the_central_audit_writer():
    from app.modules.recordings import service

    source = inspect.getsource(service)
    assert "from app.core.audit import write_audit" in source
    assert "_write_sync_audit" not in source
    assert "audit_log_table" not in source


def test_audit_log_immutability_migration_is_wired():
    migration = MIGRATION.read_text(encoding="utf-8")
    assert "prevent_audit_log_mutation" in migration
    assert "BEFORE UPDATE OR DELETE ON audit_log" in migration


async def test_audit_rows_cannot_be_rewritten(seeded):
    async with seeded["factory"]() as db:
        await db.execute(
            text(
                "CREATE OR REPLACE FUNCTION prevent_audit_log_mutation() "
                "RETURNS TRIGGER AS $$ BEGIN RAISE EXCEPTION 'audit_log is "
                "append-only' USING ERRCODE = '42501'; END; $$ LANGUAGE plpgsql"
            )
        )
        await db.execute(
            text(
                "CREATE TRIGGER trg_audit_log_immutable BEFORE UPDATE OR DELETE "
                "ON audit_log FOR EACH ROW EXECUTE FUNCTION "
                "prevent_audit_log_mutation()"
            )
        )
        await db.execute(
            text(
                "INSERT INTO audit_log (id, ts, actor_id, action, resource_type, "
                "resource_id, result, metadata) VALUES "
                "(gen_random_uuid(), now(), null, 'test.append', 'recording', "
                "00000000-0000-0000-0000-000000000001, 'success', '{}'::json)"
            )
        )
        await db.commit()
        try:
            async with db.begin_nested():
                await db.execute(text("UPDATE audit_log SET result = 'tampered'"))
        except DBAPIError:
            pass  # Expected DBAPIError caught via savepoint
        await db.execute(text("DROP TRIGGER IF EXISTS trg_audit_log_immutable ON audit_log"))
        await db.execute(text("DROP FUNCTION IF EXISTS prevent_audit_log_mutation()"))
        await db.commit()



# ---------------------------------------------------------------------------
# HTTP surface (RBAC, grants, auditing)
# ---------------------------------------------------------------------------


async def _audit_rows(db, action: str) -> list:
    stmt = (
        select(audit_log_table)
        .where(audit_log_table.c.action == action)
        .order_by(audit_log_table.c.ts)
    )
    return list((await db.execute(stmt)).all())


async def test_playback_url_is_audited(client, seeded):
    resp = await client.get(
        f"/recordings/{seeded['recording_id']}/stream", headers=seeded["headers"]
    )
    assert resp.status_code == 200
    async with seeded["factory"]() as db:
        rows = await _audit_rows(db, "recording.played")
        assert rows, "playback grant must be audited"
        assert rows[-1]._mapping["result"] == "granted"
        assert rows[-1]._mapping["trace_id"]
        assert rows[-1]._mapping["resource_id"] == str(seeded["recording_id"])


async def test_download_grant_is_audited_and_single_use(client, seeded):
    resp = await client.get(
        f"/recordings/{seeded['recording_id']}/download", headers=seeded["headers"]
    )
    assert resp.status_code == 200
    download_url = resp.json()

    async with seeded["factory"]() as db:
        rows = await _audit_rows(db, "recording.downloaded")
        assert rows
        assert rows[-1]._mapping["result"] == "granted"
        assert rows[-1]._mapping["metadata"]["single_use"] is True
        assert rows[-1]._mapping["metadata"]["ttl_seconds"] == 900

    first = await client.get(download_url)
    assert first.status_code == 200
    second = await client.get(download_url)
    assert second.status_code == 403

    async with seeded["factory"]() as db:
        denied = await _audit_rows(db, "recording.download")
        assert denied, "reused grant must be audited as denied"
        assert denied[-1]._mapping["result"] == "denied"


async def test_viewer_may_play_but_not_download(client, seeded):
    play = await client.get(
        f"/recordings/{seeded['recording_id']}/stream", headers=seeded["viewer_headers"]
    )
    assert play.status_code == 200

    download = await client.get(
        f"/recordings/{seeded['recording_id']}/download",
        headers=seeded["viewer_headers"],
    )
    assert download.status_code == 403
    assert download.json()["error"]["code"] == "recording.download_unauthorized"

    async with seeded["factory"]() as db:
        rows = await _audit_rows(db, "recording.download")
        assert rows[-1]._mapping["result"] == "denied"


async def test_call_alias_routes_enforce_single_use(client, seeded):
    token_resp = await client.post(
        f"/calls/{seeded['call_id']}/recording/download-token",
        headers=seeded["headers"],
    )
    assert token_resp.status_code == 200
    token = token_resp.json()["data"]["token"]
    payload = decode_signed_grant(token)
    assert payload["recording_id"] == str(seeded["recording_id"])
    assert payload["exp"] - payload["iat"] == 900

    first = await client.get(f"/recordings/download/{token}")
    assert first.status_code == 200
    assert first.content == seeded["audio_bytes"]
    second = await client.get(f"/recordings/download/{token}")
    assert second.status_code == 403


async def test_call_alias_routes_reject_missing_recording(client, seeded):
    unknown_call = uuid.uuid4()
    playback = await client.get(
        f"/calls/{unknown_call}/recording/playback-url", headers=seeded["headers"]
    )
    assert playback.status_code == 404
    token = await client.post(
        f"/calls/{unknown_call}/recording/download-token", headers=seeded["headers"]
    )
    assert token.status_code == 404


async def test_grant_for_purged_recording_is_refused(client, seeded):
    resp = await client.post(
        f"/recordings/{seeded['recording_id']}/purge",
        headers=seeded["headers"],
        json={"reason": "RP-27"},
    )
    assert resp.status_code == 200
    playback = await client.get(
        f"/recordings/{seeded['recording_id']}/stream", headers=seeded["headers"]
    )
    assert playback.status_code == 410
    async with seeded["factory"]() as db:
        rows = await _audit_rows(db, "recording.purge")
        assert rows
        assert rows[-1]._mapping["result"] == "success"


async def test_tls_enforcement_blocks_plaintext_from_remote_hosts(client, engine):
    import httpx

    from app.main import app

    # Loopback / in-process callers stay exempt (no 400 from the TLS gate).
    assert (await client.get("/recordings")).status_code == 401

    transport = httpx.ASGITransport(app=app, client=("203.0.113.7", 51234))
    async with httpx.AsyncClient(
        transport=transport, base_url="http://app.example.com/api/v1"
    ) as remote:
        blocked = await remote.get("/recordings")
        assert blocked.status_code == 400
        assert blocked.json()["error"]["code"] == "security.tls_required"
