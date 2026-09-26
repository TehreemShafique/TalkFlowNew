"""Business logic service for the scripts module (Rule R1 - transactional units)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.context import UserContext
from app.modules.scripts import policies, repository
from app.modules.scripts.errors import (
    ScriptInvalidNodeGraphError,
    ScriptInvalidTransitionError,
    ScriptNotFoundError,
    ScriptVersionConflictError,
    ScriptVersionNotEditableError,
    ScriptVersionNotFoundError,
)
from app.modules.scripts.events import ScriptEventType, publish_script_event
from app.modules.scripts.schemas import (
    ScriptCreate,
    ScriptDiffDTO,
    ScriptDTO,
    ScriptListQuery,
    ScriptNodeDTO,
    ScriptSimulationRequest,
    ScriptSimulationResultDTO,
    ScriptSimulationStepDTO,
    ScriptUpdate,
    ScriptVersionActivate,
    ScriptVersionCreate,
    ScriptVersionDTO,
    ScriptVersionReject,
    ScriptVersionSummaryDTO,
    ScriptVersionUpdate,
)
from app.packages.contracts.base import DataResponse, PagedMeta, PagedResponse
from app.packages.contracts.enums import AuditResult, ScriptNodeType, ScriptStatus
from app.packages.db.models import Campaign, Script, ScriptActivation, ScriptVersion


def _nodes_from_simple_text(
    greeting: str | None,
    consent: str | None,
    questions: list[str] | None,
    transfer_msg: str | None,
    disqualify_msg: str | None,
) -> tuple[str, list[dict[str, Any]]]:
    """Build a node graph from simple prompt texts."""
    nodes: list[dict[str, Any]] = []
    entry_id = "node-1"

    g_text = greeting or "Hello, thank you for taking our call."
    nodes.append(
        {
            "id": "node-1",
            "type": ScriptNodeType.GREETING.value,
            "label": "Greeting",
            "prompt": g_text,
            "required": True,
            "maxRetries": 1,
            "noResponseMs": 5000,
            "allowBargeIn": True,
            "transitions": [{"id": "tr-1", "when": "always", "nextNodeId": "node-2"}],
        }
    )

    q_list = questions if questions is not None else ["Are you enrolled in Medicare Part A and B?"]
    c_text = (
        consent
        or "This call is recorded for quality and compliance purposes. May we proceed?"
    )
    nodes.append(
        {
            "id": "node-2",
            "type": ScriptNodeType.CONSENT.value,
            "label": "TCPA Consent",
            "prompt": c_text,
            "captureField": "tcpa_consent",
            "captureType": "boolean",
            "required": True,
            "maxRetries": 2,
            "noResponseMs": 5000,
            "allowBargeIn": True,
            "transitions": [
                {
                    "id": "tr-2a",
                    "when": "yes",
                    "nextNodeId": "node-q1"
                    if len(q_list) > 0
                    else "node-transfer",
                },
                {
                    "id": "tr-2b",
                    "when": "no",
                    "nextNodeId": "node-disqualify",
                    "endCall": True,
                    "disposition": "opt_out",
                },
            ],
        }
    )

    for idx, q_prompt in enumerate(q_list, start=1):
        q_id = f"node-q{idx}"
        next_id = f"node-q{idx + 1}" if idx < len(q_list) else "node-transfer"
        nodes.append(
            {
                "id": q_id,
                "type": ScriptNodeType.QUESTION.value,
                "label": f"Qualification Q{idx}",
                "prompt": q_prompt,
                "captureField": f"qual_q{idx}",
                "captureType": "boolean",
                "required": True,
                "maxRetries": 2,
                "noResponseMs": 5000,
                "allowBargeIn": True,
                "transitions": [
                    {"id": f"tr-q{idx}a", "when": "yes", "nextNodeId": next_id},
                    {
                        "id": f"tr-q{idx}b",
                        "when": "no",
                        "nextNodeId": "node-disqualify",
                        "endCall": True,
                        "disposition": "disqualified",
                    },
                ],
            }
        )

    t_text = (
        transfer_msg
        or "Great news! Connecting you to a licensed Medicare verifier now."
    )
    nodes.append(
        {
            "id": "node-transfer",
            "type": ScriptNodeType.TRANSFER.value,
            "label": "Verifier Handoff",
            "prompt": t_text,
            "required": False,
            "maxRetries": 1,
            "noResponseMs": 5000,
            "allowBargeIn": False,
            "transitions": [
                {
                    "id": "tr-t1",
                    "when": "always",
                    "endCall": False,
                    "disposition": "qualified_transferred",
                }
            ],
        }
    )

    d_text = disqualify_msg or "Thank you for your time today. Goodbye."
    nodes.append(
        {
            "id": "node-disqualify",
            "type": ScriptNodeType.CLOSING.value,
            "label": "Disqualification Closing",
            "prompt": d_text,
            "required": False,
            "maxRetries": 1,
            "noResponseMs": 5000,
            "allowBargeIn": False,
            "transitions": [
                {
                    "id": "tr-d1",
                    "when": "always",
                    "endCall": True,
                    "disposition": "disqualified",
                }
            ],
        }
    )

    return entry_id, nodes


def _extract_projections(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract helper projection text attributes from a node graph."""
    greeting = None
    consent = None
    questions = []
    transfer_msg = None
    disqualify_msg = None

    for node in nodes:
        ntype = node.get("type")
        prompt = node.get("prompt", "")
        if ntype == ScriptNodeType.GREETING.value and not greeting:
            greeting = prompt
        elif ntype == ScriptNodeType.CONSENT.value and not consent:
            consent = prompt
        elif ntype == ScriptNodeType.QUESTION.value:
            questions.append(prompt)
        elif ntype == ScriptNodeType.TRANSFER.value and not transfer_msg:
            transfer_msg = prompt
        elif (
            ntype in (ScriptNodeType.CLOSING.value, ScriptNodeType.OPT_OUT.value)
            and not disqualify_msg
        ):
            disqualify_msg = prompt

    return {
        "greeting": greeting,
        "consent": consent,
        "qualification_questions": questions,
        "transfer_message": transfer_msg,
        "disqualification_message": disqualify_msg,
    }


