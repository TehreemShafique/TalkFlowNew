"""STEP 15 ingest columns + STEP 18 transcript full-text engine.

Ships four schema pieces the ingest worker (``workers/call_ingest_worker.py``)
and the calls module rely on:

* ``calls.agent_alias_used`` / ``calls.rule_set_version_id`` - recorded when the
  ``talkflow.call.opened.v1`` event is ingested (the Agent alias the voice bot
  used and the rule set the campaign was run under).  Both are set **at open**,
  so late / out-of-order reconciliation never has to guess them.
* ``transcript_turns.tsv`` - a ``GENERATED ALWAYS AS (to_tsvector('english',
  text)) STORED`` TSVECTOR column.  PostgreSQL maintains it from the stored
  text, so full-text search (roadmap STEP 18) can never drift from the source.
  The ``transcript_tsv_idx`` GIN index is created on the partitioned parent and
  recurses to every partition.
* ``transcript_turns.node_id`` - made NOT NULL so node-level QA and script-path
  visualizers can rely on every turn carrying its script node (existing NULLs
  are backfilled to ``'unknown'``).

A plain unique index on ``calls.channel_id`` is deliberately NOT added here:
the dev ``calls`` table is range-partitioned by ``started_at``, and PG forbids
a unique index that does not include the partition key.  Rule-2 idempotency
("one channel -> one call") is enforced by the worker's channel lookup instead;
the ORM test table keeps a real ``UniqueConstraint`` on channel_id.

Revision ID: b5c6d7e8f901
Revises: 9f0a1b2c3d4e
Create Date: 2026-09-18
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b5c6d7e8f901"
down_revision: str | None = "9f0a1b2c3d4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Stamps recorded at open (roadmap section 660).
    op.execute(
        "ALTER TABLE calls ADD COLUMN IF NOT EXISTS agent_alias_used VARCHAR(64)"
    )
    op.execute("ALTER TABLE calls ADD COLUMN IF NOT EXISTS rule_set_version_id UUID")

    # Full-text transcript search (roadmap STEP 18).  The vector is a real
    # GENERATED ALWAYS column so the stored text IS the source of truth; the
    # GIN index lives on the partitioned parent and cascades to partitions.
    op.execute("DROP INDEX IF EXISTS ix_transcript_turns_tsv_gin")
    op.execute("ALTER TABLE transcript_turns DROP COLUMN IF EXISTS tsv")
    op.execute(
        "ALTER TABLE transcript_turns ADD COLUMN tsv TSVECTOR "
        "GENERATED ALWAYS AS (to_tsvector('english', text)) STORED"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS transcript_tsv_idx "
        "ON transcript_turns USING GIN (tsv)"
    )

    # Node id is mandatory for node-level QA / script-path visualizers
    # (roadmap STEP 18 / section 26.4).
    op.execute("UPDATE transcript_turns SET node_id = 'unknown' WHERE node_id IS NULL")
    op.execute("ALTER TABLE transcript_turns ALTER COLUMN node_id SET NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE transcript_turns ALTER COLUMN node_id DROP NOT NULL")
    op.execute("DROP INDEX IF EXISTS transcript_tsv_idx")
    op.execute("ALTER TABLE transcript_turns DROP COLUMN IF EXISTS tsv")
    op.execute("ALTER TABLE calls DROP COLUMN IF EXISTS rule_set_version_id")
    op.execute("ALTER TABLE calls DROP COLUMN IF EXISTS agent_alias_used")
