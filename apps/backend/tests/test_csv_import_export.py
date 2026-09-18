"""Tests for the leads import wizard, suppression/DNC register and export pipeline.

Covers the frozen wire contracts (camelCase envelopes) for spec 12/14/19/28:
upload -> mapping -> commit (with idempotent re-commit + error report), single-
lead CRUD, suppression add/check/remove/import incl. the VICIdial sync outbox
events, and the export history/download with phone masking for non-PII roles.
"""

from __future__ import annotations

import uuid

from app.core.security import create_access_token
from app.modules.exports.policies import ExportPolicy, build_csv, masked_phone
from app.modules.leads.policies import (
    RowVerdict,
    apply_mapping,
    classify_row,
    missing_required_fields,
    prepare_row,
)
from app.modules.suppression.events import SUPPRESSION_CHANNEL
from app.modules.suppression.policies import (
    parse_expires_at,
    parse_reason,
    resolve_header_map,
)
from app.modules.users_rbac import repository as users_repo
from app.packages.contracts.enums import SuppressionReason, UserStatus
from app.packages.db.models import Lead, User
from app.packages.phone import normalize_us_phone

# ---------------------------------------------------------------------------
# Pure policy tests (no DB / no HTTP)
# ---------------------------------------------------------------------------


def test_normalize_us_phone_variants():
    assert normalize_us_phone("(850) 555-4586") == "18505554586"
    assert normalize_us_phone("+1-202-555-0100") == "12025550100"
    assert normalize_us_phone("1 305 555 0199") == "13055550199"
    assert normalize_us_phone("4045550123") == "14045550123"
    assert normalize_us_phone("not-a-phone") is None
    assert normalize_us_phone("") is None


def test_apply_mapping_splits_system_and_custom():
    row = {"phone": "202-555-0100", "first_name": "New", "notes": "hello"}
    system, custom = apply_mapping(
        row, {"phone": "phone", "first_name": "first_name", "notes": "notes"}
    )
    assert system == {"phone": "202-555-0100", "first_name": "New"}
    assert custom == {"notes": "hello"}
    system, _ = apply_mapping(row, {"first_name": "first_name"})  # no phone
    assert system == {"first_name": "New"}


def test_prepare_row_normalizes_and_validates():
    prepared, reason = prepare_row(
        {"phone": "(404) 555-0101", "first_name": "Amy"},
        {"phone": "phone", "first_name": "first_name"},
    )
    assert prepared is not None
    assert prepared.system["phone"] == "14045550101"
    assert reason is None

    _, reason = prepare_row({"phone": "nope"}, {"phone": "phone"})
    assert reason == "invalid_phone"

    _, reason = prepare_row(
        {"phone": "202-555-0100", "dob": "01/02/1980"},
        {"phone": "phone", "dob": "date_of_birth"},
    )
    assert reason == "invalid_date_of_birth"


def test_missing_required_fields():
    assert missing_required_fields({"first_name": "first_name"}) == ["phone"]
    assert missing_required_fields({"phone": "phone"}) == []


def test_classify_row_priorities_suppression_first():
    verdict = classify_row(
        "13055550199",
        seen_in_file={"13055550199"},
        existing_phones={"13055550199"},
        suppressed_phones={"13055550199"},
    )
    assert verdict == RowVerdict("suppressed", "suppressed_dnc")

    assert classify_row(
        "12025550100", seen_in_file={"12025550100"}, existing_phones=set(), suppressed_phones=set()
    ) == RowVerdict("duplicate", "duplicate_in_file")
    assert classify_row(
        "18505554586", seen_in_file=set(), existing_phones={"18505554586"}, suppressed_phones=set()
    ) == RowVerdict("duplicate", "duplicate_in_system")
    assert classify_row(
        "14045550101", seen_in_file=set(), existing_phones=set(), suppressed_phones=set()
    ) == RowVerdict("valid", None)