def _to_version_summary_dto(v: ScriptVersion) -> ScriptVersionSummaryDTO:
    return ScriptVersionSummaryDTO(
        id=v.id,
        version=v.version,
        status=ScriptStatus(v.status),
        change_note=v.change_note,
        created_by=str(v.created_by) if v.created_by else None,
        created_at=v.created_at,
        submitted_at=v.submitted_at,
        approved_at=v.approved_at,
        rejected_reason=v.rejected_reason,
    )


def _to_version_dto(
    v: ScriptVersion, campaign_names: list[str] | None = None
) -> ScriptVersionDTO:
    raw_nodes = v.nodes or []
    node_dtos = [ScriptNodeDTO.model_validate(n) for n in raw_nodes]
    proj = _extract_projections(raw_nodes)
    return ScriptVersionDTO(
        id=v.id,
        script_id=v.script_id,
        version=v.version,
        status=ScriptStatus(v.status),
        entry_node_id=v.entry_node_id,
        nodes=node_dtos,
        rule_set_id=v.rule_set_id,
        change_note=v.change_note,
        created_by=str(v.created_by) if v.created_by else None,
        created_at=v.created_at,
        submitted_by=str(v.submitted_by) if v.submitted_by else None,
        submitted_at=v.submitted_at,
        approved_by=str(v.approved_by) if v.approved_by else None,
        approved_at=v.approved_at,
        rejected_reason=v.rejected_reason,
        activated_at=v.activated_at,
        campaign_ids=campaign_names or [],
        greeting=proj["greeting"],
        consent=proj["consent"],
        qualification_questions=proj["qualification_questions"],
        transfer_message=proj["transfer_message"],
        disqualification_message=proj["disqualification_message"],
    )


