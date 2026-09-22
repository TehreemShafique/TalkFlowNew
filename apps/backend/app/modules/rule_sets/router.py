"""HTTP API router for rule sets module (/api/v1/rule-sets)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import UserContext
from app.core.database import get_db
from app.core.dependencies import require_permissions
from app.core.permissions import PERM_SCRIPT_VIEW
from app.modules.rule_sets import service
from app.modules.rule_sets.schemas import (
    RuleSetDTO,
    RuleSetEvaluateRequest,
    RuleSetEvaluateResponse,
)
from app.packages.contracts.base import DataResponse, PagedResponse

router = APIRouter(prefix="/rule-sets", tags=["rule-sets"])

ViewGate = Annotated[UserContext, Depends(require_permissions([PERM_SCRIPT_VIEW]))]
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=PagedResponse[RuleSetDTO])
async def list_rule_sets(
    actor: ViewGate,
    db: DbSession,
):
    """List qualification rule sets."""
    return await service.list_rule_sets(db, actor)


@router.post("/evaluate", response_model=DataResponse[RuleSetEvaluateResponse])
async def evaluate_rule_set(
    payload: RuleSetEvaluateRequest,
):
    """Evaluate fields against Medicare qualification rule set (Step 24)."""
    return await service.evaluate_rule_set(None, payload)
