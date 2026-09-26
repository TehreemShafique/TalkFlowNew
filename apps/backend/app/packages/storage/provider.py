"""Storage providers - local disk and S3/MinIO/R2.

Local provider returns **short-lived signed playback/download grants** (not raw
paths - Rule R7); S3/MinIO returns **SigV4 presigned URLs** hand-rolled so the
control plane has no botocore dependency (pyproject.toml has none).

RP-27: object storage is private, TLS-only, and every PUT is written with
server-side encryption (``AES256`` or ``aws:kms``); presigned GETs are clamped
to a short TTL so a leaked URL expires quickly.
"""

from __future__ import annotations

import hashlib
import hmac
import urllib.parse
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.security import create_signed_grant
from app.core.tls import (
    TLSPolicyError,
    assert_encrypted_endpoint,
    server_side_encryption_enabled,
)
from app.packages.contracts.enums import StorageProvider

StorageResult = str  # presigned URL or signed grant token payload

_PURPOSE_ROUTES = {"stream": "stream", "download": "download"}


def clamp_presign_ttl(ttl_seconds: int, purpose: str) -> int:
    """Never hand out a presigned URL that outlives its policy window."""
    ceiling = settings.storage_presign_max_ttl_seconds
    if purpose == "stream":
        ceiling = min(ceiling, settings.playback_url_ttl_seconds)
    try:
        ttl = int(ttl_seconds)
    except (TypeError, ValueError):
        ttl = ceiling
    return max(1, min(ttl, ceiling))