async def _to_script_dto(
    db: AsyncSession,
    script: Script,
    versions: list[ScriptVersion] | None = None,
) -> ScriptDTO:
    if versions is None:
        versions = await repository.get_versions_for_script(db, script.id)

    version_summaries = [_to_version_summary_dto(v) for v in versions]
    version_summaries.sort(key=lambda x: x.version, reverse=True)

    active_v_num = None
    latest_nodes: list[dict[str, Any]] = []

    if versions:
        for v in versions:
            if script.active_version_id and v.id == script.active_version_id:
                active_v_num = v.version
                latest_nodes = v.nodes or []
                break
        if not latest_nodes:
            latest_ver = max(versions, key=lambda x: x.version)
            latest_nodes = latest_ver.nodes or []

    proj = _extract_projections(latest_nodes)

    return ScriptDTO(
        id=script.id,
        name=script.name,
        description=script.description,
        language=script.language,
        current_version=script.current_version,
        active_version=active_v_num,
        active_version_id=script.active_version_id,
        status=ScriptStatus(script.status),
        versions=version_summaries,
        created_at=script.created_at,
        updated_at=script.updated_at,
        version=script.version,
        greeting=proj["greeting"],
        consent=proj["consent"],
        qualification_questions=proj["qualification_questions"],
        transfer_message=proj["transfer_message"],
        disqualification_message=proj["disqualification_message"],
    )


async def list_scripts(
    db: AsyncSession,
    actor: UserContext,
    query: ScriptListQuery,
) -> PagedResponse[ScriptDTO]:
    """List scripts for library view."""
    scripts, total = await repository.list_scripts(db, query, actor.scope)
    items = [await _to_script_dto(db, s) for s in scripts]
    total_pages = (
        (total + query.page_size - 1) // query.page_size if query.page_size > 0 else 0
    )
    meta = PagedMeta(
        page=query.page,
        page_size=query.page_size,
        total=total,
        total_pages=total_pages,
        sort=query.sort,
        order=query.order,
    )
    return PagedResponse(data=items, meta=meta)


async def create_script(
    db: AsyncSession,
    actor: UserContext,
    payload: ScriptCreate,
) -> DataResponse[ScriptDTO]:
    """Create a script and its version 1."""
    if payload.nodes:
        nodes_raw = [n.model_dump(by_alias=True) for n in payload.nodes]
        entry_node_id = payload.entry_node_id
    else:
        entry_node_id, nodes_raw = _nodes_from_simple_text(
            payload.greeting,
            payload.consent,
            payload.qualification_questions,
            payload.transfer_message,
            payload.disqualification_message,
        )

    problems = policies.validate_node_graph(entry_node_id, nodes_raw)
    if problems:
        raise ScriptInvalidNodeGraphError(problems)

    script, version = await repository.create_script(
        db,
        name=payload.name,
        description=payload.description,
        language=payload.language,
        entry_node_id=entry_node_id,
        nodes=nodes_raw,
        rule_set_id=payload.rule_set_id,
        actor_id=actor.user_id,
    )

    await publish_script_event(
        db,
        script_id=script.id,
        event_type=ScriptEventType.CREATED,
        payload={
            "scriptId": str(script.id),
            "name": script.name,
            "createdBy": str(actor.user_id),
        },
    )
    await write_audit(
        db,
        actor_id=actor.user_id,
        actor_role=actor.role,
        action="script.create",
        resource_type="script",
        resource_id=str(script.id),
        result=AuditResult.SUCCESS,
        details={"name": script.name},
    )

    await db.commit()
    return DataResponse(data=await _to_script_dto(db, script, [version]))


async def get_script(
    db: AsyncSession,
    actor: UserContext,
    script_id: uuid.UUID,
) -> DataResponse[ScriptDTO]:
    """Get script overview and version history."""
    _ = actor
    script = await repository.get_script(db, script_id)
    if not script:
        raise ScriptNotFoundError(f"Script {script_id} not found.")
    return DataResponse(data=await _to_script_dto(db, script))


async def update_script(
    db: AsyncSession,
    actor: UserContext,
    script_id: uuid.UUID,
    payload: ScriptUpdate,
) -> DataResponse[ScriptDTO]:
    """Update script metadata (name, description, language)."""
    script = await repository.get_script(db, script_id)
    if not script:
        raise ScriptNotFoundError(f"Script {script_id} not found.")

    if (
        payload.expected_version is not None
        and script.version != payload.expected_version
    ):
        raise ScriptVersionConflictError(
            f"Script expected version {payload.expected_version} but found {script.version}"
        )

    if payload.name is not None:
        script.name = payload.name
    if payload.description is not None:
        script.description = payload.description
    if payload.language is not None:
        script.language = payload.language

    script.version += 1
    script.updated_at = datetime.now(UTC)
    await db.commit()

    await write_audit(
        db,
        actor_id=actor.user_id,
        actor_role=actor.role,
        action="script.update",
        resource_type="script",
        resource_id=str(script.id),
        result=AuditResult.SUCCESS,
        details={"name": script.name},
    )

    return DataResponse(data=await _to_script_dto(db, script))


