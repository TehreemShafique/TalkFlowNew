"""US phone number normalization to E.164 ("18505554586").

Shared by the leads and suppression modules so an imported lead and a DNC
entry can never disagree about what a number "is".  Kept provider-agnostic
(zero I/O) so the exact same function decides E.164 validity in policies
(pure), repositories (SQL constraints) and the schedulers.
"""

from __future__ import annotations

import re

_NON_DIGITS = re.compile(r"\D+")


def normalize_us_phone(raw: str | None) -> str | None:
    """Normalize a phone to 11-digit E.164 (no leading ``+``).

    Accepted forms: 10-digit NANP, 11 digits with a leading 1, an explicit
    ``+1`` prefix, or any mix of spaces/dashes/parens around those digits.
    Returns ``None`` when the digits do not form a valid NANP number.
    """
    if not raw:
        return None
    text = raw.strip()
    text = text.removeprefix("+")
    digits = _NON_DIGITS.sub("", text)
    if len(digits) == 10:
        return "1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return digits
    return None