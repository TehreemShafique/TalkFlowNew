"""Repository for compliance_profiles and compliance_rules tables."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def list_profiles(db: AsyncSession) -> list[dict[str, Any]]:
    res = await db.execute(
        text(
            "SELECT id, name, description, jurisdiction, is_active, created_at, updated_at FROM compliance_profiles ORDER BY created_at DESC"
        )
    )
    rows = res.fetchall()
    items = []
    for r in rows:
        items.append(
            {
                "id": r[0],
                "name": r[1],
                "description": r[2],
                "jurisdiction": r[3],
                "is_active": r[4],
                "created_at": r[5],
                "updated_at": r[6],
            }
        )
    return items


async def get_profile(db: AsyncSession, profile_id: uuid.UUID) -> dict[str, Any] | None:
    res = await db.execute(
        text(
            "SELECT id, name, description, jurisdiction, is_active, created_at, updated_at FROM compliance_profiles WHERE id = :id"
        ),
        {"id": profile_id},
    )
    r = res.fetchone()
    if not r:
        return None

    rules_res = await db.execute(
        text(
            "SELECT id, profile_id, rule_key, mode, rationale, updated_at FROM compliance_rules WHERE profile_id = :pid"
        ),
        {"pid": profile_id},
    )
    rules = []
    for r_row in rules_res.fetchall():
        rules.append(
            {
                "id": r_row[0],
                "profile_id": r_row[1],
                "rule_key": r_row[2],
                "mode": r_row[3],
                "rationale": r_row[4],
                "updated_at": r_row[5],
            }
        )

    return {
        "id": r[0],
        "name": r[1],
        "description": r[2],
        "jurisdiction": r[3],
        "is_active": r[4],
        "created_at": r[5],
        "updated_at": r[6],
        "rules": rules,
    }


async def update_rule_mode(
    db: AsyncSession,
    profile_id: uuid.UUID,
    rule_key: str,
    mode: str,
    rationale: str | None,
    user_id: uuid.UUID | None,
) -> None:
    await db.execute(
        text(
            """
            INSERT INTO compliance_rules (id, profile_id, rule_key, mode, rationale, updated_by, updated_at)
            VALUES (gen_random_uuid(), :pid, :rk, :mode, :rat, :uid, clock_timestamp())
            ON CONFLICT (profile_id, rule_key)
            DO UPDATE SET mode = :mode, rationale = :rat, updated_by = :uid, updated_at = clock_timestamp()
            """
        ),
        {
            "pid": profile_id,
            "rk": rule_key,
            "mode": mode,
            "rat": rationale,
            "uid": user_id,
        },
    )
    await db.commit()
