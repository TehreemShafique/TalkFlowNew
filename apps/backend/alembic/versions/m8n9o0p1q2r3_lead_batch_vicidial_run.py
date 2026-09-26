"""Add VICIdial run-control columns to lead_import_jobs.

The dashboard's lead-list registry toggles each imported list into the VICIdial
hopper.  The resulting state (assigned list id, run count, execution status,
active flag, start/stop timestamps) is persisted here rather than in the
browser so run counts survive a cache clear and every operator sees the same
list state.

Existing rows default to an idle, never-run list (``vicidial_list_id`` NULL
means "not yet mapped to a dialer list").

Revision ID: m8n9o0p1q2r3
Revises: l7m8n9o0p1q2
Create Date: 2026-09-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "m8n9o0p1q2r3"
down_revision: str | None = "l7m8n9o0p1q2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE lead_import_jobs ADD COLUMN IF NOT EXISTS "
        "vicidial_list_id VARCHAR(64)"
    )
    op.execute(
        "ALTER TABLE lead_import_jobs ADD COLUMN IF NOT EXISTS "
        "vicidial_run_count INTEGER NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE lead_import_jobs ADD COLUMN IF NOT EXISTS "
        "vicidial_status VARCHAR(16) NOT NULL DEFAULT 'idle'"
    )
    op.execute(
        "ALTER TABLE lead_import_jobs ADD COLUMN IF NOT EXISTS "
        "is_active_for_vicidial BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute(
        "ALTER TABLE lead_import_jobs ADD COLUMN IF NOT EXISTS "
        "vicidial_started_at TIMESTAMPTZ"
    )
    op.execute(
        "ALTER TABLE lead_import_jobs ADD COLUMN IF NOT EXISTS "
        "vicidial_stopped_at TIMESTAMPTZ"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE lead_import_jobs DROP COLUMN IF EXISTS vicidial_stopped_at")
    op.execute("ALTER TABLE lead_import_jobs DROP COLUMN IF EXISTS vicidial_started_at")
    op.execute(
        "ALTER TABLE lead_import_jobs DROP COLUMN IF EXISTS is_active_for_vicidial"
    )
    op.execute("ALTER TABLE lead_import_jobs DROP COLUMN IF EXISTS vicidial_status")
    op.execute("ALTER TABLE lead_import_jobs DROP COLUMN IF EXISTS vicidial_run_count")
    op.execute("ALTER TABLE lead_import_jobs DROP COLUMN IF EXISTS vicidial_list_id")