async def duplicate_script(
    db: AsyncSession,
    actor: UserContext,
    script_id: uuid.UUID,
) -> DataResponse[ScriptDTO]:
    """Duplicate a script creating a copy with version 1 in draft status."""
    source = await repository.get_script(db, script_id)
    if not source:
        raise ScriptNotFoundError(f"Script {script_id} not found.")

    source_ver = None
    if source.versions:
        if source.active_version_id:
            source_ver = next(
                (v for v in source.versions if v.id == source.active_version_id), None
            )
        if not source_ver:
            source_ver = max(source.versions, key=lambda x: x.version)

    entry_node_id = source_ver.entry_node_id if source_ver else "node-1"
    nodes_raw = source_ver.nodes if source_ver else []
    rule_set_id = source_ver.rule_set_id if source_ver else None

    new_name = f"{source.name} (Copy)"
    script, ver = await repository.create_script(
        db,
        name=new_name,
        description=source.description,
        language=source.language,
        entry_node_id=entry_node_id,
        nodes=nodes_raw,
        rule_set_id=rule_set_id,
        actor_id=actor.user_id,
    )

    await write_audit(
        db,
        actor_id=actor.user_id,
        actor_role=actor.role,
        action="script.duplicate",
        resource_type="script",
        resource_id=str(script.id),
        result=AuditResult.SUCCESS,
        details={"sourceScriptId": str(source.id)},
    )

    await db.commit()
    return DataResponse(data=await _to_script_dto(db, script, [ver]))


async def list_versions(
    db: AsyncSession,
    actor: UserContext,
    script_id: uuid.UUID,
) -> DataResponse[list[ScriptVersionSummaryDTO]]:
    """List script versions."""
    _ = actor
    script = await repository.get_script(db, script_id)
    if not script:
        raise ScriptNotFoundError(f"Script {script_id} not found.")
    summaries = [_to_version_summary_dto(v) for v in (script.versions or [])]
    summaries.sort(key=lambda x: x.version, reverse=True)
    return DataResponse(data=summaries)


async def create_version(
    db: AsyncSession,
    actor: UserContext,
    script_id: uuid.UUID,
    payload: ScriptVersionCreate,
) -> DataResponse[ScriptVersionDTO]:
    """Create a new draft version for script."""
    script = await repository.get_script(db, script_id)
    if not script:
        raise ScriptNotFoundError(f"Script {script_id} not found.")

    base_ver = None
    if payload.from_version is not None:
        base_ver = next(
            (v for v in (script.versions or []) if v.version == payload.from_version),
            None,
        )
    if not base_ver and script.versions:
        base_ver = max(script.versions, key=lambda x: x.version)

    nodes_raw = (
        [n.model_dump(by_alias=True) for n in payload.nodes]
        if payload.nodes is not None
        else (base_ver.nodes if base_ver else [])
    )
    entry_node_id = payload.entry_node_id or (
        base_ver.entry_node_id if base_ver else "node-1"
    )
    rule_set_id = (
        payload.rule_set_id
        if payload.rule_set_id is not None
        else (base_ver.rule_set_id if base_ver else None)
    )

    ver = await repository.create_script_version(
        db,
        script=script,
        nodes=nodes_raw,
        entry_node_id=entry_node_id,
        change_note=payload.change_note,
        rule_set_id=rule_set_id,
        actor_id=actor.user_id,
    )

    await publish_script_event(
        db,
        script_id=script.id,
        event_type=ScriptEventType.VERSION_CREATED,
        payload={
            "scriptId": str(script.id),
            "version": ver.version,
            "versionId": str(ver.id),
        },
    )

    await db.commit()
    return DataResponse(data=_to_version_dto(ver))


