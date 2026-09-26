"""Add the descriptive columns to retention_policies.

``2a1c4f7e96b3`` created ``retention_policies`` as a bare stub - ``CREATE TABLE
IF NOT EXISTS retention_policies (id UUID PRIMARY KEY)`` - because the only
consumer at the time was the ``call_recordings.retention_policy_id`` foreign
key, which needs nothing but a target ``id``.

The ORM projection in ``packages.db.models`` has since grown the two columns
the retention purger and the recordings module actually read: a human-readable
``name`` and the ``audio_days`` window.  Nothing ever migrated them, so a
database built from migrations has a one-column table that the ORM cannot
insert into - ``retention_policies_table.insert().values(id=..., name=...,
audio_days=...)`` raises ``UndefinedColumnError``.  That is what the test
fixture in ``tests/conftest.py`` does.

Both columns are nullable, matching the ORM: a policy row created before this
revision keeps working with a NULL window, and the purger treats that as "no
expiry" rather than "expire immediately".

Revision ID: n9o0p1q2r3s4
Revises: m8n9o0p1q2r3
Create Date: 2026-09-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "n9o0p1q2r3s4"
down_revision: str | None = "m8n9o0p1q2r3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE retention_policies ADD COLUMN IF NOT EXISTS name VARCHAR(120)"
    )
    op.execute("ALTER TABLE retention_policies ADD COLUMN IF NOT EXISTS audio_days INTEGER")


def downgrade() -> None:
    op.execute("ALTER TABLE retention_policies DROP COLUMN IF EXISTS audio_days")
    op.execute("ALTER TABLE retention_policies DROP COLUMN IF EXISTS name")
