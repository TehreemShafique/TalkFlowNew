"""Campaign service - lifecycle orchestration (repository + policies + audit).

Every mutation writes its ``audit_log`` row and its outbox event in the **same
transaction** as the state change (Rule R8), and the pure start guard
(``policies.can_start_campaign``) decides dialability without any I/O.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.context import UserContext
from app.modules.campaigns import repository as repo
from app.modules.campaigns.errors import (
    CampaignInvalidStateError,
    CampaignNotFoundError,
    CampaignStartFailedError,
    CampaignVersionConflictError,
)
from app.modules.campaigns.events import CampaignEventType, publish_campaign_event
from app.modules.campaigns.policies import (
    CampaignSnapshot,
    can_pause,
    can_start_campaign,
    can_stop,
    can_transition_to_start,
    resolve_scope_constraints,
)
from app.modules.campaigns.schemas import (
    CampaignCreate,
    CampaignDTO,
    CampaignListQuery,
    CampaignStartResponse,
    CampaignStatsDTO,
    CampaignUpdate,
)
from app.packages.contracts.base import DataResponse, PagedMeta, PagedResponse
from app.packages.contracts.enums import AuditResult, CampaignStatus
from app.packages.db.models import Campaign, ScriptVersion

logger = structlog.get_logger("campaigns.service")

# Fields a PUT may mutate directly (status is special-cased: activation is
# reserved for /start so the start guard can never be bypassed).
_UPDATABLE_FIELDS = (
    "name",
    "script_id",
    "active_script_version_id",
    "rule_set_version_id",
    "compliance_profile_id",
    "vicidial_campaign_id",
    "closer_in_group",
    "timezone",
    "dialing",
    "transfer",
    "recording",
    "retention",
)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _to_dto(campaign: Campaign, list_ids: list[str] | None = None) -> CampaignDTO:
    return CampaignDTO(
        id=campaign.id,
        name=campaign.name,
        status=CampaignStatus(campaign.status),
        script_id=campaign.script_id,
        active_script_version_id=campaign.active_script_version_id,
        rule_set_version_id=campaign.rule_set_version_id,
        compliance_profile_id=campaign.compliance_profile_id,
        vicidial_campaign_id=campaign.vicidial_campaign_id,
        closer_in_group=campaign.closer_in_group,
        vicidial_list_ids=list_ids or [],
        timezone=campaign.timezone,
        dialing=campaign.dialing,
        transfer=campaign.transfer,
        recording=campaign.recording,
        retention=campaign.retention,
        version=campaign.version,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


async def _load(
    session: AsyncSession, user: UserContext, campaign_id: uuid.UUID
) -> Campaign:
    campaign = await repo.get_campaign(
        session, campaign_id, resolve_scope_constraints(user)
    )
    if campaign is None:
        raise CampaignNotFoundError()
    return campaign


def _rate(numerator: int, denominator: int) -> float:
    """Fraction rounded to 4 dp; ``0.0`` when there is no denominator."""
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


async def _snapshot_async(
    session: AsyncSession, campaign: Campaign, list_ids: list[str]
) -> CampaignSnapshot:
    ver_status = None
    if campaign.active_script_version_id:
        ver = await session.get(ScriptVersion, campaign.active_script_version_id)
        if ver:
            ver_status = ver.status
    # Caller IDs live in the opaque ``dialing`` config blob rather than a
    # dedicated column, so the start guard reads them from there.
    dialing = campaign.dialing or {}
    caller_ids = dialing.get("callerIds") or dialing.get("caller_ids") or []
    return CampaignSnapshot(
        active_script_version_id=campaign.active_script_version_id,
        script_version_status=ver_status,
        rule_set_version_id=campaign.rule_set_version_id,
        compliance_profile_id=campaign.compliance_profile_id,
        closer_in_group=campaign.closer_in_group,
        vicidial_campaign_id=campaign.vicidial_campaign_id,
        vicidial_list_ids=tuple(list_ids),
        caller_ids=tuple(str(cid) for cid in caller_ids),
    )


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


async def list_campaigns(
    session: AsyncSession,
    user: UserContext,
    query: CampaignListQuery,
) -> PagedResponse[CampaignDTO]:
    campaign_rows, total = await repo.list_campaigns(
        session, query, resolve_scope_constraints(user)
    )
    list_map = await repo.batch_list_ids(session, [c.id for c in campaign_rows])
    total_pages = max(1, (total + query.page_size - 1) // query.page_size)
    return PagedResponse[CampaignDTO](
        data=[_to_dto(c, list_map.get(c.id)) for c in campaign_rows],
        meta=PagedMeta(
            page=query.page,
            page_size=query.page_size,
            total=total,
            total_pages=total_pages,
            sort=query.sort,
            order=query.order,
        ),
    )


async def get_campaign(
    session: AsyncSession, user: UserContext, campaign_id: uuid.UUID
) -> DataResponse[CampaignDTO]:
    campaign = await _load(session, user, campaign_id)
    list_ids = await repo.fetch_list_ids(session, campaign.id)
    return DataResponse[CampaignDTO](data=_to_dto(campaign, list_ids))


async def get_campaign_stats(
    session: AsyncSession, user: UserContext, campaign_id: uuid.UUID
) -> DataResponse[CampaignStatsDTO]:
    """Today's funnel counters + rates for one campaign (PRD FR-11)."""
    await _load(session, user, campaign_id)
    calls_today, contacted, qualified, transferred = await repo.get_campaign_stats(
        session, campaign_id
    )
    return DataResponse[CampaignStatsDTO](
        data=CampaignStatsDTO(
            calls_today=calls_today,
            contact_rate=_rate(contacted, calls_today),
            qualification_rate=_rate(qualified, calls_today),
            transfer_rate=_rate(transferred, calls_today),
        )
    )


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


