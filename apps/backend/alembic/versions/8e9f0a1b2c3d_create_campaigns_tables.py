"""Create campaigns + campaign_vicidial_lists.

The campaigns module owns the campaign registry and its VICIdial list mapping
(blueprint section 13, "Campaigns and VICIdial mapping"):

* ``campaigns`` - governance record: lifecycle status, bound script / rule set /
  compliance profile and the VICIdial routing identifiers.  The script / rule
  set / compliance columns are intentionally plain UUID columns with **no**
  SQL foreign key: those owning modules are not built yet and their tables do
  not exist in this migration chain.  The start guard checks their presence in
  ``campaigns/policies.py`` and will gain real lookups once those migrations
  land.
* ``campaign_vicidial_lists`` - one row per mapped VICIdial ``list_id``
  (FK -> campaigns, ON DELETE CASCADE).

Schema order is FK-safe: campaigns is created before its child mapping table.

Reconciliation: a minimal ``campaigns`` stub (id, name) may already exist from
the shared read-only projection in ``packages/db/models.py`` having been
``create_all``-ed against a developer database.  This migration therefore
creates the table when absent and adds only the missing columns when a stub is
present, so ``alembic upgrade head`` succeeds from either starting state.

Revision ID: 8e9f0a1b2c3d
Revises: 7f3a9c2b4d80
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "8e9f0a1b2c3d"
down_revision: str | None = "7f3a9c2b4d80"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSONB = postgresql.JSONB(astext_type=sa.Text())

# Columns added by this migration (id + name are assumed to already exist when
# reconciling a stub table).
_ADDED_COLUMNS: list[sa.Column] = [
    sa.Column(
        "status",
        sa.String(length=16),
        server_default=sa.text("'draft'"),
        nullable=False,
    ),
    sa.Column("script_id", sa.Uuid(), nullable=True),
    sa.Column("active_script_version_id", sa.Uuid(), nullable=True),
    sa.Column("rule_set_version_id", sa.Uuid(), nullable=True),
    sa.Column("compliance_profile_id", sa.Uuid(), nullable=True),
    sa.Column("vicidial_campaign_id", sa.String(length=64), nullable=True),
    sa.Column("closer_in_group", sa.String(length=120), nullable=True),
    sa.Column(
        "timezone",
        sa.String(length=64),
        server_default=sa.text("'America/New_York'"),
        nullable=False,
    ),
    sa.Column("dialing", _JSONB, nullable=True),
    sa.Column("transfer", _JSONB, nullable=True),
    sa.Column("recording", _JSONB, nullable=True),
    sa.Column("retention", _JSONB, nullable=True),
    sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
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

_CHILD_TABLE = "campaign_vicidial_lists"


def _create_campaigns() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("campaigns"):
        op.create_table(
            "campaigns",
            sa.Column(
                "id",
                sa.Uuid(),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("name", sa.String(length=160), nullable=False),
            *[c.copy() for c in _ADDED_COLUMNS],
            sa.PrimaryKeyConstraint("id"),
        )
    else:
        existing = {c["name"] for c in inspector.get_columns("campaigns")}
        for column in _ADDED_COLUMNS:
            if column.name not in existing:
                op.add_column("campaigns", column.copy())

    indexes = {ix["name"] for ix in sa.inspect(op.get_bind()).get_indexes("campaigns")}
    if "ix_campaigns_status" not in indexes:
        op.create_index("ix_campaigns_status", "campaigns", ["status"])


def _create_child_table() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(_CHILD_TABLE):
        op.create_table(
            _CHILD_TABLE,
            sa.Column(
                "id",
                sa.Uuid(),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("campaign_id", sa.Uuid(), nullable=False),
            sa.Column("vicidial_list_id", sa.String(length=64), nullable=False),
            sa.Column(
                "active", sa.Boolean(), server_default=sa.text("true"), nullable=False
            ),
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
            sa.ForeignKeyConstraint(
                ["campaign_id"], ["campaigns.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "campaign_id", "vicidial_list_id", name="uq_campaign_vicidial_lists"
            ),
        )
    indexes = {ix["name"] for ix in sa.inspect(op.get_bind()).get_indexes(_CHILD_TABLE)}
    if "ix_campaign_vicidial_lists_campaign_id" not in indexes:
        op.create_index(
            "ix_campaign_vicidial_lists_campaign_id", _CHILD_TABLE, ["campaign_id"]
        )


def upgrade() -> None:
    _create_campaigns()
    _create_child_table()


def downgrade() -> None:
    # Mirror the reconciliation in upgrade(): the child table is always ours to
    # drop, but ``campaigns`` may predate this migration (shared stub) and is
    # referenced by ``call_recordings``, so we only remove the columns we added.
    op.execute(f"DROP TABLE IF EXISTS {_CHILD_TABLE}")
    op.execute("DROP INDEX IF EXISTS ix_campaigns_status")
    for column in _ADDED_COLUMNS:
        op.execute(f"ALTER TABLE campaigns DROP COLUMN IF EXISTS {column.name}")
