"""RP-27: make audit_log append-only.

The audit trail is the compliance record for every PHI access (playback
grants, downloads, purges).  Rows may only be inserted - corrections are made
by appending a new row, never by rewriting history.

Revision ID: c5d6e7f8a9b0
Revises: i4j5k6l7m8n9
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c5d6e7f8a9b0"
down_revision: str | None = "i4j5k6l7m8n9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_log_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only (attempted %)', TG_OP
                USING ERRCODE = '42501';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_log_immutable
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW
        EXECUTE FUNCTION prevent_audit_log_mutation();
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_log_actor_ts "
        "ON audit_log (actor_id, ts DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_audit_log_resource "
        "ON audit_log (resource_type, resource_id, ts DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_audit_log_resource;")
    op.execute("DROP INDEX IF EXISTS ix_audit_log_actor_ts;")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_immutable ON audit_log;")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_log_mutation();")