async def create_campaign(
    session: AsyncSession,
    user: UserContext,
    payload: CampaignCreate,
) -> DataResponse[CampaignDTO]:
    campaign = Campaign(
        name=payload.name,
        status=CampaignStatus.DRAFT.value,
        script_id=payload.script_id,
        active_script_version_id=payload.active_script_version_id,
        rule_set_version_id=payload.rule_set_version_id,
        compliance_profile_id=payload.compliance_profile_id,
        vicidial_campaign_id=payload.vicidial_campaign_id,
        closer_in_group=payload.closer_in_group,
        timezone=payload.timezone,
        dialing=payload.dialing,
        transfer=payload.transfer,
        recording=payload.recording,
        retention=payload.retention,
        version=1,
    )
    await repo.save(session, campaign)

    if payload.vicidial_list_ids:
        await repo.replace_vicidial_lists(
            session, campaign.id, payload.vicidial_list_ids
        )

    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="campaign.create",
        resource_type="campaign",
        resource_id=str(campaign.id),
        result=AuditResult.SUCCESS,
        details={"name": campaign.name},
    )
    await publish_campaign_event(
        session,
        campaign_id=campaign.id,
        event_type=CampaignEventType.CREATED,
        payload={"name": campaign.name, "status": campaign.status},
    )
    await session.commit()

    list_ids = await repo.fetch_list_ids(session, campaign.id)
    logger.info(
        "campaign created", campaign_id=str(campaign.id), actor=str(user.user_id)
    )
    return DataResponse[CampaignDTO](data=_to_dto(campaign, list_ids))


async def update_campaign(
    session: AsyncSession,
    user: UserContext,
    campaign_id: uuid.UUID,
    payload: CampaignUpdate,
) -> DataResponse[CampaignDTO]:
    campaign = await _load(session, user, campaign_id)

    if payload.version is not None and payload.version != campaign.version:
        raise CampaignVersionConflictError()

    data = payload.model_dump(exclude_unset=True)
    data.pop("version", None)

    # Activation is the start guard's job - never a plain field write.
    if data.get("status") == CampaignStatus.ACTIVE:
        raise CampaignInvalidStateError(
            details={"reason": "Use POST /campaigns/{id}/start to activate."}
        )

    for field in _UPDATABLE_FIELDS:
        if field in data:
            setattr(campaign, field, data[field])
    if "status" in data:
        campaign.status = (
            data["status"].value
            if isinstance(data["status"], CampaignStatus)
            else str(data["status"])
        )

    campaign.version += 1

    list_ids: list[str] | None = data.get("vicidial_list_ids")
    if list_ids is not None:
        await repo.replace_vicidial_lists(session, campaign.id, list_ids)

    await repo.save(session, campaign)
    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="campaign.update",
        resource_type="campaign",
        resource_id=str(campaign.id),
        result=AuditResult.SUCCESS,
        details={"version": campaign.version, "fields": sorted(data)},
    )
    await publish_campaign_event(
        session,
        campaign_id=campaign.id,
        event_type=CampaignEventType.UPDATED,
        payload={"version": campaign.version},
    )
    await session.commit()

    if list_ids is None:
        list_ids = await repo.fetch_list_ids(session, campaign.id)
    return DataResponse[CampaignDTO](data=_to_dto(campaign, list_ids))