def test_suppression_policies():
    assert resolve_header_map(["Phone Number", "Reason", "Notes"]) == {
        "phone": "Phone Number",
        "reason": "Reason",
    }
    assert parse_reason("litigator") == (SuppressionReason.LITIGATOR.value, None)
    assert parse_reason("") == (SuppressionReason.INTERNAL_DNC.value, None)
    assert parse_reason("bogus") == (None, "invalid_reason")
    expiry = parse_expires_at("2030-01-15")
    assert expiry is not None and expiry.tzinfo is not None
    assert parse_expires_at("not-a-date") is None


def test_export_policy_and_masking():
    from app.core.context import UserContext

    admin = UserContext(
        user_id=uuid.uuid4(), tenant_id=None, permissions={"lead.view"}, role="MASTER_ADMIN"
    )
    reporter = UserContext(
        user_id=uuid.uuid4(),
        tenant_id=None,
        permissions={"export.create"},
        role="REPORTING_USER",
    )
    assert ExportPolicy.mask_phone_numbers(admin) is False
    assert ExportPolicy.mask_phone_numbers(reporter) is True

    assert masked_phone("18505554586") == "(850) ***-4586"

    csv_bytes = build_csv(
        [{"phone": "18505554586", "first_name": "Jane"}],
        headers=["phone", "first_name"],
        mask_phone=True,
    )
    assert b"(850) ***-4586" in csv_bytes and b"18505554586" not in csv_bytes
    csv_bytes = build_csv(
        [{"phone": "18505554586", "first_name": "Jane"}],
        headers=["phone", "first_name"],
        mask_phone=False,
    )
    assert b"18505554586" in csv_bytes


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


async def _reporting_headers(seeded) -> dict:
    """Seed a REPORTING_USER (export.* permissions, no PII) + a fresh token."""
    role = None
    uid = uuid.uuid4()
    email = "qa-test-reporter@phonova.io"
    async with seeded["factory"]() as db:
        role = await users_repo.find_role_by_name(db, "REPORTING_USER")
        db.add(
            User(
                id=uid,
                email=email,
                username="qa_reporter",
                hashed_password="$argon2id$placeholder",
                full_name="QA Reporter",
                extension="002",
                is_active=True,
                status=UserStatus.APPROVED.value,
            )
        )
        await db.flush()
        await users_repo.replace_user_roles(db, uid, [role.id])
        await db.commit()
    token, _ = create_access_token({"sub": email})
    return {"Authorization": f"Bearer {token}"}


def _csv(rows: list[list[str]]) -> bytes:
    return "\n".join(",".join(row) for row in rows).encode("utf-8")


# ---------------------------------------------------------------------------
# Lead registry (CRUD + contract)
# ---------------------------------------------------------------------------


async def test_leads_require_authentication(client):
    resp = await client.get("/leads")
    assert resp.status_code == 401


async def test_lead_crud_camel_case(client, seeded):
    resp = await client.post(
        "/leads",
        headers=seeded["headers"],
        json={
            "phone": "(404) 555-0101",
            "firstName": "Amy",
            "lastName": "Smith",
            "email": "amy@x.io",
            "customFields": {"notes": "first lead"},
        },
    )
    assert resp.status_code == 201
    lead = resp.json()["data"]
    assert lead["phone"] == "14045550101"
    assert lead["status"] == "new"
    assert lead["suppressed"] is False
    assert lead["campaignId"] is None
    assert lead["customFields"]["notes"] == "first lead"

    lead_id = lead["id"]
    fetched = await client.get(f"/leads/{lead_id}", headers=seeded["headers"])
    assert fetched.status_code == 200
    assert fetched.json()["data"]["firstName"] == "Amy"

    patched = await client.patch(
        f"/leads/{lead_id}",
        headers=seeded["headers"],
        json={"status": "qualified", "lastName": "King"},
    )
    assert patched.status_code == 200
    data = patched.json()["data"]
    assert data["status"] == "qualified"
    assert data["lastName"] == "King"
    assert data["phone"] == "14045550101"


