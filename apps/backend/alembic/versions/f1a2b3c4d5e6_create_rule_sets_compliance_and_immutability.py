"""Phase 4: Rule sets, compliance profiles, immutability trigger, and activation constraints.

Revision ID: c4d5e6f7a8b9
Revises: b5c6d7e8f901
Create Date: 2026-09-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: str | None = "b5c6d7e8f901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    # 1. Create rule_sets table
    op.create_table(
        "rule_sets",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
    op.create_index("ix_rule_sets_name", "rule_sets", ["name"])

    # 2. Create rule_set_versions table
    op.create_table(
        "rule_set_versions",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "rule_set_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("rule_sets.id", ondelete="CASCADE"),
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
            "rules",
            _JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "disqualification_reasons",
            _JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
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
        sa.UniqueConstraint(
            "rule_set_id", "version", name="uq_rule_set_versions_rule_set_id_version"
        ),
    )
    op.create_index(
        "ix_rule_set_versions_rule_set_id", "rule_set_versions", ["rule_set_id"]
    )

    # 3. FK from rule_sets.active_version_id -> rule_set_versions.id
    op.create_foreign_key(
        "fk_rule_sets_active_version_id",
        "rule_sets",
        "rule_set_versions",
        ["active_version_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )

    # 4. Create compliance_profiles table
    op.create_table(
        "compliance_profiles",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "jurisdiction",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'US-MEDICARE'"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
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

    # 5. Create compliance_rules table
    op.create_table(
        "compliance_rules",
        sa.Column(
            "id",
            sa.Uuid(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "profile_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("compliance_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule_key", sa.String(length=64), nullable=False),
        sa.Column(
            "mode",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'enforce'"),
        ),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column(
            "updated_by",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("clock_timestamp()"),
        ),
        sa.UniqueConstraint(
            "profile_id", "rule_key", name="uq_compliance_rules_profile_id_rule_key"
        ),
    )

    # 6. Add trigger to prevent updates on non-draft script_versions
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_script_version_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.status <> 'draft' THEN
                RAISE EXCEPTION 'script_versions records are immutable when status is not draft (status=%)', OLD.status
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_prevent_approved_script_version_mutation
        BEFORE UPDATE ON script_versions
        FOR EACH ROW
        EXECUTE FUNCTION prevent_script_version_mutation();
        """
    )

    # 7. Add partial unique index for single active script activation per campaign
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_script_activations_campaign_active
        ON script_activations (campaign_id)
        WHERE campaign_id IS NOT NULL;
        """
    )

    # 8. Add FKs from campaigns to rule_set_versions and compliance_profiles
    op.execute(
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS rule_set_version_id UUID;"
    )
    op.execute(
        "ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS compliance_profile_id UUID;"
    )
    op.create_foreign_key(
        "fk_campaigns_rule_set_version_id",
        "campaigns",
        "rule_set_versions",
        ["rule_set_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_campaigns_compliance_profile_id",
        "campaigns",
        "compliance_profiles",
        ["compliance_profile_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_campaigns_compliance_profile_id", "campaigns", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_campaigns_rule_set_version_id", "campaigns", type_="foreignkey"
    )
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS compliance_profile_id;")
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS rule_set_version_id;")
    op.execute("DROP INDEX IF EXISTS uq_script_activations_campaign_active;")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_prevent_approved_script_version_mutation ON script_versions;"
    )
    op.execute("DROP FUNCTION IF EXISTS prevent_script_version_mutation;")
    op.drop_table("compliance_rules")
    op.drop_table("compliance_profiles")
    op.drop_constraint(
        "fk_rule_sets_active_version_id", "rule_sets", type_="foreignkey"
    )
    op.drop_table("rule_set_versions")
    op.drop_table("rule_sets")