async def start_campaign(
    session: AsyncSession,
    user: UserContext,
    campaign_id: uuid.UUID,
) -> DataResponse[CampaignStartResponse]:
    """Run the start guard and activate only when every prerequisite exists.

    On failure the caller receives one 409 carrying the *complete* problem list
    (``error.details.problems``) - never the first gap only.
    """
    campaign = await _load(session, user, campaign_id)
    if not can_transition_to_start(campaign.status):
        raise CampaignInvalidStateError(
            details={
                "status": campaign.status,
                "reason": "Campaign is already running.",
            }
        )

    list_ids = await repo.fetch_list_ids(session, campaign.id)
    problems = can_start_campaign(await _snapshot_async(session, campaign, list_ids))
    if problems:
        await write_audit(
            session,
            actor_id=user.user_id,
            actor_role=user.role,
            action="campaign.start",
            resource_type="campaign",
            resource_id=str(campaign.id),
            result=AuditResult.FAILED,
            details={"problems": sorted(problems)},
        )
        await session.commit()
        raise CampaignStartFailedError(problems)

    campaign.status = CampaignStatus.ACTIVE.value
    campaign.version += 1
    await repo.save(session, campaign)
    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="campaign.start",
        resource_type="campaign",
        resource_id=str(campaign.id),
        result=AuditResult.SUCCESS,
        details={"version": campaign.version, "list_ids": list_ids},
    )
    await publish_campaign_event(
        session,
        campaign_id=campaign.id,
        event_type=CampaignEventType.STARTED,
        payload={"status": campaign.status, "version": campaign.version},
    )
    await session.commit()
    logger.info(
        "campaign started", campaign_id=str(campaign.id), actor=str(user.user_id)
    )
    return DataResponse[CampaignStartResponse](
        data=CampaignStartResponse(campaign=_to_dto(campaign, list_ids), problems=[])
    )


async def pause_campaign(
    session: AsyncSession,
    user: UserContext,
    campaign_id: uuid.UUID,
) -> DataResponse[CampaignDTO]:
    campaign = await _load(session, user, campaign_id)
    if not can_pause(campaign.status):
        raise CampaignInvalidStateError(
            details={"status": campaign.status, "reason": "Campaign is not active."}
        )

    campaign.status = CampaignStatus.PAUSED.value
    campaign.version += 1
    await repo.save(session, campaign)
    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="campaign.pause",
        resource_type="campaign",
        resource_id=str(campaign.id),
        result=AuditResult.SUCCESS,
        details={"version": campaign.version},
    )
    await publish_campaign_event(
        session,
        campaign_id=campaign.id,
        event_type=CampaignEventType.PAUSED,
        payload={"status": campaign.status, "version": campaign.version},
    )
    await session.commit()

    list_ids = await repo.fetch_list_ids(session, campaign.id)
    return DataResponse[CampaignDTO](data=_to_dto(campaign, list_ids))


async def stop_campaign(
    session: AsyncSession,
    user: UserContext,
    campaign_id: uuid.UUID,
) -> DataResponse[CampaignDTO]:
    """Stop a running (active) or paused campaign.

    Stopping releases the campaign from the dialer but keeps every binding
    intact, so ``/start`` can bring it back once prerequisites still hold.
    """
    campaign = await _load(session, user, campaign_id)
    if not can_stop(campaign.status):
        raise CampaignInvalidStateError(
            details={"status": campaign.status, "reason": "Campaign is not running."}
        )

    campaign.status = CampaignStatus.STOPPED.value
    campaign.version += 1
    await repo.save(session, campaign)
    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="campaign.stop",
        resource_type="campaign",
        resource_id=str(campaign.id),
        result=AuditResult.SUCCESS,
        details={"version": campaign.version},
    )
    await publish_campaign_event(
        session,
        campaign_id=campaign.id,
        event_type=CampaignEventType.STOPPED,
        payload={"status": campaign.status, "version": campaign.version},
    )
    await session.commit()
    logger.info(
        "campaign stopped", campaign_id=str(campaign.id), actor=str(user.user_id)
    )

    list_ids = await repo.fetch_list_ids(session, campaign.id)
    return DataResponse[CampaignDTO](data=_to_dto(campaign, list_ids))


async def bind_script(
    session: AsyncSession,
    user: UserContext,
    campaign_id: uuid.UUID,
    script_id: uuid.UUID,
    active_script_version_id: uuid.UUID,
) -> DataResponse[CampaignDTO]:
    """Bind an approved script version to a campaign."""
    campaign = await _load(session, user, campaign_id)
    ver = await session.get(ScriptVersion, active_script_version_id)
    if not ver or ver.status not in ("approved", "active"):
        raise CampaignInvalidStateError(
            details={
                "active_script_version_id": str(active_script_version_id),
                "reason": "Script version is not approved or active.",
            }
        )

    campaign.script_id = script_id
    campaign.active_script_version_id = active_script_version_id
    campaign.version += 1
    await repo.save(session, campaign)
    await write_audit(
        session,
        actor_id=user.user_id,
        actor_role=user.role,
        action="campaign.bind_script",
        resource_type="campaign",
        resource_id=str(campaign.id),
        result=AuditResult.SUCCESS,
        details={
            "scriptId": str(script_id),
            "activeScriptVersionId": str(active_script_version_id),
        },
    )
    await session.commit()
    list_ids = await repo.fetch_list_ids(session, campaign.id)
    return DataResponse[CampaignDTO](data=_to_dto(campaign, list_ids))
