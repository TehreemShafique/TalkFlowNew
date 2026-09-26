"""Add the ORM timestamp columns to refresh_tokens.

``app.packages.db.base.Base`` injects ``created_at``/``updated_at`` as NOT NULL
on every mapped subclass, so ``j5k6l7m8n9o0`` must have created them too.  It did
not, and the gap was invisible to the test suite because the test database is
built from ORM metadata via ``create_all`` rather than from migrations - the
mismatch only surfaced against a migrated database, as a login-time 500
(``column "created_at" of relation "refresh_tokens" does not exist``).

Revision ID: l7m8n9o0p1q2
Revises: k6l7m8n9o0p1
Create Date: 2026-09-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "l7m8n9o0p1q2"
down_revision: str | None = "k6l7m8n9o0p1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE refresh_tokens ADD COLUMN IF NOT EXISTS "
        "created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
    )
    op.execute(
        "ALTER TABLE refresh_tokens ADD COLUMN IF NOT EXISTS "
        "updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE refresh_tokens DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE refresh_tokens DROP COLUMN IF EXISTS created_at")
