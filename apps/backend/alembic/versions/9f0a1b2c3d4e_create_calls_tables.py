"""Create the calls module tables (partitioned calls / transcript_turns / call_events,
plus call_qualification_fields, call_performance and call_node_path).

The calls module (ADR-02, decision.md section 3) owns the call registry and its
event / transcript / qualification / performance side tables:

* ``calls`` - one row per dialed call, range-partitioned monthly by
  ``started_at`` (decision.md/§13.3 "Partitioning is not optional").  The
  pre-existing plain stub (``id UUID PRIMARY KEY`` + the columns added by
  e5f6a7b8c9d0) is swapped here: inbound FKs are dropped first, the stub is
  renamed aside, the partitioned parent + partitions are created, the shared
  columns are copied, and the stub is dropped.
* ``transcript_turns`` - AI Voice Bot transcript lines, range-partitioned
  monthly by ``created_at`` (the spec's "by started_at" note is stale - the
  table carries no ``started_at`` column; ``created_at`` is added with a
  ``clock_timestamp()`` default and used as the partition key).
* ``call_events`` - deduplicated raw events, range-partitioned monthly by
  ``event_ts``.
* ``call_qualification_fields`` / ``call_performance`` / ``call_node_path`` -
  plain tables.

**Deviations from the task's flat-schema description, all required by
PostgreSQL partitioning** (documented so the wire contract is unaffected):

1. PKs are composite: ``calls (id, started_at)``, ``transcript_turns
   (id, created_at)``, ``call_events (id, event_ts)``.  A partitioned table's
   PK/unique index must include every partition-key column, so a single-column
   ``id`` PK is impossible.
2. No child FK to ``calls.id`` (transcript_turns / call_events /
   call_qualification_fields / call_performance / call_node_path / and the
   pre-existing call_recordings / qa_reviews / call_transcripts).  A FK to
   ``calls.id`` would need a unique index on ``(id)`` alone, which partitioning
   forbids.  Those columns are indexed instead; the FK is enforced logically by
   the owning repositories at write time.  The ORM models (used by
   ``Base.metadata.create_all`` in the test suite, where ``calls`` is the plain
   table) keep the real FKs.
3. UNIQUE indexes are composite: ``transcript_turns (call_id, seq,
   created_at)`` and ``call_events (call_id, external_event_id, event_ts)``
   instead of ``(call_id, seq)`` / ``(call_id, external_event_id)``.
4. ``calls.reference`` is NOT NULL (spec) but gains ``DEFAULT ''`` so legacy
   stub rows (which predate the column) copy cleanly; real rows from the
   pipeline always set it.  Uniqueness of ``reference`` (blueprint §13.3)
   cannot be a plain unique index here (partition key rule) and is deferred -
   see remain.md.
5. Outbound FKs from the partitioned ``calls`` parent to ``leads.id`` /
   ``campaigns.id`` / ``users.id`` are kept (a partitioned table may reference
   plain tables); the scripts tables do not exist yet so ``script_id`` /
   ``script_version_id`` are soft columns (same pattern as campaigns).

Schema order is FK-safe and the swap is idempotent: re-running on an already
partitioned schema creates only the missing partitions/indexes.

Revision ID: 9f0a1b2c3d4e
Revises: e5f6a7b8c9d0
Create Date: 2026-09-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "9f0a1b2c3d4e"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSONB = postgresql.JSONB(astext_type=sa.Text())

# Monthly partitions created up-front; the partition-maintenance job (see
# remain.md) is responsible for each later month.
_MONTHS = (
    ("2026_09", "2026-09-01", "2026-10-01"),
    ("2026_10", "2026-10-01", "2026-11-01"),
    ("2026_11", "2026-11-01", "2026-12-01"),
)

_CALLS_COLUMNS = """
    id UUID NOT NULL,
    reference VARCHAR(64) NOT NULL DEFAULT '',
    direction VARCHAR(16) NOT NULL DEFAULT 'outbound',
    status VARCHAR(32) NOT NULL DEFAULT 'queued',
    disposition VARCHAR(64),
    lead_id UUID,
    campaign_id UUID,
    script_id UUID,
    script_version_id UUID,
    channel_id VARCHAR(64),
    vicidial_call_id VARCHAR(64),
    vicidial_lead_id VARCHAR(64),
    vicidial_list_id VARCHAR(64),
    vicidial_status VARCHAR(32),
    caller_number VARCHAR(32),
    caller_state VARCHAR(8),
    did_used VARCHAR(32),
    caller_id_used VARCHAR(32),
    attempt_number INTEGER NOT NULL DEFAULT 1,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    answered_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    talk_time_seconds INTEGER,
    qualification_status VARCHAR(32),
    disqualification_reason VARCHAR(64),
    transfer_status VARCHAR(32),
    verifier_id UUID,
    qa_status VARCHAR(32),
    qa_score DOUBLE PRECISION,
    tenant_id VARCHAR(36),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (id, started_at)