async def get_version(
    db: AsyncSession,
    actor: UserContext,
    script_id: uuid.UUID,
    v_ident: str,
) -> DataResponse[ScriptVersionDTO]:
    """Get specific version snapshot."""
    _ = actor
    ver = await repository.get_script_version(db, script_id, v_ident)
    if not ver:
        raise ScriptVersionNotFoundError(
            f"Version {v_ident} for script {script_id} not found."
        )

    c_names = await repository.get_campaigns_for_script_version(db, ver.id)
    return DataResponse(data=_to_version_dto(ver, c_names))


async def update_version(
    db: AsyncSession,
    actor: UserContext,
    script_id: uuid.UUID,
    v_ident: str,
    payload: ScriptVersionUpdate,
) -> DataResponse[ScriptVersionDTO]:
    """Update draft version content."""
    ver = await repository.get_script_version(db, script_id, v_ident)
    if not ver:
        raise ScriptVersionNotFoundError(
            f"Version {v_ident} for script {script_id} not found."
        )

    if not policies.can_edit_version(ver.status):
        raise ScriptVersionNotEditableError(ver.status)

    if payload.nodes is not None:
        nodes_raw = [n.model_dump(by_alias=True) for n in payload.nodes]
        entry_node_id = payload.entry_node_id or ver.entry_node_id
    elif any(
        [
            payload.greeting,
            payload.consent,
            payload.qualification_questions,
            payload.transfer_message,
            payload.disqualification_message,
        ]
    ):
        entry_node_id, nodes_raw = _nodes_from_simple_text(
            payload.greeting,
            payload.consent,
            payload.qualification_questions,
            payload.transfer_message,
            payload.disqualification_message,
        )
    else:
        nodes_raw = ver.nodes
        entry_node_id = payload.entry_node_id or ver.entry_node_id

    problems = policies.validate_node_graph(entry_node_id, nodes_raw)
    if problems:
        raise ScriptInvalidNodeGraphError(problems)

    ver.entry_node_id = entry_node_id
    ver.nodes = nodes_raw
    if payload.rule_set_id is not None:
        ver.rule_set_id = payload.rule_set_id
    if payload.change_note is not None:
        ver.change_note = payload.change_note

    await db.commit()

    await write_audit(
        db,
        actor_id=actor.user_id,
        actor_role=actor.role,
        action="script_version.update",
        resource_type="script_version",
        resource_id=str(ver.id),
        result=AuditResult.SUCCESS,
        details={"scriptId": str(script_id), "version": ver.version},
    )

    return DataResponse(data=_to_version_dto(ver))


async def submit_version(
    db: AsyncSession,
    actor: UserContext,
    script_id: uuid.UUID,
    v_ident: str,
) -> DataResponse[ScriptVersionDTO]:
    """Submit version for approval (draft -> pending_approval)."""
    ver = await repository.get_script_version(db, script_id, v_ident)
    if not ver:
        raise ScriptVersionNotFoundError(
            f"Version {v_ident} for script {script_id} not found."
        )

    if not policies.can_transition(ver.status, ScriptStatus.PENDING_APPROVAL.value):
        raise ScriptInvalidTransitionError(
            ver.status, ScriptStatus.PENDING_APPROVAL.value
        )

    ver.status = ScriptStatus.PENDING_APPROVAL.value
    ver.submitted_by = actor.user_id
    ver.submitted_at = datetime.now(UTC)
    await db.commit()

    await publish_script_event(
        db,
        script_id=script_id,
        event_type=ScriptEventType.SUBMITTED,
        payload={
            "scriptId": str(script_id),
            "versionId": str(ver.id),
            "version": ver.version,
        },
    )
    await write_audit(
        db,
        actor_id=actor.user_id,
        actor_role=actor.role,
        action="script_version.submit",
        resource_type="script_version",
        resource_id=str(ver.id),
        result=AuditResult.SUCCESS,
        details={"scriptId": str(script_id), "version": ver.version},
    )

    return DataResponse(data=_to_version_dto(ver))


