"""VICIdial Non-Agent API integration (B3-1, BACKEND-8a)."""

from app.packages.vicidial.client import VicidialClient
from app.packages.vicidial.credentials import (
    VicidialCredentials,
    get_vicidial_credentials,
)
from app.packages.vicidial.mapper import (
    all_outcomes,
    map_outcome_safe,
    map_talkflow_to_vicidial_status,
)
from app.packages.vicidial.methods import add_dnc, add_lead, update_lead_status
from app.packages.vicidial.parser import (
    VicidialResponse,
    extract_added_lead_id,
    parse_vicidial_response,
)

__all__ = [
    "VicidialClient",
    "VicidialCredentials",
    "VicidialResponse",
    "add_dnc",
    "add_lead",
    "all_outcomes",
    "extract_added_lead_id",
    "get_vicidial_credentials",
    "map_outcome_safe",
    "map_talkflow_to_vicidial_status",
    "parse_vicidial_response",
    "update_lead_status",
]