async def test_lead_create_rejects_bad_phone_and_unknown_campaign(client, seeded):
    bad = await client.post(
        "/leads", headers=seeded["headers"], json={"phone": "not-a-phone"}
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "lead.invalid_phone"

    missing = await client.post(
        "/leads",
        headers=seeded["headers"],
        json={"phone": "404-555-0102", "campaignId": str(uuid.uuid4())},
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "lead.campaign_not_found"


async def test_viewer_cannot_list_leads(client, seeded):
    resp = await client.get("/leads", headers=seeded["viewer_headers"])
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "auth.permission_denied"


# ---------------------------------------------------------------------------
# Import wizard (spec 12 + 14)
# ---------------------------------------------------------------------------

_SOURCE_CSV = [
    ["phone", "first_name", "last_name", "email", "dob", "notes"],
    ["(850) 555-4586", "Jane", "System Dup", "jane@x.com", "1980-01-02", "hi"],
    ["202-555-0100", "New", "Lead", "new@x.com", "1985-03-04", "hello"],
    ["202-555-0100", "Again", "File Dup", "", "1990-01-01", "dup"],
    ["bad-number", "Bad", "Row", "", "", ""],
    ["305-555-0199", "Suppressed", "Person", "", "", ""],
]

_MAPPING = {
    "phone": "phone",
    "first_name": "first_name",
    "last_name": "last_name",
    "email": "email",
    "dob": "date_of_birth",
    "notes": "notes",
}


async def test_import_wizard_end_to_end(client, seeded):
    added = await client.post(
        "/suppression",
        headers=seeded["headers"],
        json={"phone": "305-555-0199", "reason": "complaint"},
    )
    assert added.status_code == 201

    upload = await client.post(
        "/leads/import",
        headers=seeded["headers"],
        files={"file": ("leads.csv", _csv(_SOURCE_CSV), "text/csv")},
    )
    assert upload.status_code == 201
    job = upload.json()["data"]
    assert job["status"] == "mapping"
    assert job["totalRows"] == 5
    assert {c["name"] for c in job["columns"]} == {
        "phone",
        "first_name",
        "last_name",
        "email",
        "dob",
        "notes",
    }
    job_id = job["jobId"]

    mapped = await client.post(
        f"/leads/import/{job_id}/mapping",
        headers=seeded["headers"],
        json={"mapping": _MAPPING},
    )
    assert mapped.status_code == 200
    data = mapped.json()["data"]
    assert data["status"] == "validating"
    assert data["validation"] == {
        "total": 5,
        "valid": 1,
        "invalid": 1,
        "duplicatesFile": 1,
        "duplicatesSystem": 1,
        "suppressed": 1,
    }
    assert data["importedRows"] == 1
    assert data["duplicateRows"] == 2
    assert data["invalidRows"] == 1
    assert data["suppressedRows"] == 1
    assert data["errorReportUrl"] == f"/api/v1/leads/import/{job_id}/errors"

    committed = await client.post(
        f"/leads/import/{job_id}/commit", headers=seeded["headers"]
    )
    assert committed.status_code == 200
    assert committed.json()["data"]["status"] == "completed"
    assert committed.json()["data"]["importedRows"] == 1

    replay = await client.post(
        f"/leads/import/{job_id}/commit", headers=seeded["headers"]
    )
    assert replay.status_code == 200
    assert replay.json()["data"]["status"] == "completed"
    assert replay.json()["data"]["importedRows"] == 1

    listing = await client.get("/leads?search=New", headers=seeded["headers"])
    assert listing.status_code == 200
    names = [l["firstName"] for l in listing.json()["data"]]
    assert "New" in names

    errors = await client.get(
        f"/leads/import/{job_id}/errors", headers=seeded["headers"]
    )
    assert errors.status_code == 200
    assert errors.headers["content-type"].startswith("text/csv")
    body = errors.text
    for reason in (
        "duplicate_in_system",
        "duplicate_in_file",
        "invalid_phone",
        "suppressed_dnc",
    ):
        assert reason in body

    async with seeded["factory"]() as db:
        from sqlalchemy import func, select

        from app.packages.db.models import audit_log_table, outbox_table

        imported = await db.execute(
            select(func.count())
            .select_from(Lead)
            .where(Lead.import_job_id == uuid.UUID(job_id))
        )
        assert imported.scalar_one() == 1

        for event_type in ("lead.import.mapping_saved", "lead.import.committed"):
            event = await db.execute(
                select(func.count()).select_from(outbox_table).where(
                    outbox_table.c.event_type == event_type
                )
            )
            assert event.scalar_one() == 1

        audited = await db.execute(
            select(func.count()).select_from(audit_log_table).where(
                audit_log_table.c.action == "lead.import.commit"
            )
        )
        assert audited.scalar_one() == 1


async def test_import_upload_forbidden_for_viewer(client, seeded):
    resp = await client.post(
        "/leads/import",
        headers=seeded["viewer_headers"],
        files={"file": ("leads.csv", _csv(_SOURCE_CSV[:2]), "text/csv")},
    )
    assert resp.status_code == 403


async def test_import_mapping_requires_phone_column(client, seeded):
    upload = await client.post(
        "/leads/import",
        headers=seeded["headers"],
        files={"file": ("x.csv", _csv(_SOURCE_CSV[:2]), "text/csv")},
    )
    job_id = upload.json()["data"]["jobId"]
    resp = await client.post(
        f"/leads/import/{job_id}/mapping",
        headers=seeded["headers"],
        json={"mapping": {"first_name": "first_name"}},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "lead.import_mapping_invalid"

    resp = await client.post(f"/leads/import/{job_id}/commit", headers=seeded["headers"])
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "lead.import_invalid_state"


# ---------------------------------------------------------------------------
# Suppression / DNC register (spec 19)
# ---------------------------------------------------------------------------


async def test_suppression_add_duplicate_check_remove(client, seeded):
    added = await client.post(
        "/suppression",
        headers=seeded["headers"],
        json={
            "phone": "(404) 555-0199",
            "reason": "litigator",
            "source": "legal",
            "evidenceReference": "CASE-9",
        },
    )
    assert added.status_code == 201
    entry = added.json()["data"]
    assert entry["phone"] == "14045550199"
    assert entry["reason"] == "litigator"
    assert entry["removedAt"] is None
    assert entry["addedBy"] == str(seeded["admin_id"])

    duplicate = await client.post(
        "/suppression",
        headers=seeded["headers"],
        json={"phone": "14045550199"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "suppression.duplicate"

    listing = await client.get(
        "/suppression?phone=14045550199", headers=seeded["headers"]
    )
    assert listing.status_code == 200
    assert listing.json()["meta"]["total"] >= 1

    check = await client.get(
        "/suppression/check?phone=404-555-0199", headers=seeded["headers"]
    )
    assert check.status_code == 200
    data = check.json()["data"]
    assert data["suppressed"] is True
    assert data["reason"] == "litigator"
    assert data["entryId"] == entry["id"]

    removed = await client.delete(
        f"/suppression/{entry['id']}", headers=seeded["headers"]
    )
    assert removed.status_code == 200
    assert removed.json()["data"]["removedAt"] is not None

    after = await client.get(
        "/suppression/check?phone=14045550199", headers=seeded["headers"]
    )
    assert after.json()["data"]["suppressed"] is False

    async with seeded["factory"]() as db:
        from sqlalchemy import func, select

        from app.packages.db.models import audit_log_table, outbox_table

        for event_type, count in (
            ("suppression.added", 1),
            ("suppression.removed", 1),
        ):
            sent = await db.execute(
                select(func.count()).select_from(outbox_table).where(
                    outbox_table.c.channel == SUPPRESSION_CHANNEL,
                    outbox_table.c.event_type == event_type,
                )
            )
            assert sent.scalar_one() == count
        audited = await db.execute(
            select(func.count()).select_from(audit_log_table).where(
                audit_log_table.c.action == "suppression.remove"
            )
        )
        assert audited.scalar_one() == 1


async def test_suppression_marks_existing_lead(client, seeded):
    added = await client.post(
        "/suppression",
        headers=seeded["headers"],
        json={"phone": "1850-555-4586", "reason": "internal_dnc"},
    )
    assert added.status_code == 201

    resp = await client.get(f"/leads/{seeded['lead_id']}", headers=seeded["headers"])
    assert resp.status_code == 200
    lead = resp.json()["data"]
    assert lead["suppressed"] is True
    assert lead["suppressionReason"] == "internal_dnc"


async def test_suppression_import_csv(client, seeded):
    payload = _csv(
        [
            ["phone", "reason"],
            ["202-555-0100", "complaint"],
            ["202-555-0100", "internal_dnc"],
            ["bad-number", "litigator"],
        ]
    )
    resp = await client.post(
        "/suppression/import",
        headers=seeded["headers"],
        files={"file": ("dnc.csv", payload, "text/csv")},
    )
    assert resp.status_code == 201
    assert resp.json()["data"] == {"total": 3, "added": 1, "duplicate": 0, "invalid": 2}

    check = await client.get(
        "/suppression/check?phone=202-555-0100", headers=seeded["headers"]
    )
    assert check.json()["data"]["suppressed"] is True
    assert check.json()["data"]["reason"] == "complaint"

    replay = await client.post(
        "/suppression/import",
        headers=seeded["headers"],
        files={"file": ("dnc.csv", payload, "text/csv")},
    )
    assert replay.status_code == 201
    assert replay.json()["data"] == {"total": 3, "added": 0, "duplicate": 1, "invalid": 2}


async def test_suppression_requires_permissions(client, seeded):
    for method, path, kwargs in (
        ("get", "/suppression", {}),
        ("post", "/suppression", {"json": {"phone": "404-555-0103"}}),
        ("delete", f"/suppression/{uuid.uuid4()}", {}),
    ):
        resp = await getattr(client, method)(path, headers=seeded["viewer_headers"], **kwargs)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Export pipeline (spec 28)
# ---------------------------------------------------------------------------


async def test_export_leads_create_download_and_audit(client, seeded):
    created = await client.post(
        "/exports", headers=seeded["headers"], json={"report": "leads"}
    )
    assert created.status_code == 201
    job = created.json()["data"]
    assert job["status"] == "ready"
    assert job["rowCount"] >= 1
    assert job["downloadUrl"] is not None
    assert job["format"] == "csv"

    download = await client.get(
        f"/exports/{job['id']}/download", headers=seeded["headers"]
    )
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("text/csv")
    assert "first_name" in download.text
    assert "18505554586" in download.text  # admin holds pii.view_full

    history = await client.get("/exports", headers=seeded["headers"])
    assert history.status_code == 200
    assert history.json()["meta"]["total"] >= 1

    async with seeded["factory"]() as db:
        from sqlalchemy import func, select

        from app.packages.db.models import audit_log_table

        audited = await db.execute(
            select(func.count()).select_from(audit_log_table).where(
                audit_log_table.c.action == "export.download"
            )
        )
        assert audited.scalar_one() == 1


async def test_export_masks_phone_for_reporting_user(client, seeded):
    headers = await _reporting_headers(seeded)
    created = await client.post("/exports", headers=headers, json={"report": "leads"})
    assert created.status_code == 201
    job_id = created.json()["data"]["id"]

    download = await client.get(
        f"/exports/{job_id}/download", headers=headers
    )
    assert download.status_code == 200
    assert "(850) ***-4586" in download.text
    assert "18505554586" not in download.text


async def test_export_supports_all_reports_and_validates(client, seeded):
    for report in ("leads", "campaigns", "calls"):
        created = await client.post(
            "/exports", headers=seeded["headers"], json={"report": report}
        )
        assert created.status_code == 201
        assert created.json()["data"]["report"] == report

    unsupported = await client.post(
        "/exports", headers=seeded["headers"], json={"report": "scripts"}
    )
    assert unsupported.status_code == 422
    assert unsupported.json()["error"]["code"] == "export.unsupported_report"

    missing = await client.get(f"/exports/{uuid.uuid4()}", headers=seeded["headers"])
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "export.not_found"


async def test_export_requires_permissions(client, seeded):
    resp = await client.post(
        "/exports", headers=seeded["viewer_headers"], json={"report": "leads"}
    )
    assert resp.status_code == 403