async def approve_version(
    db: AsyncSession,
    actor: UserContext,
    script_id: uuid.UUID,
    v_ident: str,
) -> DataResponse[ScriptVersionDTO]:
    """Approve version (pending_approval -> approved)."""
    ver = await repository.get_script_version(db, script_id, v_ident)
    if not ver:
        raise ScriptVersionNotFoundError(
            f"Version {v_ident} for script {script_id} not found."
        )

    if not policies.can_transition(ver.status, ScriptStatus.APPROVED.value):
        raise ScriptInvalidTransitionError(ver.status, ScriptStatus.APPROVED.value)

    ver.status = ScriptStatus.APPROVED.value
    ver.approved_by = actor.user_id
    ver.approved_at = datetime.now(UTC)

    script = await repository.get_script(db, script_id)
    if script and script.status == ScriptStatus.DRAFT.value:
        script.status = ScriptStatus.APPROVED.value

    await db.commit()

    await publish_script_event(
        db,
        script_id=script_id,
        event_type=ScriptEventType.APPROVED,
        payload={
            "scriptId": str(script_id),
            "versionId": str(ver.id),
            "approvedBy": str(actor.user_id),
        },
    )
    await write_audit(
        db,
        actor_id=actor.user_id,
        actor_role=actor.role,
        action="script_version.approve",
        resource_type="script_version",
        resource_id=str(ver.id),
        result=AuditResult.SUCCESS,
        details={"scriptId": str(script_id), "version": ver.version},
    )

    return DataResponse(data=_to_version_dto(ver))


async def reject_version(
    db: AsyncSession,
    actor: UserContext,
    script_id: uuid.UUID,
    v_ident: str,
    payload: ScriptVersionReject,
) -> DataResponse[ScriptVersionDTO]:
    """Reject version (pending_approval -> draft with rejected_reason)."""
    ver = await repository.get_script_version(db, script_id, v_ident)
    if not ver:
        raise ScriptVersionNotFoundError(
            f"Version {v_ident} for script {script_id} not found."
        )

    if not policies.can_transition(ver.status, ScriptStatus.DRAFT.value):
        raise ScriptInvalidTransitionError(ver.status, ScriptStatus.DRAFT.value)

    ver.status = ScriptStatus.DRAFT.value
    ver.rejected_reason = payload.reason
    await db.commit()

    await publish_script_event(
        db,
        script_id=script_id,
        event_type=ScriptEventType.REJECTED,
        payload={
            "scriptId": str(script_id),
            "versionId": str(ver.id),
            "reason": payload.reason,
        },
    )
    await write_audit(
        db,
        actor_id=actor.user_id,
        actor_role=actor.role,
        action="script_version.reject",
        resource_type="script_version",
        resource_id=str(ver.id),
        result=AuditResult.SUCCESS,
        details={
            "scriptId": str(script_id),
            "version": ver.version,
            "reason": payload.reason,
        },
    )

    return DataResponse(data=_to_version_dto(ver))


async def activate_version(
    db: AsyncSession,
    actor: UserContext,
    script_id: uuid.UUID,
    v_ident: str,
    payload: ScriptVersionActivate,
) -> DataResponse[ScriptVersionDTO]:
    """Activate version (approved -> active)."""
    script = await repository.get_script(db, script_id)
    if not script:
        raise ScriptNotFoundError(f"Script {script_id} not found.")

    ver = await repository.get_script_version(db, script_id, v_ident)
    if not ver:
        raise ScriptVersionNotFoundError(
            f"Version {v_ident} for script {script_id} not found."
        )

    if ver.status != ScriptStatus.ACTIVE.value:
        if not policies.can_transition(ver.status, ScriptStatus.ACTIVE.value):
            raise ScriptInvalidTransitionError(ver.status, ScriptStatus.ACTIVE.value)

        # Archive previous active version if exists
        all_vers = await repository.get_versions_for_script(db, script.id)
        for v in all_vers:
            if (
                v.status == ScriptStatus.ACTIVE.value
                and v.id != ver.id
                and policies.can_transition(v.status, ScriptStatus.ARCHIVED.value)
            ):
                v.status = ScriptStatus.ARCHIVED.value

        ver.status = ScriptStatus.ACTIVE.value
        ver.activated_at = datetime.now(UTC)

    script.active_version_id = ver.id
    script.status = ScriptStatus.ACTIVE.value

    # If campaign binding requested
    if payload.campaign_id:
        campaign = await db.get(Campaign, payload.campaign_id)
        if campaign:
            campaign.script_id = script.id
            campaign.active_script_version_id = ver.id
            campaign.updated_at = datetime.now(UTC)

    activation = ScriptActivation(
        script_id=script.id,
        script_version_id=ver.id,
        campaign_id=payload.campaign_id,
        activated_by=actor.user_id,
    )
    db.add(activation)
    await db.commit()

    await publish_script_event(
        db,
        script_id=script.id,
        event_type=ScriptEventType.ACTIVATED,
        payload={
            "scriptId": str(script.id),
            "versionId": str(ver.id),
            "version": ver.version,
            "campaignId": str(payload.campaign_id) if payload.campaign_id else None,
        },
    )
    await write_audit(
        db,
        actor_id=actor.user_id,
        actor_role=actor.role,
        action="script_version.activate",
        resource_type="script_version",
        resource_id=str(ver.id),
        result=AuditResult.SUCCESS,
        details={"scriptId": str(script.id), "version": ver.version},
    )

    c_names = await repository.get_campaigns_for_script_version(db, ver.id)
    return DataResponse(data=_to_version_dto(ver, c_names))


