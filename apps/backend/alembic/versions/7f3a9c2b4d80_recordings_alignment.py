"""Recordings alignment: tenant scope, retention, QA reviews, transcripts.

Adds the schema surfaces the recordings module needs to serve the CDR
Recordings & QA Compliance view end-to-end:

* ``calls.tenant_id`` - multi-tenant scope column the repository's
  ``_scope_filters()`` enforces (Rule R5).
* ``call_recordings.expires_at`` - hard retention deadline consumed by the
  background purge worker (``service.purge_expired_recordings``).
* ``qa_reviews`` - one row per audited call: float score, audit status and the
  mandatory compliance checklist flags written by POST /recordings/{id}/qa-audit.
* ``call_transcripts`` - ordered AI Voice Bot transcript lines per call,
  returned on every recording payload as ``transcript``.

Revision ID: 7f3a9c2b4d80
Revises: 136f1f2e55a9
Create Date: 2026-09-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7f3a9c2b4d80"
down_revision: str | None = "136f1f2e55a9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("calls", sa.Column("tenant_id", sa.String(length=36), nullable=True))
    op.create_index("ix_calls_tenant_id", "calls", ["tenant_id"])

    op.add_column(
        "call_recordings",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "qa_reviews",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("call_id", sa.Uuid(), nullable=False),
        sa.Column("recording_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("auto_failed", sa.Boolean(), nullable=True),
        sa.Column("consent_verified", sa.Boolean(), nullable=True),
        sa.Column("qual_verified", sa.Boolean(), nullable=True),
        sa.Column("transfer_verified", sa.Boolean(), nullable=True),
        sa.Column("notes", sa.String(length=4000), nullable=True),
        sa.Column("audited_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["recording_id"], ["call_recordings.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["audited_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_qa_reviews_call_id", "qa_reviews", ["call_id"], unique=True)
    op.create_index("ix_qa_reviews_recording_id", "qa_reviews", ["recording_id"])

    op.create_table(
        "call_transcripts",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("call_id", sa.Uuid(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(length=32), nullable=False),
        sa.Column("time", sa.String(length=16), nullable=False),
        sa.Column("text", sa.String(length=4000), nullable=False),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_call_transcripts_call_id", "call_transcripts", ["call_id"])


def downgrade() -> None:
    op.drop_index("ix_call_transcripts_call_id", table_name="call_transcripts")
    op.drop_table("call_transcripts")

    op.drop_index("ix_qa_reviews_recording_id", table_name="qa_reviews")
    op.drop_index("uq_qa_reviews_call_id", table_name="qa_reviews")
    op.drop_table("qa_reviews")

    op.drop_column("call_recordings", "expires_at")

    op.drop_index("ix_calls_tenant_id", table_name="calls")
    op.drop_column("calls", "tenant_id")
