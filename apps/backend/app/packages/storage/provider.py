"""Storage providers - local disk and S3/MinIO.

Local provider returns **short-lived signed playback/download grants** (not raw
paths - Rule R7); S3/MinIO returns **SigV4 presigned URLs** hand-rolled so the
control plane has no botocore dependency (pyproject.toml has none).
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
from app.packages.contracts.enums import StorageProvider

StorageResult = str  # presigned URL or signed grant token payload


class BaseStorageProvider(ABC):
    @abstractmethod
    def build_access_url(
        self, *, storage_key: str, purpose: str, ttl_seconds: int
    ) -> str:
        """Return an externally usable URL/grant for reading the object."""

    @abstractmethod
    async def put_bytes(
        self, storage_key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        """Persist raw bytes (CSV error reports, export artifacts)."""

    @abstractmethod
    async def read_bytes(self, storage_key: str) -> bytes:
        """Read the full object back (download path)."""

    @abstractmethod
    async def delete(self, storage_key: str) -> None:
        """Best-effort removal of the physical object."""


class LocalStorageProvider(BaseStorageProvider):
    def __init__(self, root: Path | None = None, public_base: str | None = None) -> None:
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
        token, _ = create_signed_grant(
            storage_key, purpose=purpose, ttl_seconds=ttl_seconds
        )
        return f"{self.public_base}/api/v1/recordings/stream/{urllib.parse.quote(token, safe='')}"

    async def put_bytes(
        self, storage_key: str, data: bytes, content_type: str = "application/octet-stream"
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
    """SigV4 presigned URLs + signed DELETE via httpx (no botocore)."""

    def __init__(self) -> None:
        self.endpoint = settings.storage_s3_endpoint.rstrip("/")
        self.bucket = settings.storage_s3_bucket
        self.region = settings.storage_s3_region
        self.access_key = settings.storage_s3_access_key
        self.secret_key = settings.storage_s3_secret_key
        if not (self.endpoint and self.bucket and self.access_key and self.secret_key):
            raise RuntimeError("S3 storage selected but S3 settings are not configured")

    def _sign(self, *, method: str, key: str, ttl_seconds: int) -> str:
        host = urllib.parse.urlsplit(self.endpoint).netloc
        path = urllib.parse.quote(f"/{self.bucket}/{key.lstrip('/')}")
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        exp = int(ttl_seconds)
        scope = f"{date_stamp}/{self.region}/s3/aws4_request"

        payload_hash = hashlib.sha256(b"").hexdigest()
        canonical_headers = (
            f"host:{host}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{amz_date}\n"
        )
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        params = (
            f"X-Amz-Algorithm=AWS4-HMAC-SHA256"
            f"&X-Amz-Credential={urllib.parse.quote(f'{self.access_key}/{scope}', safe='')}"
            f"&X-Amz-Date={amz_date}&X-Amz-Expires={exp}&X-Amz-SignedHeaders={signed_headers}"
        )
        canonical_request = (
            f"{method}\n{path}\n{params}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        )
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
        signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()

        return (
            f"{self.endpoint}/{self.bucket}/{urllib.parse.quote(key.lstrip('/'))}"
            f"?{params}&X-Amz-Signature={signature}"
        )

    def build_access_url(
        self, *, storage_key: str, purpose: str, ttl_seconds: int
    ) -> str:
        return self._sign(method="GET", key=storage_key, ttl_seconds=ttl_seconds)

    async def put_bytes(
        self, storage_key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        payload_hash = hashlib.sha256(data).hexdigest()
        now = datetime.now(UTC)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        host = urllib.parse.urlsplit(self.endpoint).netloc
        key = storage_key.lstrip("/")
        path = urllib.parse.quote(f"/{self.bucket}/{key}")
        scope = f"{date_stamp}/{self.region}/s3/aws4_request"
        canonical_headers = (
            f"content-type:{content_type}\n"
            f"host:{host}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{amz_date}\n"
        )
        signed_headers = "content-type;host;x-amz-content-sha256;x-amz-date"
        params = (
            f"X-Amz-Algorithm=AWS4-HMAC-SHA256"
            f"&X-Amz-Credential={urllib.parse.quote(f'{self.access_key}/{scope}', safe='')}"
            f"&X-Amz-Date={amz_date}&X-Amz-Expires=300"
            f"&X-Amz-SignedHeaders={signed_headers}"
        )
        canonical_request = (
            f"PUT\n{path}\n{params}\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        )
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
        signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
        url = f"{self.endpoint}/{self.bucket}/{path}?{params}&X-Amz-Signature={signature}"

        async with httpx.AsyncClient() as client:
            resp = await client.put(
                url,
                content=data,
                headers={
                    "content-type": content_type,
                    "x-amz-content-sha256": payload_hash,
                    "x-amz-date": amz_date,
                },
            )
            if resp.status_code not in (200, 201, 204):
                raise RuntimeError(f"S3 PUT failed: {resp.status_code} {resp.text}")

    async def read_bytes(self, storage_key: str) -> bytes:
        url = self._sign(method="GET", key=storage_key, ttl_seconds=60)
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.content

    async def delete(self, storage_key: str) -> None:
        url = self._sign(method="DELETE", key=storage_key, ttl_seconds=60)
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                url,
                headers={
                    "x-amz-content-sha256": hashlib.sha256(b"").hexdigest(),
                    "x-amz-date": datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
                },
            )
            if resp.status_code not in (204, 200, 404):
                raise RuntimeError(f"S3 DELETE failed: {resp.status_code} {resp.text}")


def get_storage_provider() -> BaseStorageProvider:
    provider = StorageProvider(settings.storage_provider)
    if provider is StorageProvider.LOCAL:
        return LocalStorageProvider()
    if provider in (StorageProvider.S3, StorageProvider.MINIO):
        return S3StorageProvider()
    raise RuntimeError(f"Unsupported storage provider: {provider}")