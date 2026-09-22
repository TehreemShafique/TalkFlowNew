"""Phase 7/Analytics: six pre-aggregated tables + rollup watermark (STEP 39).

Revision ID: h3i4j5k6l7m8
Revises: 0025051a7183
Create Date: 2026-09-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "h3i4j5k6l7m8"
down_revision: str | None = "0025051a7183"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UNSET_UUID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    # 1. Daily per-campaign funnel.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agg_campaign_daily (
            date DATE NOT NULL,
            tenant_id VARCHAR(36) NOT NULL,
            campaign_id UUID NOT NULL,
            total_calls INTEGER NOT NULL DEFAULT 0,
            answered INTEGER NOT NULL DEFAULT 0,
            contacted INTEGER NOT NULL DEFAULT 0,
            qualified INTEGER NOT NULL DEFAULT 0,
            transferred INTEGER NOT NULL DEFAULT 0,
            verifier_accepted INTEGER NOT NULL DEFAULT 0,
            disqualified INTEGER NOT NULL DEFAULT 0,
            avg_duration DOUBLE PRECISION,
            PRIMARY KEY (date, tenant_id, campaign_id)
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agg_campaign_daily_date "
        "ON agg_campaign_daily (date);"
    )

    # 2. Daily script-version performance.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agg_script_version_daily (
            date DATE NOT NULL,
            tenant_id VARCHAR(36) NOT NULL,
            script_version_id UUID NOT NULL,
            total_calls INTEGER NOT NULL DEFAULT 0,
            answered INTEGER NOT NULL DEFAULT 0,
            contacted INTEGER NOT NULL DEFAULT 0,
            qualified INTEGER NOT NULL DEFAULT 0,
            transferred INTEGER NOT NULL DEFAULT 0,
            disqualified INTEGER NOT NULL DEFAULT 0,
            avg_duration DOUBLE PRECISION,
            PRIMARY KEY (date, tenant_id, script_version_id)
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agg_script_version_daily_date "
        "ON agg_script_version_daily (date);"
    )

    # 3. Daily lead-source quality.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agg_source_daily (
            date DATE NOT NULL,
            tenant_id VARCHAR(36) NOT NULL,
            source VARCHAR(120) NOT NULL,
            total_calls INTEGER NOT NULL DEFAULT 0,
            answered INTEGER NOT NULL DEFAULT 0,
            contacted INTEGER NOT NULL DEFAULT 0,
            qualified INTEGER NOT NULL DEFAULT 0,
            transferred INTEGER NOT NULL DEFAULT 0,
            verifier_accepted INTEGER NOT NULL DEFAULT 0,
            disqualified INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (date, tenant_id, source)
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agg_source_daily_date "
        "ON agg_source_daily (date);"
    )

    # 4. Daily per-agent-alias bot performance.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agg_bot_daily (
            date DATE NOT NULL,
            tenant_id VARCHAR(36) NOT NULL,
            agent_alias VARCHAR(64) NOT NULL,
            total_calls INTEGER NOT NULL DEFAULT 0,
            answered INTEGER NOT NULL DEFAULT 0,
            contacted INTEGER NOT NULL DEFAULT 0,
            qualified INTEGER NOT NULL DEFAULT 0,
            transferred INTEGER NOT NULL DEFAULT 0,
            avg_talk_time_seconds DOUBLE PRECISION,
            avg_duration DOUBLE PRECISION,
            PRIMARY KEY (date, tenant_id, agent_alias)
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agg_bot_daily_date ON agg_bot_daily (date);"
    )

    # 5. Daily compliance signals by disqualification reason.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agg_compliance_daily (
            date DATE NOT NULL,
            tenant_id VARCHAR(36) NOT NULL,
            campaign_id UUID NOT NULL,
            reason VARCHAR(64) NOT NULL,
            total_calls INTEGER NOT NULL DEFAULT 0,
            answered INTEGER NOT NULL DEFAULT 0,
            contacted INTEGER NOT NULL DEFAULT 0,
            qualified INTEGER NOT NULL DEFAULT 0,
            disqualified INTEGER NOT NULL DEFAULT 0,
            opted_out INTEGER NOT NULL DEFAULT 0,
            qa_autofail INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (date, tenant_id, campaign_id, reason)
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agg_compliance_daily_date "
        "ON agg_compliance_daily (date);"
    )

    # 6. Single-row-per-tenant live headline counters.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agg_dashboard_counters (
            tenant_id VARCHAR(36) PRIMARY KEY,
            captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            total_calls INTEGER NOT NULL DEFAULT 0,
            calls_today INTEGER NOT NULL DEFAULT 0,
            answered_today INTEGER NOT NULL DEFAULT 0,
            qualified_today INTEGER NOT NULL DEFAULT 0,
            active_campaigns INTEGER NOT NULL DEFAULT 0,
            enabled_scripts INTEGER NOT NULL DEFAULT 0,
            suppression_count INTEGER NOT NULL DEFAULT 0,
            live_calls INTEGER NOT NULL DEFAULT 0
        );
        """
    )

    # 7. Persistent rollup watermark (incremental by design, STEP 39).
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agg_rollup_watermark (
            tenant_id VARCHAR(36) NOT NULL,
            aggregate_name VARCHAR(64) NOT NULL,
            watermark TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (tenant_id, aggregate_name)
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agg_rollup_watermark;")
    op.execute("DROP TABLE IF EXISTS agg_dashboard_counters;")
    op.execute("DROP TABLE IF EXISTS agg_compliance_daily;")
    op.execute("DROP TABLE IF EXISTS agg_bot_daily;")
    op.execute("DROP TABLE IF EXISTS agg_source_daily;")
    op.execute("DROP TABLE IF EXISTS agg_script_version_daily;")
    op.execute("DROP TABLE IF EXISTS agg_campaign_daily;")
