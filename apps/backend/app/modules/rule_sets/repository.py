"""DB repository for rule_sets and rule_set_versions tables."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


async def list_rule_sets(db: AsyncSession) -> list[dict[str, Any]]:
    from sqlalchemy import text

    result = await db.execute(
        text(
            "SELECT id, name, description, current_version, active_version_id, "
            "status, created_at, updated_at FROM rule_sets ORDER BY created_at DESC"
        )
    )
    rows = result.fetchall()
    items = []
    for r in rows:
        items.append(
            {
                "id": r[0],
                "name": r[1],
                "description": r[2],
                "current_version": r[3],
                "active_version_id": r[4],
                "status": r[5],
                "created_at": r[6],
                "updated_at": r[7],
            }
        )
    return items


async def get_rule_set(
    db: AsyncSession, rule_set_id: uuid.UUID
) -> dict[str, Any] | None:
    from sqlalchemy import text

    result = await db.execute(
        text(
            "SELECT id, name, description, current_version, active_version_id, status, created_at, updated_at FROM rule_sets WHERE id = :id"
        ),
        {"id": rule_set_id},
    )
    r = result.fetchone()
    if not r:
        return None
    return {
        "id": r[0],
        "name": r[1],
        "description": r[2],
        "current_version": r[3],
        "active_version_id": r[4],
        "status": r[5],
        "created_at": r[6],
        "updated_at": r[7],
    }


async def create_rule_set(
    db: AsyncSession,
    name: str,
    description: str | None,
    rules: dict,
    disqualification_reasons: dict,
) -> dict[str, Any]:
    from sqlalchemy import text

    rs_id = uuid.uuid4()
    ver_id = uuid.uuid4()

    await db.execute(
        text(
            "INSERT INTO rule_sets (id, name, description, status) VALUES (:id, :name, :desc, 'approved')"
        ),
        {"id": rs_id, "name": name, "desc": description},
    )

    import json

    await db.execute(
        text(
            """
            INSERT INTO rule_set_versions (id, rule_set_id, version, status, rules, disqualification_reasons)
            VALUES (:id, :rs_id, 1, 'approved', :rules::jsonb, :reasons::jsonb)
            """
        ),
        {
            "id": ver_id,
            "rs_id": rs_id,
            "rules": json.dumps(rules),
            "reasons": json.dumps(disqualification_reasons),
        },
    )
    await db.execute(
        text("UPDATE rule_sets SET active_version_id = :ver_id WHERE id = :id"),
        {"ver_id": ver_id, "id": rs_id},
    )
    await db.commit()
    return await get_rule_set(db, rs_id)  # type: ignore