"""

# Columns shared between the legacy plain stub and the partitioned parent;
# everything else takes its server default on copy.
_CALLS_COPY = (
    "id",
    "tenant_id",
    "started_at",
    "duration_seconds",
    "disposition",
    "qualification_status",
    "disqualification_reason",
    "lead_id",
    "campaign_id",
    "verifier_id",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _table_exists(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _partitioned(bind, name: str) -> bool:
    row = bind.execute(
        sa.text(
            "SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "JOIN pg_partitioned_table p ON p.partrelid = c.oid "
            "WHERE c.relname = :name AND n.nspname = 'public'"
        ),
        {"name": name},
    ).first()
    return row is not None


def _drop_inbound_fks(bind, target: str) -> None:
    """Drop every FK that references ``target`` (any name, any table).

    The plain stub can carry constraints under different names depending on how
    it was created (migration vs create_all), so resolve them dynamically
    instead of hard-coding names.
    """
    rows = bind.execute(
        sa.text(
            "SELECT conrelid::regclass::text AS tbl, conname AS name "
            "FROM pg_constraint "
            "WHERE contype = 'f' AND confrelid = to_regclass(:tbl)"
        ),
        {"tbl": target},
    ).all()
    for row in rows:
        bind.execute(sa.text(f'ALTER TABLE {row.tbl} DROP CONSTRAINT "{row.name}"'))


def _create_partitions(bind, parent: str, months=_MONTHS, default: bool = True) -> None:
    if default:
        name = f"{parent}_default"
        if not _table_exists(bind, name):
            bind.execute(
                sa.text(
                    f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF {parent} DEFAULT"
                )
            )
    for suffix, start, end in months:
        name = f"{parent}_monthly_{suffix}"
        if not _table_exists(bind, name):
            bind.execute(
                sa.text(
                    f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF {parent} "
                    f"FOR VALUES FROM ('{start}') TO ('{end}')"
                )
            )


def _ensure_calls_indexes(bind) -> None:
    existing = {ix["name"] for ix in sa.inspect(bind).get_indexes("calls")}
    want = {
        "ix_calls_tenant_id": "CREATE INDEX IF NOT EXISTS ix_calls_tenant_id ON calls (tenant_id)",
        "ix_calls_campaign_id_started_at": (
            "CREATE INDEX IF NOT EXISTS ix_calls_campaign_id_started_at "
            "ON calls (campaign_id, started_at)"
        ),
        "ix_calls_script_version_id_started_at": (
            "CREATE INDEX IF NOT EXISTS ix_calls_script_version_id_started_at "
            "ON calls (script_version_id, started_at)"
        ),
        "ix_calls_lead_id_started_at": (
            "CREATE INDEX IF NOT EXISTS ix_calls_lead_id_started_at ON calls (lead_id, started_at)"
        ),
        "ix_calls_vicidial_call_id": (
            "CREATE INDEX IF NOT EXISTS ix_calls_vicidial_call_id ON calls (vicidial_call_id)"
        ),
        "ix_calls_channel_id": (
            "CREATE INDEX IF NOT EXISTS ix_calls_channel_id ON calls (channel_id)"
        ),
        "ix_calls_reference": "CREATE INDEX IF NOT EXISTS ix_calls_reference ON calls (reference)",
        "ix_calls_live_status": (
            "CREATE INDEX IF NOT EXISTS ix_calls_live_status ON calls (status) "
            "WHERE status IN ('in_progress','transferring')"
        ),
    }
    for name, ddl in want.items():
        if name not in existing:
            bind.execute(sa.text(ddl))


def _ensure_calls_fk(bind, name: str, ddl: str) -> None:
    """Add an outbound FK if missing.

    ``ADD CONSTRAINT IF NOT EXISTS`` is not valid PostgreSQL, so guard on
    ``pg_constraint`` instead (re-running an already-migrated schema must not
    fail when these exist).
    """
    exists = bind.execute(
        sa.text(
            "SELECT 1 FROM pg_constraint "
            "WHERE conname = :name AND conrelid = 'calls'::regclass"
        ),
        {"name": name},
    ).first()
    if exists is None:
        bind.execute(sa.text(ddl))


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()

    # The stub might be plain this migration swapped historically or a future
    # run may race a re-run - only touch it when it is a non-partitioned table.
    if _table_exists(bind, "calls") and not _partitioned(bind, "calls"):
        _drop_inbound_fks(bind, "calls")
        bind.execute(sa.text("ALTER TABLE calls RENAME TO calls_legacy"))

        bind.execute(
            sa.text(
                f"CREATE TABLE calls ({_CALLS_COLUMNS}) PARTITION BY RANGE (started_at)"
            )
        )
        _create_partitions(bind, "calls")

        copy_cols = ", ".join(_CALLS_COPY)
        bind.execute(
            sa.text(
                f"INSERT INTO calls ({copy_cols}) "
                f"SELECT {copy_cols} FROM calls_legacy "
                f"ON CONFLICT DO NOTHING"
            )
        )
        bind.execute(sa.text("DROP TABLE calls_legacy"))
    elif not _table_exists(bind, "calls"):
        bind.execute(
            sa.text(
                f"CREATE TABLE calls ({_CALLS_COLUMNS}) PARTITION BY RANGE (started_at)"
            )
        )
        _create_partitions(bind, "calls")

    _ensure_calls_indexes(bind)
    _ensure_calls_fk(
        bind,
        "fk_calls_lead_id",
        "ALTER TABLE calls ADD CONSTRAINT fk_calls_lead_id "
        "FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE SET NULL",
    )
    _ensure_calls_fk(
        bind,
        "fk_calls_campaign_id",
        "ALTER TABLE calls ADD CONSTRAINT fk_calls_campaign_id "
        "FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE SET NULL",
    )
    _ensure_calls_fk(
        bind,
        "fk_calls_verifier_id",
        "ALTER TABLE calls ADD CONSTRAINT fk_calls_verifier_id "
        "FOREIGN KEY (verifier_id) REFERENCES users(id) ON DELETE SET NULL",
    )

    # ---------------- transcript_turns (partitioned by created_at) ---------
    if not _table_exists(bind, "transcript_turns"):
        bind.execute(
            sa.text(
                "CREATE TABLE transcript_turns ("
                "  id UUID NOT NULL,"
                "  call_id UUID NOT NULL,"
                "  speaker VARCHAR(32) NOT NULL,"
                "  seq INTEGER NOT NULL,"
                "  text TEXT NOT NULL,"
                "  start_ts_ms INTEGER,"
                "  end_ts_ms INTEGER,"
                "  node_id VARCHAR(64),"
                "  confidence DOUBLE PRECISION,"
                "  redacted BOOLEAN NOT NULL DEFAULT false,"
                "  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT clock_timestamp(),"
                "  PRIMARY KEY (id, created_at)"
                ") PARTITION BY RANGE (created_at)"
            )
        )
        _create_partitions(bind, "transcript_turns")
    else:
        _create_partitions(bind, "transcript_turns")

    existing = {ix["name"] for ix in sa.inspect(bind).get_indexes("transcript_turns")}
    if "ix_transcript_turns_call_seq" not in existing:
        bind.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_transcript_turns_call_seq "
                "ON transcript_turns (call_id, seq)"
            )
        )
    if "uq_transcript_turns_call_seq_created" not in existing:
        bind.execute(
            sa.text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_transcript_turns_call_seq_created "
                "ON transcript_turns (call_id, seq, created_at)"
            )
        )
    if "ix_transcript_turns_call_start_ms" not in existing:
        bind.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_transcript_turns_call_start_ms "
                "ON transcript_turns (call_id, start_ts_ms)"
            )
        )

    # ---------------- call_events (partitioned by event_ts) ----------------
    if not _table_exists(bind, "call_events"):
        bind.execute(
            sa.text(
                "CREATE TABLE call_events ("
                "  id UUID NOT NULL,"
                "  call_id UUID NOT NULL,"
                "  external_event_id VARCHAR(128) NOT NULL,"
                "  type VARCHAR(96) NOT NULL,"
                "  payload JSONB,"
                "  event_ts TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),"
                "  PRIMARY KEY (id, event_ts)"
                ") PARTITION BY RANGE (event_ts)"
            )
        )
        _create_partitions(bind, "call_events")
    else:
        _create_partitions(bind, "call_events")

    existing = {ix["name"] for ix in sa.inspect(bind).get_indexes("call_events")}
    if "ix_call_events_call_id_event_ts" not in existing:
        bind.execute(
            sa.text(
                "CREATE INDEX IF NOT EXISTS ix_call_events_call_id_event_ts "
                "ON call_events (call_id, event_ts)"
            )
        )
    if "uq_call_events_call_external_ts" not in existing:
        bind.execute(
            sa.text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_call_events_call_external_ts "
                "ON call_events (call_id, external_event_id, event_ts)"
            )
        )

    # ---------------- call_qualification_fields (plain) --------------------
    if not _table_exists(bind, "call_qualification_fields"):
        op.create_table(
            "call_qualification_fields",
            sa.Column(
                "id",
                sa.Uuid(),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("call_id", sa.Uuid(), nullable=False),
            sa.Column("field", sa.String(length=64), nullable=False),
            sa.Column("label", sa.String(length=255), nullable=True),
            sa.Column("value", _JSONB, nullable=True),
            sa.Column(
                "captured_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=True,
            ),
            sa.Column("transcript_ref", sa.String(length=128), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        bind.execute(
            sa.text(
                "CREATE INDEX ix_call_qualification_fields_call_id_field "
                "ON call_qualification_fields (call_id, field)"
            )
        )

    # ---------------- call_performance (plain) -----------------------------
    if not _table_exists(bind, "call_performance"):
        op.create_table(
            "call_performance",
            sa.Column("call_id", sa.Uuid(), nullable=False),
            sa.Column("vad_ms", sa.Float(), nullable=True),
            sa.Column("stt_ms", sa.Float(), nullable=True),
            sa.Column("decide_ms", sa.Float(), nullable=True),
            sa.Column("llm_ttft_ms", sa.Float(), nullable=True),
            sa.Column("llm_total_ms", sa.Float(), nullable=True),
            sa.Column("tts_ttfa_ms", sa.Float(), nullable=True),
            sa.Column("tts_total_ms", sa.Float(), nullable=True),
            sa.Column("total_turn_ms", sa.Float(), nullable=True),
            sa.Column("turn_count", sa.Integer(), nullable=True),
            sa.Column("stt_provider", sa.String(length=32), nullable=True),
            sa.Column("tts_provider", sa.String(length=32), nullable=True),
            sa.Column("llm_provider", sa.String(length=32), nullable=True),
            sa.PrimaryKeyConstraint("call_id"),
        )

    # ---------------- call_node_path (plain, powers script-path) -----------
    if not _table_exists(bind, "call_node_path"):
        op.create_table(
            "call_node_path",
            sa.Column(
                "id",
                sa.Uuid(),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("call_id", sa.Uuid(), nullable=False),
            sa.Column("seq", sa.Integer(), nullable=True),
            sa.Column("node_id", sa.String(length=64), nullable=True),
            sa.Column("node_type", sa.String(length=32), nullable=True),
            sa.Column("node_name", sa.String(length=255), nullable=True),
            sa.Column("entered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("exited_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("transition_taken", sa.String(length=64), nullable=True),
            sa.Column("meta", _JSONB, nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        bind.execute(
            sa.text(
                "CREATE INDEX ix_call_node_path_call_id_seq ON call_node_path (call_id, seq)"
            )
        )


def downgrade() -> None:
    """Best-effort reversal: drop everything this revision created.

    A real down-migration back to a populated plain ``calls`` table is not
    attempted - the legacy data was already copied forward and the stub's exact
    shape is gone.  Fresh downgrades land without a ``calls`` table (the next
    ``upgrade head`` run rebuilds it from scratch).
    """
    for name in (
        "call_node_path",
        "call_performance",
        "call_qualification_fields",
        "call_events",
        "transcript_turns",
    ):
        op.execute(f"DROP TABLE IF EXISTS {name} CASCADE")
    op.execute("DROP TABLE IF EXISTS calls CASCADE")
