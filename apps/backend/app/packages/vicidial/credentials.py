"""VICIdial Non-Agent API credentials (B3-1)."""

from __future__ import annotations

from pydantic import BaseModel

from app.core.config import settings


class VicidialCredentials(BaseModel):
    """Credentials and addressing defaults for the VICIdial Non-Agent API."""

    url: str = "http://localhost/vicidial/non_agent_api.php"
    user: str = ""
    password: str = ""
    source: str = "talkflow"
    default_campaign_id: str = "TEST_CAMP"
    default_list_id: str = "1001"


def get_vicidial_credentials() -> VicidialCredentials:
    """Build the configured credentials from application settings."""
    return VicidialCredentials(
        url=settings.vicidial_url,
        user=settings.vicidial_user,
        password=settings.vicidial_pass,
        source=settings.vicidial_source,
        default_campaign_id=settings.vicidial_default_campaign_id,
        default_list_id=settings.vicidial_default_list_id,
    )
