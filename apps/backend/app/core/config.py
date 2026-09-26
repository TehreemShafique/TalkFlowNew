"""Application settings for the TalkFlow control plane."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "TalkFlow Control Plane"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://talkflow:admin@localhost:5432/talkflow"
    redis_url: str = "redis://localhost:6379/1"

    # Kafka (STEP 15 ingest consumer worker).  ``kafka_call_ingest_group``
    # follows the talkflow_backend.md convention ``talkflow-<worker>-v1``.
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_call_ingest_group: str = "talkflow-call-ingest-v1"

    jwt_algorithm: str = "HS256"
    jwt_access_secret: str = "change-me-in-production"
    jwt_access_ttl_minutes: int = 15
    download_token_ttl_minutes: int = 15
    playback_url_ttl_seconds: int = 300

    # Access-token JWT (port of services/auth-service/app/core/config.py).
    secret_key: str = "change-me-in-production-0123456789abcdef"
    algorithm: str = "HS256"
    # Blueprint 11.4: the access JWT is short-lived and is always paired with a
    # rotating opaque refresh token; it must never be the only credential.
    access_token_expire_minutes: int = 15
    token_blacklist_ttl: int = 3600
    role_cache_ttl: int = 300

    # Refresh tokens (blueprint 11.4 / 13.2): opaque, stored hashed, rotated on
    # every use with family-wide reuse detection.
    refresh_token_ttl_days: int = 7

    # Auth cookie settings. `cookie_secure` must be True in production (HTTPS).
    cookie_name: str = "access_token"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cookie_refresh_name: str = "refresh_token"

    # Seed the super-admin on first boot.
    seed_admin_email: str = "admin@phonova.io"
    seed_admin_password: str = "e4GLTRrHlBFyFy47"
    seed_admin_full_name: str = "Admin MPN"

    storage_provider: str = "local"
    storage_local_root: str = "./data/recordings"
    storage_public_base_url: str = "http://localhost:8001"
    storage_s3_endpoint: str = ""
    storage_s3_bucket: str = ""
    storage_s3_region: str = "us-east-1"
    storage_s3_access_key: str = ""
    storage_s3_secret_key: str = ""
    storage_s3_server_side_encryption: str = "AES256"
    storage_s3_kms_key_id: str = ""
    storage_presign_max_ttl_seconds: int = 60 * 60 * 24 * 7
    database_require_tls: bool = True
    enforce_https: bool = True
    tls_min_version: str = "TLSv1.3"
    require_tls_1_3: bool = True

    # Starlette matches the browser's ``Origin`` header as an exact string, and
    # ``localhost`` resolves to IPv6 ``::1`` first on Windows/Chrome.  Every
    # loopback spelling the dashboard can be opened on must be listed or the
    # browser discards the response and ``fetch`` rejects with
    # "TypeError: Failed to fetch" (which is indistinguishable from the API
    # being down).  The bracketed form is what the browser actually sends.
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://[::1]:3000",
    ]

    # VICIdial Non-Agent API (B3-1).  The API user must have User level >= 8.
    # ``vicidial_url`` is the full ``non_agent_api.php`` endpoint.
    vicidial_url: str = "http://localhost/vicidial/non_agent_api.php"
    vicidial_user: str = ""
    vicidial_pass: str = ""
    vicidial_source: str = "talkflow"
    vicidial_default_campaign_id: str = "TEST_CAMP"
    vicidial_default_list_id: str = "1001"

    # BACKEND-8a telephony edge.  Shared secret VICIdial must echo back in the
    # ``X-TalkFlow-Telephony-Token`` header on every start-call / dispo-call
    # webhook.  AMI credentials must be a restricted manager user (read-only
    # events) - never the full watchroot default.
    telephony_webhook_token: str = ""
    asterisk_ami_host: str = "localhost"
    asterisk_ami_port: int = 5038
    asterisk_ami_user: str = ""
    asterisk_ami_pass: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    # If running outside docker container, replace hostname 'postgres' with 'localhost'
    if "@postgres:" in s.database_url:
        s.database_url = s.database_url.replace("@postgres:", "@localhost:")
    if "@redis:" in s.redis_url:
        s.redis_url = s.redis_url.replace("@redis:", "@localhost:")
    return s


settings = get_settings()
