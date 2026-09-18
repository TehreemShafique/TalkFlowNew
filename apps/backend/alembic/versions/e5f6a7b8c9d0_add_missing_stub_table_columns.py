"""Add missing stub table columns for calls, leads, and campaigns tables.

Revision ID: e5f6a7b8c9d0
Revises: 8e9f0a1b2c3d
Create Date: 2026-09-17
"""
from collections.abc import Sequence

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "8e9f0a1b2c3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    # calls columns
    op.execute("ALTER TABLE calls ADD COLUMN IF NOT EXISTS started_at TIMESTAMP WITH TIME ZONE;")
    op.execute("ALTER TABLE calls ADD COLUMN IF NOT EXISTS duration_seconds INTEGER;")
    op.execute("ALTER TABLE calls ADD COLUMN IF NOT EXISTS disposition VARCHAR(32);")
    op.execute("ALTER TABLE calls ADD COLUMN IF NOT EXISTS qualification_status VARCHAR(32);")
    op.execute("ALTER TABLE calls ADD COLUMN IF NOT EXISTS disqualification_reason VARCHAR(64);")
    op.execute("ALTER TABLE calls ADD COLUMN IF NOT EXISTS lead_id UUID;")
    op.execute("ALTER TABLE calls ADD COLUMN IF NOT EXISTS campaign_id UUID;")
    op.execute("ALTER TABLE calls ADD COLUMN IF NOT EXISTS verifier_id UUID;")

    # leads columns
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS first_name VARCHAR(120);")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_name VARCHAR(120);")
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS phone_normalized VARCHAR(32);")

    # campaigns columns
    op.execute("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS name VARCHAR(160);")

def downgrade() -> None:
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS name;")
    op.execute("ALTER TABLE leads DROP COLUMN IF EXISTS phone_normalized;")
    op.execute("ALTER TABLE leads DROP COLUMN IF EXISTS last_name;")
    op.execute("ALTER TABLE leads DROP COLUMN IF EXISTS first_name;")
    op.execute("ALTER TABLE calls DROP COLUMN IF EXISTS verifier_id;")
    op.execute("ALTER TABLE calls DROP COLUMN IF EXISTS campaign_id;")
    op.execute("ALTER TABLE calls DROP COLUMN IF EXISTS lead_id;")
    op.execute("ALTER TABLE calls DROP COLUMN IF EXISTS disqualification_reason;")
    op.execute("ALTER TABLE calls DROP COLUMN IF EXISTS qualification_status;")
    op.execute("ALTER TABLE calls DROP COLUMN IF EXISTS disposition;")
    op.execute("ALTER TABLE calls DROP COLUMN IF EXISTS duration_seconds;")
    op.execute("ALTER TABLE calls DROP COLUMN IF EXISTS started_at;")