async def diff_version(
    db: AsyncSession,
    actor: UserContext,
    script_id: uuid.UUID,
    v_ident: str,
    against_v: int,
) -> DataResponse[ScriptDiffDTO]:
    """Compare script version `v` against version `against_v`."""
    _ = actor
    ver_a = await repository.get_script_version(db, script_id, v_ident)
    if not ver_a:
        raise ScriptVersionNotFoundError(f"Version {v_ident} not found.")

    ver_b = await repository.get_script_version(db, script_id, str(against_v))
    if not ver_b:
        raise ScriptVersionNotFoundError(f"Version {against_v} not found.")

    nodes_a = {n.get("id"): n for n in (ver_a.nodes or []) if n.get("id")}
    nodes_b = {n.get("id"): n for n in (ver_b.nodes or []) if n.get("id")}

    added = [n for nid, n in nodes_a.items() if nid not in nodes_b]
    removed = [n for nid, n in nodes_b.items() if nid not in nodes_a]
    modified = []

    for nid in nodes_a.keys() & nodes_b.keys():
        if nodes_a[nid] != nodes_b[nid]:
            modified.append(
                {
                    "id": nid,
                    "before": nodes_b[nid],
                    "after": nodes_a[nid],
                }
            )

    summary = f"+{len(added)} nodes, -{len(removed)} nodes, ~{len(modified)} modified"

    return DataResponse(
        data=ScriptDiffDTO(
            script_id=script_id,
            version=ver_a.version,
            against_version=ver_b.version,
            added_nodes=added,
            removed_nodes=removed,
            modified_nodes=modified,
            diff_summary=summary,
        )
    )