class BaseStorageProvider(ABC):
    @abstractmethod
    def build_access_url(
        self, *, storage_key: str, purpose: str, ttl_seconds: int
    ) -> str:
        """Return an externally usable URL/grant for reading the object."""

    @abstractmethod
    async def put_bytes(
        self,
        storage_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        """Persist raw bytes (CSV error reports, export artifacts)."""

    @abstractmethod
    async def read_bytes(self, storage_key: str) -> bytes:
        """Read the full object back (download path)."""

    @abstractmethod
    async def delete(self, storage_key: str) -> None:
        """Best-effort removal of the physical object."""


class LocalStorageProvider(BaseStorageProvider):
    def __init__(
        self, root: Path | None = None, public_base: str | None = None
    ) -> None:
        self.root = Path(root or settings.storage_local_root).resolve()
        self.public_base = (public_base or settings.storage_public_base_url).rstrip("/")

    def _path(self, storage_key: str) -> Path:
        # storage_key is provider-relative; never allow escaping the root.
        safe = storage_key.replace("\\", "/").lstrip("/")
        candidate = (self.root / safe).resolve()
        if not str(candidate).startswith(str(self.root)):
            raise ValueError("storage key escapes provider root")
        return candidate

    def build_access_url(
        self, *, storage_key: str, purpose: str, ttl_seconds: int
    ) -> str:
        route = _PURPOSE_ROUTES.get(purpose, "stream")
        token, _ = create_signed_grant(
            storage_key,
            purpose=purpose,
            ttl_seconds=clamp_presign_ttl(ttl_seconds, purpose),
        )
        quoted = urllib.parse.quote(token, safe="")
        return f"{self.public_base}/api/v1/recordings/{route}/{quoted}"

    async def put_bytes(
        self,
        storage_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        path = self._path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def read_bytes(self, storage_key: str) -> bytes:
        return self._path(storage_key).read_bytes()

    async def delete(self, storage_key: str) -> None:
        path = self._path(storage_key)
        try:
            path.unlink(missing_ok=True)
        except FileNotFoundError:
            return


class S3StorageProvider(BaseStorageProvider):
    """SigV4 presigned URLs + signed PUT/DELETE via httpx (no botocore)."""

    def __init__(self) -> None:
        self.endpoint = settings.storage_s3_endpoint.rstrip("/")
        self.bucket = settings.storage_s3_bucket
        self.region = settings.storage_s3_region
        self.access_key = settings.storage_s3_access_key
        self.secret_key = settings.storage_s3_secret_key
        self.encryption = (settings.storage_s3_server_side_encryption or "").strip()
        self.kms_key_id = (settings.storage_s3_kms_key_id or "").strip()
        if not (self.endpoint and self.bucket and self.access_key and self.secret_key):
            raise RuntimeError("S3 storage selected but S3 settings are not configured")
        assert_encrypted_endpoint(self.endpoint, label="storage endpoint")
        if not server_side_encryption_enabled():
            raise TLSPolicyError(
                "S3/MinIO storage requires storage_s3_server_side_encryption "
                "(AES256 or aws:kms with a key id)"
            )

    def _encryption_headers(self) -> dict[str, str]:
        """Server-side encryption headers applied to every stored object."""
        headers = {"x-amz-server-side-encryption": self.encryption}
        if self.encryption in ("aws:kms", "aws:kms:dsse") and self.kms_key_id:
            headers["x-amz-server-side-encryption-aws-kms-key-id"] = self.kms_key_id
        if self.encryption == "aws:kms:dsse":
            headers["x-amz-server-side-encryption-customer-algorithm"] = "AES256"
        return headers

    def _sign(
        self,
        *,
        method: str,
        key: str,
        ttl_seconds: int,
        purpose: str = "",
        max_ttl_seconds: int | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[str, dict[str, str]]:
        """Return a SigV4 presigned URL plus the headers the client must echo."""
        host = urllib.parse.urlsplit(self.endpoint).netloc
        path = urllib.parse.quote(f"/{self.bucket}/{key.lstrip('/')}")
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        ceiling = settings.storage_presign_max_ttl_seconds
        if purpose == "stream":
            ceiling = min(ceiling, settings.playback_url_ttl_seconds)
        if max_ttl_seconds is not None:
            ceiling = min(ceiling, max_ttl_seconds)
        try:
            requested = int(ttl_seconds)
        except (TypeError, ValueError):
            requested = ceiling
        exp = max(1, min(requested, ceiling))
        scope = f"{date_stamp}/{self.region}/s3/aws4_request"

        payload_hash = hashlib.sha256(b"").hexdigest()
        header_pairs = {
            "host": host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
            **(extra_headers or {}),
        }
        canonical_headers = "".join(
            f"{name}:{header_pairs[name]}\n" for name in sorted(header_pairs)
        )
        signed_headers = ";".join(sorted(header_pairs))
        params = (
            f"X-Amz-Algorithm=AWS4-HMAC-SHA256"
            f"&X-Amz-Credential={urllib.parse.quote(f'{self.access_key}/{scope}', safe='')}"
            f"&X-Amz-Date={amz_date}&X-Amz-Expires={exp}&X-Amz-SignedHeaders={signed_headers}"
        )
        canonical_request = f"{method}\n{path}\n{params}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        string_to_sign = (
            f"AWS4-HMAC-SHA256\n{amz_date}\n{scope}\n"
            f"{hashlib.sha256(canonical_request.encode()).hexdigest()}"
        )

        def hmac_sha256(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode(), hashlib.sha256).digest()

        k_date = hmac_sha256(("AWS4" + self.secret_key).encode(), date_stamp)
        k_region = hmac_sha256(k_date, self.region)
        k_service = hmac_sha256(k_region, "s3")
        k_signing = hmac_sha256(k_service, "aws4_request")
        signature = hmac.new(
            k_signing, string_to_sign.encode(), hashlib.sha256
        ).hexdigest()

        url = f"{self.endpoint}{path}?{params}&X-Amz-Signature={signature}"
        wire_headers = {
            name: value for name, value in header_pairs.items() if name != "host"
        }
        return url, wire_headers

    def build_access_url(
        self, *, storage_key: str, purpose: str, ttl_seconds: int
    ) -> str:
        url, _headers = self._sign(
            method="GET",
            key=storage_key,
            ttl_seconds=ttl_seconds,
            purpose=purpose,
        )
        return url

    async def put_bytes(
        self,
        storage_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> None:
        payload_hash = hashlib.sha256(data).hexdigest()
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        host = urllib.parse.urlsplit(self.endpoint).netloc
        key = storage_key.lstrip("/")
        path = urllib.parse.quote(f"/{self.bucket}/{key}")
        scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        headers = {
            "content-type": content_type,
            "host": host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
            **self._encryption_headers(),
        }
        canonical_headers = "".join(
            f"{name}:{headers[name]}\n" for name in sorted(headers)
        )
        signed_headers = ";".join(sorted(headers))
        params = (
            f"X-Amz-Algorithm=AWS4-HMAC-SHA256"
            f"&X-Amz-Credential={urllib.parse.quote(f'{self.access_key}/{scope}', safe='')}"
            f"&X-Amz-Date={amz_date}&X-Amz-Expires=300"
            f"&X-Amz-SignedHeaders={signed_headers}"
        )
        canonical_request = f"PUT\n{path}\n{params}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        string_to_sign = (
            f"AWS4-HMAC-SHA256\n{amz_date}\n{scope}\n"
            f"{hashlib.sha256(canonical_request.encode()).hexdigest()}"
        )

        def hmac_sha256(key: bytes, msg: str) -> bytes:
            return hmac.new(key, msg.encode(), hashlib.sha256).digest()

        k_date = hmac_sha256(("AWS4" + self.secret_key).encode(), date_stamp)
        k_region = hmac_sha256(k_date, self.region)
        k_service = hmac_sha256(k_region, "s3")
        k_signing = hmac_sha256(k_service, "aws4_request")
        signature = hmac.new(
            k_signing, string_to_sign.encode(), hashlib.sha256
        ).hexdigest()
        url = f"{self.endpoint}{path}?{params}&X-Amz-Signature={signature}"

        sent_headers = {
            name: value for name, value in headers.items() if name != "host"
        }
        async with httpx.AsyncClient() as client:
            resp = await client.put(url, content=data, headers=sent_headers)
            if resp.status_code not in (200, 201, 204):
                raise RuntimeError(f"S3 PUT failed: {resp.status_code} {resp.text}")

    async def read_bytes(self, storage_key: str) -> bytes:
        url, headers = self._sign(
            method="GET", key=storage_key, ttl_seconds=60, max_ttl_seconds=60
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.content

    async def delete(self, storage_key: str) -> None:
        url, headers = self._sign(
            method="DELETE", key=storage_key, ttl_seconds=60, max_ttl_seconds=60
        )
        async with httpx.AsyncClient() as client:
            resp = await client.delete(url, headers=headers)
            if resp.status_code not in (204, 200, 404):
                raise RuntimeError(f"S3 DELETE failed: {resp.status_code} {resp.text}")


def get_storage_provider() -> BaseStorageProvider:
    provider = StorageProvider(settings.storage_provider)
    if provider is StorageProvider.LOCAL:
        return LocalStorageProvider()
    if provider in (StorageProvider.S3, StorageProvider.MINIO):
        return S3StorageProvider()
    raise RuntimeError(f"Unsupported storage provider: {provider}")
