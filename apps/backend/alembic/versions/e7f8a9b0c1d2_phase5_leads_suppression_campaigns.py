"""Phase 5: Leads external_key, lead_import_rows staging, suppression channels & soft removal, campaign caller_ids & dialer fields.

Revision ID: e7f8a9b0c1d2
Revises: c4d5e6f7a8b9
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e7f8a9b0c1d2"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    # 1. Add external_key to leads table
    op.execute("ALTER TABLE leads ADD COLUMN IF NOT EXISTS external_key VARCHAR(20);")
    op.execute(
        """
        UPDATE leads
        SET external_key = LOWER(SUBSTRING(MD5(id::text), 1, 16))
        WHERE external_key IS NULL;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_leads_external_key
        ON leads (external_key);
        """
    )

    # 2. Create lead_import_rows staging table (Step 28)
    op.create_table(
        "lead_import_rows",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "job_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("lead_import_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("raw_data", _JSONB, nullable=False),
        sa.Column("normalized_data", _JSONB, nullable=True),
        sa.Column(
            "verdict",
            sa.String(length=24),
            nullable=False,
            server_default=sa.text("'valid'"),
        ),
        sa.Column("error_reason", sa.String(length=64), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
    )
    op.create_index("ix_lead_import_rows_job_id", "lead_import_rows", ["job_id"])
    op.create_index("ix_lead_import_rows_verdict", "lead_import_rows", ["verdict"])

    # 3. Add suppression entries channels, SLA clock, and vicidial columns (Step 29)
    op.execute(
        "ALTER TABLE suppression_entries ADD COLUMN IF NOT EXISTS channel VARCHAR(32);"
    )
    op.execute(
        "ALTER TABLE suppression_entries ADD COLUMN IF NOT EXISTS received_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp();"
    )
    op.execute(
        "ALTER TABLE suppression_entries ADD COLUMN IF NOT EXISTS honored_at TIMESTAMP WITH TIME ZONE;"
    )
    op.execute(
        "ALTER TABLE suppression_entries ADD COLUMN IF NOT EXISTS vicidial_synced_at TIMESTAMP WITH TIME ZONE;"
    )

    # 4. Add campaigns caller_ids, vicidial_campaign_id, campaign_vicidial_lists columns (Step 30)
    op.execute(
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS vicidial_campaign_id VARCHAR(64);"
    )
    op.execute(
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS campaign_vicidial_lists JSONB DEFAULT '[]'::jsonb;"
    )
    op.execute(
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS caller_ids JSONB DEFAULT '[]'::jsonb;"
    )
    op.execute("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS verifier_group_id UUID;")


def downgrade() -> None:
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS verifier_group_id;")
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS caller_ids;")
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS campaign_vicidial_lists;")
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS vicidial_campaign_id;")
    op.execute(
        "ALTER TABLE suppression_entries DROP COLUMN IF EXISTS vicidial_synced_at;"
    )
    op.execute("ALTER TABLE suppression_entries DROP COLUMN IF EXISTS honored_at;")
    op.execute("ALTER TABLE suppression_entries DROP COLUMN IF EXISTS received_at;")
    op.execute("ALTER TABLE suppression_entries DROP COLUMN IF EXISTS channel;")
    op.drop_table("lead_import_rows")
    op.execute("DROP INDEX IF EXISTS uq_leads_external_key;")
    op.execute("ALTER TABLE leads DROP COLUMN IF EXISTS external_key;")
