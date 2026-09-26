"""merge heads b8c9d0e1f2a3 j5k6l7m8n9o0

The telephony migration ``b8c9d0e1f2a3`` branched off the ``0025051a7183``
merge point and was never merged back, so the history carried two heads.  The
refresh-token migration ``j5k6l7m8n9o0`` then added a second.  This revision
closes both, restoring the single linear head the drift gate and
``alembic upgrade head`` expect.

Revision ID: k6l7m8n9o0p1
Revises: j5k6l7m8n9o0, b8c9d0e1f2a3
Create Date: 2026-09-26
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "k6l7m8n9o0p1"
# j5k6l7m8n9o0 listed first: it sits at the end of the long main chain
# (h3i4j5k6l7m8 -> i4j5k6l7m8n9 -> c5d6e7f8a9b0), and alembic walks a parent's
# chain before the next parent, matching the ordering rationale in
# 0025051a7183.  Both sides are additive and idempotent, so this is a
# bookkeeping-only merge.
down_revision: str | Sequence[str] | None = ("j5k6l7m8n9o0", "b8c9d0e1f2a3")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
