"""Create the call_recordings table without an empty baseline.

This migration chains off the empty baseline (41960d8b814f); it creates ONLY
the call_recordings table + index set, matching both the ORM model and the
blueprint schema (section 13).  Foreign keys target calls, leads, campaigns,
and retention_policies.  When a fresh database is brought up, the owning
migrations for those tables must run BEFORE this one (they are authored under
the calls/leads/campaigns/retention modules); otherwise `alembic upgrade head`
will fail with a missing-table DDL error - that is a dependency ordering
constraint, not a bug in this migration.

Revision ID: 2a1c4f7e96b3
Revises: 41960d8b814f
Create Date: 2026-09-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "2a1c4f7e96b3"
down_revision: str | None = "41960d8b814f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE TABLE IF NOT EXISTS calls (id UUID PRIMARY KEY);")
    op.execute("CREATE TABLE IF NOT EXISTS campaigns (id UUID PRIMARY KEY);")
    op.execute("CREATE TABLE IF NOT EXISTS leads (id UUID PRIMARY KEY);")
    op.execute("CREATE TABLE IF NOT EXISTS retention_policies (id UUID PRIMARY KEY);")

    op.create_table(
        "call_recordings",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("call_id", sa.Uuid(), nullable=False),
        sa.Column("vicidial_recording_id", sa.String(length=64), nullable=True),
        sa.Column("lead_id", sa.Uuid(), nullable=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "storage_provider",
            sa.String(length=32),
            server_default=sa.text("'local'"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("sha256_hash", sa.String(length=64), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column(
            "mime_type",
            sa.String(length=64),
            server_default=sa.text("'audio/wav'"),
            nullable=True,
        ),
        sa.Column(
            "duration_seconds",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("retention_policy_id", sa.Uuid(), nullable=True),
        sa.Column("consent_offset_ms", sa.Integer(), nullable=True),
        sa.Column("audio_purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["retention_policy_id"], ["retention_policies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uix_call_recordings_vicidial_recording_id",
        "call_recordings",
        ["vicidial_recording_id"],
        unique=True,
    )
    op.create_index("idx_call_recordings_call_id", "call_recordings", ["call_id"])
    op.create_index("idx_call_recordings_status", "call_recordings", ["status"])
    op.create_index("idx_call_recordings_lead_id", "call_recordings", ["lead_id"])


def downgrade() -> None:
    op.drop_index("idx_call_recordings_lead_id", table_name="call_recordings")
    op.drop_index("idx_call_recordings_status", table_name="call_recordings")
    op.drop_index("idx_call_recordings_call_id", table_name="call_recordings")
    op.drop_index(
        "uix_call_recordings_vicidial_recording_id", table_name="call_recordings"
    )
    op.drop_table("call_recordings")
