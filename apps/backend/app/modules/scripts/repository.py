"""Data access repository for scripts and script versions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.scripts.schemas import ScriptListQuery
from app.packages.contracts.enums import ScriptStatus
from app.packages.db.models import Campaign, Script, ScriptActivation, ScriptVersion


def _sort_column(sort_key: str | None):
    _SORTABLE = {
        "name": Script.name,
        "status": Script.status,
        "created_at": Script.created_at,
        "updated_at": Script.updated_at,
    }
    return _SORTABLE.get(sort_key or "", Script.created_at)


async def list_scripts(
    session: AsyncSession,
    query: ScriptListQuery,
    constraints: dict[str, Any],
) -> tuple[list[Script], int]:
    """List scripts with filtering, searching, sorting and pagination."""
    _ = constraints
    conditions = []
    if query.status:
        conditions.append(Script.status == query.status.value)
    if query.search and query.search.strip():
        term = f"%{query.search.strip()}%"
        conditions.append(
            (Script.name.ilike(term)) | (Script.description.ilike(term))
        )

    count_stmt = select(func.count(Script.id)).where(and_(*conditions))
    total = (await session.execute(count_stmt)).scalar() or 0

    sort_col = _sort_column(query.sort)
    order_clause = sort_col.asc() if (query.order or "").lower() == "asc" else sort_col.desc()

    offset = (query.page - 1) * query.page_size
    stmt = (
        select(Script)
        .options(selectinload(Script.versions))
        .where(and_(*conditions))
        .order_by(order_clause)
        .offset(offset)
        .limit(query.page_size)
    )

    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_script(session: AsyncSession, script_id: uuid.UUID) -> Script | None:
    """Fetch script by ID with versions loaded."""
    stmt = select(Script).options(selectinload(Script.versions)).where(Script.id == script_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_script_version(
    session: AsyncSession,
    script_id: uuid.UUID,
    version_identifier: str,
) -> ScriptVersion | None:
    """Fetch script version by version integer number or UUID string."""
    try:
        ver_uuid = uuid.UUID(version_identifier)
        stmt = select(ScriptVersion).where(
            and_(ScriptVersion.script_id == script_id, ScriptVersion.id == ver_uuid)
        )
        res = (await session.execute(stmt)).scalar_one_or_none()
        if res:
            return res
    except ValueError:
        pass

    try:
        ver_num = int(version_identifier)
        stmt = select(ScriptVersion).where(
            and_(ScriptVersion.script_id == script_id, ScriptVersion.version == ver_num)
        )
        return (await session.execute(stmt)).scalar_one_or_none()
    except ValueError:
        return None


async def get_versions_for_script(
    session: AsyncSession, script_id: uuid.UUID
) -> list[ScriptVersion]:
    """Fetch all versions for a script ordered by version desc."""
    stmt = (
        select(ScriptVersion)
        .where(ScriptVersion.script_id == script_id)
        .order_by(ScriptVersion.version.desc())
    )
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def create_script(
    session: AsyncSession,
    name: str,
    description: str | None,
    language: str,
    entry_node_id: str,
    nodes: list[dict[str, Any]],
    rule_set_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
) -> tuple[Script, ScriptVersion]:
    """Create a new Script with version 1 in draft status."""
    script = Script(
        name=name,
        description=description,
        language=language,
        current_version=1,
        status=ScriptStatus.DRAFT.value,
        version=1,
    )
    session.add(script)
    await session.flush()

    ver = ScriptVersion(
        script_id=script.id,
        version=1,
        status=ScriptStatus.DRAFT.value,
        entry_node_id=entry_node_id,
        nodes=nodes,
        rule_set_id=rule_set_id,
        created_by=actor_id,
    )
    session.add(ver)
    await session.flush()

    await session.refresh(script)
    script.versions = [ver]
    return script, ver


async def create_script_version(
    session: AsyncSession,
    script: Script,
    nodes: list[dict[str, Any]],
    entry_node_id: str,
    change_note: str | None,
    rule_set_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
) -> ScriptVersion:
    """Create a new draft version for a script."""
    new_ver_num = script.current_version + 1
    script.current_version = new_ver_num
    script.version += 1
    script.updated_at = datetime.now(UTC)

    ver = ScriptVersion(
        script_id=script.id,
        version=new_ver_num,
        status=ScriptStatus.DRAFT.value,
        entry_node_id=entry_node_id,
        nodes=nodes,
        change_note=change_note,
        rule_set_id=rule_set_id,
        created_by=actor_id,
    )
    session.add(ver)
    await session.flush()

    if "versions" in script.__dict__ and isinstance(script.versions, list):
        script.versions.append(ver)

    return ver


async def list_approval_queue(
    session: AsyncSession,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[tuple[ScriptVersion, Script]], int]:
    """Fetch script versions pending approval."""
    stmt_count = select(func.count(ScriptVersion.id)).where(
        ScriptVersion.status == ScriptStatus.PENDING_APPROVAL.value
    )
    total = (await session.execute(stmt_count)).scalar() or 0

    offset = (page - 1) * page_size
    stmt = (
        select(ScriptVersion, Script)
        .join(Script, ScriptVersion.script_id == Script.id)
        .where(ScriptVersion.status == ScriptStatus.PENDING_APPROVAL.value)
        .order_by(ScriptVersion.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )

    result = await session.execute(stmt)
    return list(result.all()), total


async def get_campaigns_for_script_version(
    session: AsyncSession, script_version_id: uuid.UUID
) -> list[str]:
    """Return campaign names bound to this active script version."""
    stmt = select(Campaign.name).where(
        Campaign.active_script_version_id == script_version_id
    )
    result = await session.execute(stmt)
    return [r for r in result.scalars().all() if r]