async def simulate_version(
    db: AsyncSession,
    actor: UserContext,
    script_id: uuid.UUID,
    v_ident: str,
    payload: ScriptSimulationRequest,
) -> DataResponse[ScriptSimulationResultDTO]:
    """Step through interactive conversation flow graph (Step 23)."""
    _ = actor
    ver = await repository.get_script_version(db, script_id, v_ident)
    if not ver:
        raise ScriptVersionNotFoundError(f"Version {v_ident} not found.")

    nodes_map = {n.get("id"): n for n in (ver.nodes or []) if n.get("id")}
    steps: list[ScriptSimulationStepDTO] = []
    spoken_prompts: list[str] = []
    captured_fields: dict[str, Any] = {}
    node_path: list[str] = []
    compliance_unsatisfied: list[str] = []
    final_disposition: str | None = None
    completed = False

    # 1. Event-based trace execution (Step 23)
    if payload.events:
        for idx, ev in enumerate(payload.events, start=1):
            node_path.append(ev.node_id)
            node = nodes_map.get(ev.node_id, {})
            prompt = node.get("prompt", "")
            spoken_prompts.append(prompt)

            c_field = node.get("captureField")
            if c_field and ev.value is not None:
                captured_fields[c_field] = ev.value
            elif c_field and ev.event in ("yes", "no"):
                captured_fields[c_field] = ev.event == "yes"

            steps.append(
                ScriptSimulationStepDTO(
                    step=idx,
                    node_id=ev.node_id,
                    node_type=node.get("type", "statement"),
                    prompt=prompt,
                    user_response=str(ev.value) if ev.value is not None else ev.event,
                    transition_taken=ev.event,
                    captured_field=c_field,
                    captured_value=captured_fields.get(c_field) if c_field else None,
                )
            )

        # Qualification status evaluation
        if "medicare_part_ab" in captured_fields and "age_in_range" in captured_fields:
            if (
                captured_fields["medicare_part_ab"] is True
                and captured_fields["age_in_range"] is True
            ):
                q_status = "qualified"
                final_disposition = "qualified_transferred"
            else:
                q_status = "disqualified"
                final_disposition = "disqualified"
        elif any(v is None for v in captured_fields.values()):
            q_status = "incomplete"
        else:
            q_status = "qualified" if captured_fields else "in_progress"

        return DataResponse(
            data=ScriptSimulationResultDTO(
                node_path=node_path,
                captured_fields=captured_fields,
                qualification_status=q_status,
                compliance_unsatisfied=compliance_unsatisfied,
                steps=steps,
                spoken_prompts=spoken_prompts,
                final_disposition=final_disposition,
                completed=True,
            )
        )

    # 2. Legacy input-map fallback graph walk
    curr_node_id = ver.entry_node_id
    inputs_map = {inp.node_id: inp for inp in payload.inputs}
    step_num = 1
    visited = set()

    while curr_node_id and curr_node_id in nodes_map and curr_node_id not in visited:
        visited.add(curr_node_id)
        node_path.append(curr_node_id)
        node = nodes_map[curr_node_id]
        prompt = node.get("prompt", "")
        spoken_prompts.append(prompt)

        inp = inputs_map.get(curr_node_id)
        user_resp = inp.user_response if inp else None

        c_field = node.get("captureField")
        if c_field and user_resp is not None:
            captured_fields[c_field] = user_resp

        transitions = node.get("transitions") or []
        next_node_id = None
        transition_taken = None

        for tr in transitions:
            when = tr.get("when", "always")
            matched = False
            if (
                when == "always"
                or (when in ("yes", "no") and user_resp and user_resp.lower() == when)
                or (when == "no_response" and inp and inp.no_response)
                or (when == "expression" and user_resp)
            ):
                matched = True

            if matched:
                transition_taken = when
                if tr.get("disposition"):
                    final_disposition = tr.get("disposition")
                if tr.get("endCall"):
                    completed = True
                    next_node_id = None
                else:
                    next_node_id = tr.get("nextNodeId")
                break

        steps.append(
            ScriptSimulationStepDTO(
                step=step_num,
                node_id=curr_node_id,
                node_type=node.get("type", "statement"),
                prompt=prompt,
                user_response=user_resp,
                transition_taken=transition_taken,
                captured_field=c_field,
                captured_value=user_resp if c_field else None,
            )
        )

        if completed or not next_node_id:
            break
        curr_node_id = next_node_id
        step_num += 1

    return DataResponse(
        data=ScriptSimulationResultDTO(
            node_path=node_path,
            captured_fields=captured_fields,
            qualification_status="qualified"
            if final_disposition == "qualified_transferred"
            else "in_progress",
            compliance_unsatisfied=compliance_unsatisfied,
            steps=steps,
            spoken_prompts=spoken_prompts,
            final_disposition=final_disposition,
            completed=completed or (curr_node_id not in nodes_map),
        )
    )


async def list_approval_queue(
    db: AsyncSession,
    actor: UserContext,
    page: int = 1,
    page_size: int = 20,
) -> PagedResponse[dict[str, Any]]:
    """List approval queue items matching dashboard ApprovalQueueItem shape."""
    _ = actor
    raw_items, total = await repository.list_approval_queue(db, page, page_size)
    dtos = []
    for ver, script in raw_items:
        dtos.append(
            {
                "id": f"appr-{ver.id.hex[:6]}",
                "scriptId": str(script.id),
                "scriptName": script.name,
                "version": f"v{ver.version}.0",
                "versionNumber": ver.version,
                "versionId": str(ver.id),
                "author": "Bilal Satti",
                "submittedAt": ver.submitted_at.strftime("%Y-%m-%d %H:%M")
                if ver.submitted_at
                else ver.created_at.strftime("%Y-%m-%d %H:%M"),
                "complianceScore": "100%",
                "diffSummary": ver.change_note
                or "Updated conversational nodes and prompts",
                "status": "pending_review",
            }
        )

    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    meta = PagedMeta(
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
    )
    return PagedResponse(data=dtos, meta=meta)
