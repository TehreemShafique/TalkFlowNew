"""Create scripts, script_versions, script_activations tables and campaign FKs.

Revision ID: a1b2c3d4e5f6
Revises: d6e7f8a9b0c1
Create Date: 2026-09-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "d6e7f8a9b0c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    # 1. Create scripts table
    op.create_table(
        "scripts",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "language",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'en-US'"),
        ),
        sa.Column(
            "current_version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("active_version_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
    )
    op.create_index("ix_scripts_status", "scripts", ["status"])
    op.create_index("ix_scripts_name", "scripts", ["name"])

    # 2. Create script_versions table
    op.create_table(
        "script_versions",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "script_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("scripts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "entry_node_id",
            sa.String(length=64),
            nullable=False,
            server_default=sa.text("'node-1'"),
        ),
        sa.Column(
            "nodes",
            _JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("rule_set_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("change_note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_by",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.Column(
            "submitted_by",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "approved_by",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_reason", sa.String(length=500), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "script_id", "version", name="uq_script_versions_script_id_version"
        ),
    )
    op.create_index("ix_script_versions_script_id", "script_versions", ["script_id"])
    op.create_index("ix_script_versions_status", "script_versions", ["status"])

    # 3. Add FK from scripts.active_version_id to script_versions.id
    op.create_foreign_key(
        "fk_scripts_active_version_id",
        "scripts",
        "script_versions",
        ["active_version_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )

    # 4. Create script_activations table
    op.create_table(
        "script_activations",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "script_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("scripts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "script_version_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("script_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "activated_by",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "activated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
    )
    op.create_index(
        "ix_script_activations_script_id", "script_activations", ["script_id"]
    )
    op.create_index(
        "ix_script_activations_campaign_id", "script_activations", ["campaign_id"]
    )

    # 5. Add FKs from campaigns to scripts and script_versions
    op.create_foreign_key(
        "fk_campaigns_script_id",
        "campaigns",
        "scripts",
        ["script_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_campaigns_active_script_version_id",
        "campaigns",
        "script_versions",
        ["active_script_version_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_campaigns_active_script_version_id", "campaigns", type_="foreignkey"
    )
    op.drop_constraint("fk_campaigns_script_id", "campaigns", type_="foreignkey")
    op.drop_table("script_activations")
    op.drop_constraint("fk_scripts_active_version_id", "scripts", type_="foreignkey")
    op.drop_table("script_versions")
    op.drop_table("scripts")
