"""Service layer for rule sets module."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.context import UserContext
from app.modules.rule_sets import repository
from app.modules.rule_sets.policies import MEDICARE_RS, evaluate
from app.modules.rule_sets.schemas import (
    RuleSetDTO,
    RuleSetEvaluateRequest,
    RuleSetEvaluateResponse,
)
from app.packages.contracts.base import DataResponse, PagedMeta, PagedResponse


async def list_rule_sets(
    db: AsyncSession,
    actor: UserContext,
) -> PagedResponse[RuleSetDTO]:
    _ = actor
    raw_items = await repository.list_rule_sets(db)
    dtos = [
        RuleSetDTO(
            id=item["id"],
            name=item["name"],
            description=item["description"],
            current_version=item["current_version"],
            active_version_id=item["active_version_id"],
            status=item["status"],
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )
        for item in raw_items
    ]
    meta = PagedMeta(page=1, page_size=len(dtos) or 20, total=len(dtos), total_pages=1)
    return PagedResponse(data=dtos, meta=meta)


async def evaluate_rule_set(
    rule_set_id: uuid.UUID | None,
    payload: RuleSetEvaluateRequest,
) -> DataResponse[RuleSetEvaluateResponse]:
    _ = rule_set_id
    eval_res = evaluate(MEDICARE_RS, payload.fields)
    return DataResponse(
        data=RuleSetEvaluateResponse(
            status=eval_res.status,
            reason=eval_res.reason,
        )
    )
