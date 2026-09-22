"""Phase 9: QA scorecards & reviews, alerts, integrations, notifications (STEP 49-51).

Revision ID: i4j5k6l7m8n9
Revises: h3i4j5k6l7m8
Create Date: 2026-09-22
"""

from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "i4j5k6l7m8n9"
down_revision: str | None = "h3i4j5k6l7m8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS qa_scorecards (
            id UUID PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            version VARCHAR(20) NOT NULL DEFAULT 'v1.0',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS qa_scorecard_criteria (
            id UUID PRIMARY KEY,
            scorecard_id UUID NOT NULL REFERENCES qa_scorecards(id) ON DELETE CASCADE,
            category VARCHAR(60) NOT NULL,
            title VARCHAR(200) NOT NULL,
            weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
            auto_fail BOOLEAN NOT NULL DEFAULT FALSE,
            display_order INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS qa_reviews (
            id UUID PRIMARY KEY,
            call_id UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
            recording_id UUID REFERENCES call_recordings(id) ON DELETE SET NULL,
            scorecard_id UUID NOT NULL REFERENCES qa_scorecards(id),
            reviewer_id UUID NOT NULL REFERENCES users(id),
            total_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            passed BOOLEAN NOT NULL DEFAULT TRUE,
            auto_failed BOOLEAN NOT NULL DEFAULT FALSE,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS qa_review_scores (
            id UUID PRIMARY KEY,
            review_id UUID NOT NULL REFERENCES qa_reviews(id) ON DELETE CASCADE,
            criterion_id UUID NOT NULL REFERENCES qa_scorecard_criteria(id),
            score_value DOUBLE PRECISION NOT NULL DEFAULT 0.0,
            auto_failed BOOLEAN NOT NULL DEFAULT FALSE
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id UUID PRIMARY KEY,
            code VARCHAR(80) NOT NULL,
            severity VARCHAR(20) NOT NULL DEFAULT 'warning',
            title VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            resource_type VARCHAR(60),
            resource_id VARCHAR(120),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            acknowledged_at TIMESTAMPTZ,
            acknowledged_by UUID REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS integrations (
            id UUID PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            type VARCHAR(60) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'configured',
            config JSONB DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id UUID PRIMARY KEY,
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            title VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            type VARCHAR(40) NOT NULL DEFAULT 'info',
            read_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS notifications CASCADE;
        DROP TABLE IF EXISTS integrations CASCADE;
        DROP TABLE IF EXISTS alerts CASCADE;
        DROP TABLE IF EXISTS qa_review_scores CASCADE;
        DROP TABLE IF EXISTS qa_reviews CASCADE;
        DROP TABLE IF EXISTS qa_scorecard_criteria CASCADE;
        DROP TABLE IF EXISTS qa_scorecards CASCADE;
        """
    )
