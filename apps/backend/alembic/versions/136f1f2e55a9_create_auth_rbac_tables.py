"""Create auth & RBAC tables (users, roles, user_sessions, user_roles).

Also creates ``audit_log`` + ``outbox`` (blueprint sections 10/8): the control
plane appends to these in every state-changing operation and the owning
modules are not part of this alembic chain, so they are materialized here with
the exact column set the projections consume.

Port of services/auth-service migrations 61a3de7a6070 + b2f8c91d3e45 into the
backend schema.  Key differences from the legacy port:

* Primary keys are UUID (v7 generated app-side, ``gen_random_uuid()`` as the
  Postgres server default) instead of integers.
* ``users.status`` is a VARCHAR(16) string column (PENDING/APPROVED/REJECTED)
  rather than a Postgres enum - consistent with how the rest of the control
  plane stores status enums (e.g. call_recordings.status).
* The legacy single-role ``users.role_id`` FK was NOT ported; membership is
  many-to-many only.
* The six system roles are seeded here so the single-MASTER_ADMIN unique index
  can be created against a known role id.

Revision ID: 136f1f2e55a9
Revises: 2a1c4f7e96b3
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "136f1f2e55a9"
down_revision: str | None = "2a1c4f7e96b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _seed_system_roles() -> None:
    """Insert the six system roles idempotently (name is unique)."""
    op.execute(
        """
        INSERT INTO roles (id, name, domain, description, is_system, created_at, updated_at)
        VALUES
          (gen_random_uuid(), 'MASTER_ADMIN',    'system',       'System administration, global settings, & full administrative privileges.',       true, clock_timestamp(), clock_timestamp()),
          (gen_random_uuid(), 'DEVOPS_IT',       'system',       'Technical infrastructure, telephony integrations & developer operations.',         true, clock_timestamp(), clock_timestamp()),
          (gen_random_uuid(), 'CAMPAIGN_MANAGER','operations',   'Dialer campaigns, lead routing, schedules & outbound lists.',                     true, clock_timestamp(), clock_timestamp()),
          (gen_random_uuid(), 'QA',              'quality',      'Quality assurance audits, call evaluation & compliance scoring.',                 true, clock_timestamp(), clock_timestamp()),
          (gen_random_uuid(), 'VIEWER',          'verification', 'Medicare verifiers, licensed call agents & customer verification.',               true, clock_timestamp(), clock_timestamp()),
          (gen_random_uuid(), 'REPORTING_USER',  'reporting',    'Call performance metrics, report generation & analytics access.',                 true, clock_timestamp(), clock_timestamp())
        ON CONFLICT (name) DO NOTHING
        """
    )


def _create_single_master_admin_index() -> None:
    """Partial unique index: at most one user may hold MASTER_ADMIN."""
    op.execute(
        """
        DO $$
        DECLARE master_id UUID;
        BEGIN
            SELECT id INTO master_id FROM roles WHERE name = 'MASTER_ADMIN' LIMIT 1;
            IF master_id IS NOT NULL THEN
                EXECUTE format(
                    'CREATE UNIQUE INDEX uq_single_master_admin ON user_roles (role_id) WHERE role_id = %L',
                    master_id
                );
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("domain", sa.String(length=32), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column(
            "is_system", sa.Boolean(), server_default=sa.text("false"), nullable=False
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_roles_name", "roles", ["name"], unique=True)

    op.create_table(
        "users",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("collaborator_pin", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=160), nullable=True),
        sa.Column("extension", sa.String(length=40), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'PENDING'"),
            nullable=False,
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "user_sessions",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_id", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_sessions_token_id", "user_sessions", ["token_id"])
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])

    _seed_system_roles()
    _create_single_master_admin_index()

    op.create_table(
        "audit_log",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_role", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=96), nullable=True),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("result", sa.String(length=32), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=256), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "outbox",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("aggregate_type", sa.String(length=64), nullable=True),
        sa.Column("aggregate_id", sa.String(length=64), nullable=True),
        sa.Column("channel", sa.String(length=96), nullable=True),
        sa.Column("event_type", sa.String(length=96), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "attempts", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("outbox")
    op.drop_table("audit_log")
    op.execute("DROP INDEX IF EXISTS uq_single_master_admin")
    op.drop_index("ix_user_roles_role_id", table_name="user_roles")
    op.drop_index("ix_user_roles_user_id", table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_index("ix_user_sessions_token_id", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_table("roles")
