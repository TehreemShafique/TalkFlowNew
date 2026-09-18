"""Create the leads/suppression/export pipeline tables.

Owned modules (ADR-02):

* ``modules/leads`` -- extends the pre-existing ``leads`` stub (id / first_name
  / last_name / phone_normalized from e5f6a7b8c9d0) with the master-data and
  import columns the CSV wizard commits into, and creates the resumable
  ``lead_import_jobs`` registry (upload -> mapping -> validating -> commit).
* ``modules/suppression`` -- creates the ``suppression_entries`` DNC register
  with a partial unique index guaranteeing exactly one ACTIVE entry per number
  (``WHERE removed_at IS NULL``); removal is a soft delete that keeps the audit
  trail (ADR-06 dual write with VICIdial).
* ``modules/exports`` -- creates the ``exports`` job table (request -> queued ->
  processing -> ready), artifacts live in object storage, NOT in the DB.

The leads column additions use ``ADD COLUMN IF NOT EXISTS`` and the child
tables are created only when absent, so ``alembic upgrade head`` succeeds both
on a freshly created database and on one whose bare ``leads`` stub predates
this migration.  Schema order is FK-safe: leads is extended before
``lead_import_jobs.campaign_id`` / ``suppression_entries.added_by`` /
``exports.created_by`` reference it.

Revision ID: d6e7f8a9b0c1
Revises: b5c6d7e8f901
Create Date: 2026-09-18
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d6e7f8a9b0c1"
down_revision: str | None = "b5c6d7e8f901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSONB = postgresql.JSONB(astext_type=sa.Text())

_LEAD_COLUMNS: list[sa.Column] = [
    sa.Column("alt_phone", sa.String(length=32), nullable=True),
    sa.Column("phone_raw", sa.String(length=64), nullable=True),
    sa.Column("email", sa.String(length=254), nullable=True),
    sa.Column("state", sa.String(length=8), nullable=True),
    sa.Column("zip_code", sa.String(length=16), nullable=True),
    sa.Column("date_of_birth", sa.Date(), nullable=True),
    sa.Column("age", sa.Integer(), nullable=True),
    sa.Column("source", sa.String(length=120), nullable=True),
    sa.Column("source_batch_id", sa.String(length=64), nullable=True),
    sa.Column("campaign_id", sa.Uuid(), nullable=True),
    sa.Column(
        "status",
        sa.String(length=24),
        server_default=sa.text("'new'"),
        nullable=False,
    ),
    sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
    sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("assigned_to", sa.Uuid(), nullable=True),
    sa.Column(
        "suppressed",
        sa.Boolean(),
        server_default=sa.text("false"),
        nullable=False,
    ),
    sa.Column("suppression_reason", sa.String(length=32), nullable=True),
    sa.Column("custom_fields", _JSONB, nullable=True),
    sa.Column(
        "imported", sa.Boolean(), server_default=sa.text("false"), nullable=False
    ),
    sa.Column("imported_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("import_job_id", sa.Uuid(), nullable=True),
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
]


def _extend_leads() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("leads"):
        # Fresh databases get the full table; FK-bearing stubs already exist
        # in every real chain, so this branch is only for scratch safety.
        op.create_table(
            "leads",
            sa.Column(
                "id",
                sa.Uuid(),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("first_name", sa.String(length=120), nullable=True),
            sa.Column("last_name", sa.String(length=120), nullable=True),
            sa.Column("phone_normalized", sa.String(length=32), nullable=True),
            *[c.copy() for c in _LEAD_COLUMNS],
            sa.PrimaryKeyConstraint("id"),
        )
        return

    existing = {c["name"] for c in inspector.get_columns("leads")}
    for column in _LEAD_COLUMNS:
        if column.name not in existing:
            op.add_column("leads", column.copy())

    indexes = {ix["name"] for ix in inspector.get_indexes("leads")}
    if "ix_leads_phone_normalized" not in indexes:
        op.create_index("ix_leads_phone_normalized", "leads", ["phone_normalized"])
    if "ix_leads_status" not in indexes:
        op.create_index("ix_leads_status", "leads", ["status"])
    if "ix_leads_campaign_id" not in indexes:
        op.create_index("ix_leads_campaign_id", "leads", ["campaign_id"])


def _create_lead_import_jobs() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("lead_import_jobs"):
        return
    op.create_table(
        "lead_import_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=24),
            server_default=sa.text("'uploading'"),
            nullable=False,
        ),
        sa.Column("total_rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("imported_rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("duplicate_rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("suppressed_rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("invalid_rows", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("columns", _JSONB, nullable=True),
        sa.Column("mapping", _JSONB, nullable=True),
        sa.Column("rows", _JSONB, nullable=True),
        sa.Column("options", _JSONB, nullable=True),
        sa.Column("validation", _JSONB, nullable=True),
        sa.Column("error_report_key", sa.String(length=512), nullable=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_import_jobs_status", "lead_import_jobs", ["status"])
    op.create_index("ix_lead_import_jobs_created_by", "lead_import_jobs", ["created_by"])


def _create_suppression_entries() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("suppression_entries"):
        op.create_table(
            "suppression_entries",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("phone_normalized", sa.String(length=32), nullable=False),
            sa.Column("reason", sa.String(length=32), nullable=False),
            sa.Column("source", sa.String(length=120), nullable=True),
            sa.Column("added_by", sa.Uuid(), nullable=True),
            sa.Column(
                "added_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("clock_timestamp()"),
                nullable=False,
            ),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("evidence_reference", sa.String(length=255), nullable=True),
            sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("removed_by", sa.Uuid(), nullable=True),
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
            sa.ForeignKeyConstraint(["added_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["removed_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    indexes = {ix["name"] for ix in sa.inspect(op.get_bind()).get_indexes("suppression_entries")}
    if "ix_suppression_entries_phone" not in indexes:
        op.create_index(
            "ix_suppression_entries_phone", "suppression_entries", ["phone_normalized"]
        )
    if "ix_suppression_entries_reason" not in indexes:
        op.create_index("ix_suppression_entries_reason", "suppression_entries", ["reason"])
    if "uq_suppression_entries_active_phone" not in indexes:
        op.create_index(
            "uq_suppression_entries_active_phone",
            "suppression_entries",
            ["phone_normalized"],
            unique=True,
            postgresql_where=sa.text("removed_at IS NULL"),
        )


def _create_exports() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("exports"):
        return
    op.create_table(
        "exports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("report", sa.String(length=64), nullable=False),
        sa.Column(
            "format",
            sa.String(length=8),
            server_default=sa.text("'csv'"),
            nullable=False,
        ),
        sa.Column("filters", _JSONB, nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'queued'"),
            nullable=False,
        ),
        sa.Column("row_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("error", sa.String(length=512), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exports_report", "exports", ["report"])
    op.create_index("ix_exports_status", "exports", ["status"])


def upgrade() -> None:
    _extend_leads()
    _create_lead_import_jobs()
    _create_suppression_entries()
    _create_exports()


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS exports")
    op.execute("DROP TABLE IF EXISTS suppression_entries")
    op.execute("DROP TABLE IF EXISTS lead_import_jobs")
    # Mirror the reconciliation in upgrade(): the leads table predates this
    # migration (shared stub), so only the columns added here are removed.
    op.execute("DROP INDEX IF EXISTS ix_leads_campaign_id")
    op.execute("DROP INDEX IF EXISTS ix_leads_status")
    op.execute("DROP INDEX IF EXISTS ix_leads_phone_normalized")
    for column in reversed(_LEAD_COLUMNS):
        op.execute(f"ALTER TABLE leads DROP COLUMN IF EXISTS {column.name}")