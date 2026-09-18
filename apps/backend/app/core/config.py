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
    access_token_expire_minutes: int = 60 * 24
    token_blacklist_ttl: int = 3600
    role_cache_ttl: int = 300

    # Auth cookie settings. `cookie_secure` must be True in production (HTTPS).
    cookie_name: str = "access_token"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    # Seed the super-admin on first boot.
    seed_admin_email: str = "admin@phonova.io"
    seed_admin_password: str = "admin123"
    seed_admin_full_name: str = "Admin MPN"

    storage_provider: str = "local"
    storage_local_root: str = "./data/recordings"
    storage_public_base_url: str = "http://localhost:8001"
    storage_s3_endpoint: str = ""
    storage_s3_bucket: str = ""
    storage_s3_region: str = "us-east-1"
    storage_s3_access_key: str = ""
    storage_s3_secret_key: str = ""

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

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