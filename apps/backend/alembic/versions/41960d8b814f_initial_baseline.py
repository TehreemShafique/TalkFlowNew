"""initial baseline migration

Revision ID: 41960d8b814f
Revises:
Create Date: 2026-09-16 00:00:00.000000

"""

from collections.abc import Sequence

revision: str = "41960d8b814f"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
