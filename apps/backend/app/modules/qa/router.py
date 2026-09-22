"""HTTP surface for Quality Assurance (/api/v1/qa) (Step 49)."""

from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import UserContext
from app.core.database import get_db
from app.core.dependencies import require_permissions
from app.core.permissions import PERM_QA_AUDIT, PERM_RECORDING_VIEW
from app.modules.qa import service
from app.modules.qa.schemas import (
    QAReviewCreateRequest,
    QAReviewDTO,
    QASampleCallDTO,
    QASampleQuery,
    QAScorecardDTO,
)
from app.packages.contracts.base import DataResponse

router = APIRouter(prefix="/qa", tags=["qa"])

QaAuditGate = Annotated[UserContext, Depends(require_permissions([PERM_QA_AUDIT]))]
ViewGate = Annotated[UserContext, Depends(require_permissions([PERM_RECORDING_VIEW]))]
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/sample", response_model=DataResponse[list[QASampleCallDTO]])
async def sample_calls(
    query: Annotated[QASampleQuery, Depends()],
    actor: ViewGate,
    db: DbSession,
):
    """Risk-weighted daily call sampling (Step 49)."""
    return await service.sample_calls(db, query)


@router.get("/scorecards", response_model=DataResponse[QAScorecardDTO])
async def get_active_scorecard(actor: ViewGate, db: DbSession):
    """Fetch active QA scorecard and criteria."""
    return await service.get_active_scorecard(db)


@router.post(
    "/reviews",
    response_model=DataResponse[QAReviewDTO],
    status_code=status.HTTP_201_CREATED,
)
async def submit_qa_review(
    payload: QAReviewCreateRequest,
    actor: QaAuditGate,
    db: DbSession,
):
    """Submit QA call review (checks reviewer self-review prohibition and auto-fail)."""
    return await service.submit_qa_review(db, actor, payload)
