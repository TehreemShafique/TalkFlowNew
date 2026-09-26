"""VICIdial text response parser (B3-1)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class VicidialResponse:
    """Parsed outcome of a VICIdial Non-Agent API text response.

    VICIdial answers with HTTP 200 for both success and failure, encoding the
    result in line prefixes (``SUCCESS:``, ``ERROR:``, ``NOTICE:``).
    """

    success: bool
    data: list[str] | None = None
    notices: list[str] = field(default_factory=list)
    error: str | None = None
    raw_body: str = ""


def parse_vicidial_response(body: str) -> VicidialResponse:
    """Parse a VICIdial text response into a structured ``VicidialResponse``."""
    success = False
    data: list[str] | None = None
    notices: list[str] = []
    error: str | None = None

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line.startswith("ERROR:"):
            success = False
            error = line[len("ERROR:") :].strip()
        elif line.startswith("NOTICE:"):
            notices.append(line[len("NOTICE:") :].strip())
        elif line.startswith("SUCCESS:"):
            success = True
            data = [part.strip() for part in line[len("SUCCESS:") :].split("|")]
        elif line.startswith("VERSION:"):
            success = True
            data = [part.strip() for part in line[len("VERSION:") :].split("|")]

    return VicidialResponse(
        success=success,
        data=data,
        notices=notices,
        error=error,
        raw_body=body,
    )


_ADDED_LEAD_ID_RE = re.compile(r"LEAD HAS BEEN ADDED\s*-\s*(\d+)")


def extract_added_lead_id(response: VicidialResponse) -> str | None:
    """Extract the numeric VICIdial lead id from a successful ``add_lead``.

    The response data is pipe-split (e.g. ``add_lead LEAD HAS BEEN ADDED -
    10001|13125550000|...``) and the first cell carries the new ``lead_id``.
    Returns ``None`` for responses that did not add a lead.
    """
    if not response.success or not response.data:
        return None
    for part in response.data:
        match = _ADDED_LEAD_ID_RE.search(part)
        if match:
            return match.group(1)
    return None
