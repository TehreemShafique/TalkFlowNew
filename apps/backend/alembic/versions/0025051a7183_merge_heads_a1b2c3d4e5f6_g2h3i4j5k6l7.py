"""merge heads a1b2c3d4e5f6 g2h3i4j5k6l7

Revision ID: 0025051a7183
Revises: a1b2c3d4e5f6, g2h3i4j5k6l7
Create Date: 2026-09-22 00:05:19.298212

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0025051a7183"
# g2h3i4j5k6l7 listed first on purpose: e7f8a9b0c1d2 FKs to lead_import_jobs /
# suppression_entries which d6e7f8a9b0c1 (a1b2c3d4e5f6's parent) creates, and
# alembic upgrades the first parent's chain before walking the next.
down_revision: str | Sequence[str] | None = ("g2h3i4j5k6l7", "a1b2c3d4e5f6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
