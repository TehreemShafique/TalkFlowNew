"""Phase 6: Transactional Outbox with seq, outbox_pending index, channel sequences, and transfers table.

Revision ID: g2h3i4j5k6l7
Revises: e7f8a9b0c1d2
Create Date: 2026-09-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "g2h3i4j5k6l7"
down_revision: str | None = "e7f8a9b0c1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    # 1. Channel sequences for monotonic seq assignment at insert
    channels = [
        "dashboard",
        "calls_live",
        "transfers",
        "recordings_events",
        "talkflow_vicidial_sync_v1",
    ]
    for ch in channels:
        op.execute(f"CREATE SEQUENCE IF NOT EXISTS outbox_seq_{ch};")

    # 2. Add seq column to outbox table if not existing
    op.execute("ALTER TABLE outbox ADD COLUMN IF NOT EXISTS seq BIGINT;")

    # 3. Create index outbox_pending on outbox(created_at) WHERE dispatched_at IS NULL
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS outbox_pending
        ON outbox (created_at)
        WHERE dispatched_at IS NULL;
        """
    )

    # 4. Create transfers table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS transfers (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            call_id UUID,
            lead_id UUID REFERENCES leads(id) ON DELETE SET NULL,
            campaign_id UUID REFERENCES campaigns(id) ON DELETE SET NULL,
            from_agent_id VARCHAR(120),
            verifier_id VARCHAR(120),
            verifier_group_id VARCHAR(120),
            status VARCHAR(48) NOT NULL DEFAULT 'initiated',
            ring_timeout_seconds INT NOT NULL DEFAULT 20,
            initiated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            bridged_at TIMESTAMPTZ,
            ended_at TIMESTAMPTZ,
            failure_reason VARCHAR(255),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_transfers_call
        ON transfers (call_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_transfers_verifier
        ON transfers (verifier_id, status);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_transfers_status
        ON transfers (status, initiated_at);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS transfers CASCADE;")
    op.execute("DROP INDEX IF EXISTS outbox_pending;")
    channels = [
        "dashboard",
        "calls_live",
        "transfers",
        "recordings_events",
        "talkflow_vicidial_sync_v1",
    ]
    for ch in channels:
        op.execute(f"DROP SEQUENCE IF EXISTS outbox_seq_{ch};")
