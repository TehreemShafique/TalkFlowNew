"""BACKEND-8a: add vicidial_lead_id to leads.

Revision ID: b8c9d0e1f2a3
Revises: 0025051a7183
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b8c9d0e1f2a3"
down_revision: str | None = "0025051a7183"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS vicidial_lead_id VARCHAR(64);"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE leads DROP COLUMN IF EXISTS vicidial_lead_id;")
