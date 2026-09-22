"""Service layer for compliance module (Step 25)."""

from __future__ import annotations

import json
import uuid
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import AuditResult, write_audit
from app.core.context import UserContext
from app.core.errors import AppError
from app.modules.compliance import repository
from app.modules.compliance.policies import validate_mode_change
from app.modules.compliance.schemas import (
    ComplianceProfileDTO,
    ComplianceRuleDTO,
    ComplianceRuleUpdate,
)
from app.packages.contracts.base import DataResponse, PagedMeta, PagedResponse


async def list_profiles(
    db: AsyncSession,
    actor: UserContext,
) -> PagedResponse[ComplianceProfileDTO]:
    _ = actor
    raw_items = await repository.list_profiles(db)
    dtos = [
        ComplianceProfileDTO(
            id=item["id"],
            name=item["name"],
            description=item["description"],
            jurisdiction=item["jurisdiction"],
            is_active=item["is_active"],
            rules=[],
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )
        for item in raw_items
    ]
    meta = PagedMeta(page=1, page_size=len(dtos) or 20, total=len(dtos), total_pages=1)
    return PagedResponse(data=dtos, meta=meta)


async def get_profile(
    db: AsyncSession,
    actor: UserContext,
    profile_id: uuid.UUID,
) -> DataResponse[ComplianceProfileDTO]:
    _ = actor
    item = await repository.get_profile(db, profile_id)
    if not item:
        raise AppError(
            code="compliance.profile_not_found",
            message="Profile not found",
            http_status=404,
        )

    rules_dtos = [
        ComplianceRuleDTO(
            id=r["id"],
            profile_id=r["profile_id"],
            rule_key=r["rule_key"],
            mode=r["mode"],
            rationale=r["rationale"],
            updated_at=r["updated_at"],
        )
        for r in item.get("rules", [])
    ]
    return DataResponse(
        data=ComplianceProfileDTO(
            id=item["id"],
            name=item["name"],
            description=item["description"],
            jurisdiction=item["jurisdiction"],
            is_active=item["is_active"],
            rules=rules_dtos,
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )
    )


async def update_rule_mode(
    db: AsyncSession,
    actor: UserContext,
    profile_id: uuid.UUID,
    rule_key: str,
    payload: ComplianceRuleUpdate,
) -> DataResponse[ComplianceProfileDTO]:
    current_profile = await repository.get_profile(db, profile_id)
    if not current_profile:
        raise AppError(
            code="compliance.profile_not_found",
            message="Profile not found",
            http_status=404,
        )

    current_mode = "enforce"
    for r in current_profile.get("rules", []):
        if r["rule_key"] == rule_key:
            current_mode = r["mode"]
            break

    errs = validate_mode_change(
        current_mode=current_mode,
        target_mode=payload.mode,
        actor_role=actor.role,
        confirmation=payload.confirmation,
        rationale=payload.rationale,
    )
    if errs:
        raise AppError(
            code="compliance.invalid_override",
            message="; ".join(errs),
            http_status=403 if "MASTER_ADMIN" in errs[0] else 400,
        )

    await repository.update_rule_mode(
        db,
        profile_id=profile_id,
        rule_key=rule_key,
        mode=payload.mode,
        rationale=payload.rationale,
        user_id=actor.user_id,
    )

    await write_audit(
        db,
        actor_id=actor.user_id,
        actor_role=actor.role,
        action="compliance.rule_mode_update",
        resource_type="compliance_rule",
        resource_id=f"{profile_id}:{rule_key}",
        result=AuditResult.SUCCESS,
        details={"mode": payload.mode, "rationale": payload.rationale},
    )

    return await get_profile(db, actor, profile_id)


async def publish_bundle_to_redis(
    redis_client: Redis,
    campaign_id: uuid.UUID | str | None,
    script_version_id: uuid.UUID | str,
    bundle_data: dict[str, Any],
) -> None:
    """Compile and publish bundle to Redis on version activation (Step 25).

    Keys:
    - cp:script:bundle:{scriptVersionId} -> full JSON payload
    - cp:campaign:{campaignId}:active_script -> scriptVersionId
    """
    ver_str = str(script_version_id)
    bundle_json = json.dumps(bundle_data)

    await redis_client.set(f"cp:script:bundle:{ver_str}", bundle_json)

    if campaign_id:
        camp_str = str(campaign_id)
        await redis_client.set(f"cp:campaign:{camp_str}:active_script", ver_str)
