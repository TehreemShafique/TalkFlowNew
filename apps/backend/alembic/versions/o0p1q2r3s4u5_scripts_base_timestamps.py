"""Add the inherited Base timestamp columns to the scripts tables.

``app.packages.db.base.Base`` is an abstract mixin: every subclass inherits
``created_at`` and ``updated_at`` as NOT NULL columns.  ``a1b2c3d4e5f6`` created
``script_versions`` and ``script_activations`` before that mixin existed and did
not include them, so a database built from migrations is missing three columns
the ORM insists on:

    script_activations.created_at   NOT NULL
    script_activations.updated_at   NOT NULL
    script_versions.updated_at      NOT NULL

Any ORM insert into those two tables fails with UndefinedColumnError.  The test
suite never saw it because conftest builds its schema with
``Base.metadata.create_all`` - ORM metadata, not migrations - so the tests and a
migrated database have been describing different shapes for these tables.

``l7m8n9o0p1q2`` made the same repair for ``refresh_tokens``.

Existing rows are backfilled from the timestamp each table already had
(``created_at`` on script_versions, ``activated_at`` on script_activations, which
has no creation column of its own) rather than stamped with the migration run
time, so history is not rewritten.  The server default is dropped afterwards to
match the mixin, which populates both columns from Python.

Revision ID: o0p1q2r3s4u5
Revises: n9o0p1q2r3s4
Create Date: 2026-09-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "o0p1q2r3s4u5"
down_revision: str | None = "n9o0p1q2r3s4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE script_activations ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ")
    op.execute(
        "UPDATE script_activations SET created_at = activated_at WHERE created_at IS NULL"
    )
    op.execute("ALTER TABLE script_activations ALTER COLUMN created_at SET NOT NULL")
    op.execute("ALTER TABLE script_activations ALTER COLUMN created_at DROP DEFAULT")

    op.execute("ALTER TABLE script_activations ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ")
    op.execute(
        "UPDATE script_activations SET updated_at = COALESCE(created_at, activated_at) "
        "WHERE updated_at IS NULL"
    )
    op.execute("ALTER TABLE script_activations ALTER COLUMN updated_at SET NOT NULL")
    op.execute("ALTER TABLE script_activations ALTER COLUMN updated_at DROP DEFAULT")

    op.execute("ALTER TABLE script_versions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ")
    op.execute("UPDATE script_versions SET updated_at = created_at WHERE updated_at IS NULL")
    op.execute("ALTER TABLE script_versions ALTER COLUMN updated_at SET NOT NULL")
    op.execute("ALTER TABLE script_versions ALTER COLUMN updated_at DROP DEFAULT")


def downgrade() -> None:
    op.execute("ALTER TABLE script_versions DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE script_activations DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE script_activations DROP COLUMN IF EXISTS created_at")
