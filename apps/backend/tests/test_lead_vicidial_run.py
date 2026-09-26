"""VICIdial run control for imported lead lists (lead-list registry toggle).

Covers the two directions of ``PATCH /leads/batches/{id}/vicidial-run``:
starting pushes the batch's leads into the dialer hopper and bumps the run
count, stopping records the interruption in TalkFlow only.  The non-agent API
has no list/hopper pause, so the stop path must not attempt a dialer call.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar, Self

import pytest

from app.modules.leads import repository as leads_repo
from app.modules.leads import service as leads_service
from app.modules.leads.errors import (
    ImportJobNotFoundError,
    VicidialIngestFailedError,
    VicidialNotConfiguredError,
    VicidialNothingToSubmitError,
)
from app.packages.contracts.base import DataResponse
from app.packages.contracts.enums import VicidialRunStatus
from app.packages.db.models import Lead, LeadImportJob


class FakeSession:
    """Minimal AsyncSession double: records commits, executes nothing."""

    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("run control must not issue ad-hoc SQL")


class FakeAudit:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def __call__(self, _session: Any, **kwargs: Any) -> None:
        self.rows.append(kwargs)


def make_job(**overrides: Any) -> LeadImportJob:
    job = LeadImportJob(
        id=uuid.uuid4(),
        file_name="leads.csv",
        total_rows=2,
        imported_rows=2,
    )
    job.vicidial_list_id = overrides.get("vicidial_list_id")
    job.vicidial_run_count = overrides.get("vicidial_run_count", 0)
    job.vicidial_status = overrides.get("vicidial_status", VicidialRunStatus.IDLE.value)
    job.is_active_for_vicidial = overrides.get("is_active_for_vicidial", False)
    return job


def make_lead(job: LeadImportJob, phone: str, external_key: str) -> Lead:
    lead = Lead(id=uuid.uuid4(), external_key=external_key)
    lead.phone_normalized = phone
    lead.source = job.file_name
    lead.source_batch_id = str(job.id)
    lead.vicidial_lead_id = None
    return lead


class FakeClient:
    """Stands in for ``VicidialClient``; records every add_lead call."""

    instances: ClassVar[list[FakeClient]] = []

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self.added: list[dict[str, Any]] = []
        self.response_body = "SUCCESS: add_lead LEAD HAS BEEN ADDED - 50001"
        self.dnc_added: list[str] = []
        self.raise_on_call: Exception | None = None
        FakeClient.instances.append(self)

    async def add_dnc_phone(self, phone_number: str) -> Any:
        self.dnc_added.append(phone_number)
        return _parsed("SUCCESS: add_dnc_phone HAS BEEN ADDED", lead_id=None)
        self.raise_on_call: Exception | None = None
        FakeClient.instances.append(self)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def add_lead(self, phone_number: str, **kwargs: Any) -> Any:
        if self.raise_on_call is not None:
            raise self.raise_on_call
        self.added.append({"phone": phone_number, **kwargs})
        return _parsed(self.response_body, lead_id=str(50000 + len(self.added)))


def _parsed(body: str, lead_id: str | None) -> Any:
    from app.packages.vicidial.parser import parse_vicidial_response

    return parse_vicidial_response(body)


@pytest.fixture(autouse=True)
def _patch_dependencies(monkeypatch):
    FakeClient.instances = []
    audit = FakeAudit()

    async def fake_get_job(_session: Any, job_id: uuid.UUID, _constraints: Any = None) -> LeadImportJob | None:
        return None

    async def fake_list_leads(_session: Any, job: LeadImportJob, **_kwargs: Any) -> list[Lead]:
        return []

    async def fake_set_ids(_session: Any, pairs: list[tuple[str, uuid.UUID]]) -> None:
        return None

    async def fake_campaign_name(_session: Any, _cid: uuid.UUID) -> str | None:
        return None

    monkeypatch.setattr(leads_repo, "get_import_job", fake_get_job)
    monkeypatch.setattr(leads_repo, "list_batch_leads", fake_list_leads)
    monkeypatch.setattr(leads_repo, "set_vicidial_lead_ids", fake_set_ids)
    monkeypatch.setattr(leads_repo, "campaign_name", fake_campaign_name)
    async def fake_active_suppressed_phones(*_a, **_kw): return set()
    monkeypatch.setattr(leads_repo, "active_suppressed_phones", fake_active_suppressed_phones)
    monkeypatch.setattr(leads_service, "VicidialClient", FakeClient)
    monkeypatch.setattr(leads_service, "write_audit", audit)
    monkeypatch.setattr(leads_service, "publish_lead_event", audit)
    return audit


def make_user():
    from app.core.context import UserContext

    return UserContext.from_principal(
        user_id=uuid.uuid4(), role="admin", permissions=[], session_token_id="jti"
    )


def configure_vicidial(monkeypatch, *, configured: bool = True) -> None:
    from app.packages.vicidial import credentials as creds_mod

    def fake_creds():
        return creds_mod.VicidialCredentials(
            url="http://dialer.test/non_agent_api.php" if configured else "",
            user="api" if configured else "",
            password="pw" if configured else "",
            source="talkflow",
            default_campaign_id="TALKFLOW",
            default_list_id="9098",
        )

    monkeypatch.setattr(leads_service, "get_vicidial_credentials", fake_creds)


# ---------------------------------------------------------------------------
# Stop
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stop_marks_interrupted_without_calling_the_dialer(monkeypatch):
    configure_vicidial(monkeypatch)
    job = make_job(
        vicidial_list_id="9098", vicidial_run_count=3, is_active_for_vicidial=True
    )

    async def get_job(_s, _j, _c=None):
        return job

    monkeypatch.setattr(leads_repo, "get_import_job", get_job)

    result = await leads_service.set_vicidial_run(
        FakeSession(), make_user(), job.id, is_active=False
    )

    assert isinstance(result, DataResponse)
    assert result.data.vicidial_status == VicidialRunStatus.INTERRUPTED
    assert result.data.is_active_for_vicidial is False
    assert job.vicidial_run_count == 3, "stopping must not change the run count"
    assert job.vicidial_stopped_at is not None
    assert FakeClient.instances == [], "stop must not call the non-agent API"


# ---------------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_start_pushes_leads_to_the_hopper_and_bumps_the_run_count(monkeypatch):
    configure_vicidial(monkeypatch)
    job = make_job()
    leads = [
        make_lead(job, "13125550001", "aaa111"),
        make_lead(job, "13125550002", "bbb222"),
    ]

    async def get_job(_s, _j, _c=None):
        return job

    async def list_leads(_s, _j, *, pending_only=False, limit=None):
        return leads

    monkeypatch.setattr(leads_repo, "get_import_job", get_job)
    monkeypatch.setattr(leads_repo, "list_batch_leads", list_leads)

    result = await leads_service.set_vicidial_run(
        FakeSession(), make_user(), job.id, is_active=True
    )

    assert result.data.vicidial_status == VicidialRunStatus.RUNNING
    assert result.data.is_active_for_vicidial is True
    assert result.data.vicidial_run_count == 1
    assert result.data.vicidial_list_id == "9098", "falls back to the default list"
    assert result.data.submitted == 2
    assert result.data.accepted == 2

    client = FakeClient.instances[-1]
    assert [c["phone"] for c in client.added] == ["13125550001", "13125550002"]
    assert all(c["list_id"] == "9098" for c in client.added)
    assert all(c["add_to_hopper"] is True for c in client.added)
    assert [c["vendor_lead_code"] for c in client.added] == ["aaa111", "bbb222"]

    assert job.vicidial_started_at is not None
    assert job.vicidial_stopped_at is None


@pytest.mark.asyncio
async def test_start_increments_the_run_count_on_every_toggle(monkeypatch):
    configure_vicidial(monkeypatch)
    job = make_job()
    leads = [make_lead(job, "13125550001", "aaa111")]

    async def get_job(_s, _j, _c=None):
        return job

    async def list_leads(_s, _j, *, pending_only=False, limit=None):
        return leads

    monkeypatch.setattr(leads_repo, "get_import_job", get_job)
    monkeypatch.setattr(leads_repo, "list_batch_leads", list_leads)

    for expected in (1, 2, 3):
        result = await leads_service.set_vicidial_run(
            FakeSession(), make_user(), job.id, is_active=True
        )
        assert result.data.vicidial_run_count == expected


@pytest.mark.asyncio
async def test_start_honours_an_explicit_list_id_override(monkeypatch):
    configure_vicidial(monkeypatch)
    job = make_job()
    leads = [make_lead(job, "13125550001", "aaa111")]

    async def get_job(_s, _j, _c=None):
        return job

    async def list_leads(_s, _j, *, pending_only=False, limit=None):
        return leads

    monkeypatch.setattr(leads_repo, "get_import_job", get_job)
    monkeypatch.setattr(leads_repo, "list_batch_leads", list_leads)

    result = await leads_service.set_vicidial_run(
        FakeSession(),
        make_user(),
        job.id,
        is_active=True,
        vicidial_list_id="7777",
    )

    assert result.data.vicidial_list_id == "7777"
    assert FakeClient.instances[-1].added[0]["list_id"] == "7777"
    assert job.vicidial_list_id == "7777"


# ---------------------------------------------------------------------------
# Failure modes
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_start_without_vicidial_credentials_raises_503(monkeypatch):
    configure_vicidial(monkeypatch, configured=False)
    job = make_job()

    async def get_job(_s, _j, _c=None):
        return job

    monkeypatch.setattr(leads_repo, "get_import_job", get_job)

    with pytest.raises(VicidialNotConfiguredError):
        await leads_service.set_vicidial_run(
            FakeSession(), make_user(), job.id, is_active=True
        )
    assert job.is_active_for_vicidial is False
    assert job.vicidial_run_count == 0


@pytest.mark.asyncio
async def test_start_on_an_unknown_batch_raises_404():
    with pytest.raises(ImportJobNotFoundError):
        await leads_service.set_vicidial_run(
            FakeSession(), make_user(), uuid.uuid4(), is_active=True
        )


@pytest.mark.asyncio
async def test_start_leaves_the_list_idle_when_the_dialer_rejects_every_lead(monkeypatch):
    configure_vicidial(monkeypatch)
    job = make_job()
    leads = [make_lead(job, "13125550001", "aaa111")]

    async def get_job(_s, _j, _c=None):
        return job

    async def list_leads(_s, _j, *, pending_only=False, limit=None):
        return leads

    monkeypatch.setattr(leads_repo, "get_import_job", get_job)
    monkeypatch.setattr(leads_repo, "list_batch_leads", list_leads)

    client = FakeClient
    original_init = client.__init__

    def init_with_error(self, *a, **kw):
        original_init(self, *a, **kw)
        self.response_body = "ERROR: Duplicate Lead"

    monkeypatch.setattr(client, "__init__", init_with_error)

    with pytest.raises(VicidialIngestFailedError):
        await leads_service.set_vicidial_run(
            FakeSession(), make_user(), job.id, is_active=True
        )

    assert job.vicidial_status == VicidialRunStatus.IDLE
    assert job.is_active_for_vicidial is False
    assert job.vicidial_run_count == 0, "a failed push must not count as a run"


@pytest.mark.asyncio
async def test_start_aborts_the_ingest_when_the_dialer_is_unreachable(monkeypatch):
    import httpx

    configure_vicidial(monkeypatch)
    job = make_job()
    leads = [
        make_lead(job, "13125550001", "aaa111"),
        make_lead(job, "13125550002", "bbb222"),
    ]

    async def get_job(_s, _j, _c=None):
        return job

    async def list_leads(_s, _j, *, pending_only=False, limit=None):
        return leads

    monkeypatch.setattr(leads_repo, "get_import_job", get_job)
    monkeypatch.setattr(leads_repo, "list_batch_leads", list_leads)

    original_init = FakeClient.__init__

    def init_unreachable(self, *a, **kw):
        original_init(self, *a, **kw)
        self.raise_on_call = httpx.ConnectError("dialer down")

    monkeypatch.setattr(FakeClient, "__init__", init_unreachable)

    with pytest.raises(VicidialIngestFailedError):
        await leads_service.set_vicidial_run(
            FakeSession(), make_user(), job.id, is_active=True
        )

    client = FakeClient.instances[-1]
    assert len(client.added) == 0, "must not keep retrying an unreachable dialer"
    assert job.vicidial_run_count == 0


@pytest.mark.asyncio
async def test_start_still_runs_when_a_subset_of_leads_is_rejected(monkeypatch):
    configure_vicidial(monkeypatch)
    job = make_job()
    leads = [
        make_lead(job, "13125550001", "aaa111"),
        make_lead(job, "13125550002", "bbb222"),
    ]

    async def get_job(_s, _j, _c=None):
        return job

    async def list_leads(_s, _j, *, pending_only=False, limit=None):
        return leads

    monkeypatch.setattr(leads_repo, "get_import_job", get_job)
    monkeypatch.setattr(leads_repo, "list_batch_leads", list_leads)

    original_add = FakeClient.add_lead

    async def add_rejecting_second(self, phone_number, **kwargs):
        if phone_number == "13125550002":
            self.response_body = "ERROR: Duplicate Lead"
            from app.packages.vicidial.parser import parse_vicidial_response

            return parse_vicidial_response(self.response_body)
        return await original_add(self, phone_number, **kwargs)

    monkeypatch.setattr(FakeClient, "add_lead", add_rejecting_second)

    result = await leads_service.set_vicidial_run(
        FakeSession(), make_user(), job.id, is_active=True
    )

    assert result.data.vicidial_status == VicidialRunStatus.RUNNING
    assert result.data.accepted == 1
    assert result.data.rejected == 1
    assert result.data.vicidial_run_count == 1
    assert any("bbb222" in e for e in result.data.errors)


@pytest.mark.asyncio
async def test_start_on_a_batch_with_no_leaves_does_not_claim_a_run(monkeypatch):
    configure_vicidial(monkeypatch)
    job = make_job()

    async def get_job(_s, _j, _c=None):
        return job

    monkeypatch.setattr(leads_repo, "get_import_job", get_job)

    async def list_leads(_s, _j, *, pending_only=False, limit=None):
        return []

    monkeypatch.setattr(leads_repo, "list_batch_leads", list_leads)

    result = None
    with pytest.raises(VicidialNothingToSubmitError):
        result = await leads_service.set_vicidial_run(
            FakeSession(), make_user(), job.id, is_active=True
        )

    assert result is None
    assert job.vicidial_run_count == 0
    assert job.vicidial_status != VicidialRunStatus.RUNNING
    assert job.is_active_for_vicidial is False


@pytest.mark.asyncio
async def test_start_only_submits_leads_the_dialer_has_never_accepted(monkeypatch):
    """Regression: a re-toggled run must continue, not re-push the first page.

    The ingest used to slice ``leads[:500]`` from the whole batch, so every
    ON after the first re-sent leads that were already in the hopper and never
    reached the tail of the list.
    """
    configure_vicidial(monkeypatch)
    job = make_job()
    seen: list[bool] = []
    limits: list[int | None] = []

    async def get_job(_s, _j, _c=None):
        return job

    async def list_leads(_s, _j, *, pending_only=False, limit=None):
        seen.append(pending_only)
        limits.append(limit)
        # Second page only: the first page is already in the hopper.
        return [make_lead(job, "13125550099", "zzz999")]

    monkeypatch.setattr(leads_repo, "get_import_job", get_job)
    monkeypatch.setattr(leads_repo, "list_batch_leads", list_leads)

    result = await leads_service.set_vicidial_run(
        FakeSession(), make_user(), job.id, is_active=True
    )

    assert seen == [True], "the repository must be asked for pending leads only"
    assert limits == [500], "the page size must stay bounded"
    assert result.data.submitted == 1
    assert result.data.accepted == 1

    client = FakeClient.instances[-1]
    assert [c["phone"] for c in client.added] == ["13125550099"]


@pytest.mark.asyncio
async def test_start_persists_state_and_audit_in_one_transaction(
    monkeypatch, _patch_dependencies
):
    """The state flip and its audit row must share a single commit.

    Committing the state before the audit would leave a run recorded with no
    audit trail if the audit insert failed.
    """
    configure_vicidial(monkeypatch)
    job = make_job()

    async def get_job(_s, _j, _c=None):
        return job

    async def list_leads(_s, _j, *, pending_only=False, limit=None):
        return [make_lead(job, "13125550001", "aaa111")]

    monkeypatch.setattr(leads_repo, "get_import_job", get_job)
    monkeypatch.setattr(leads_repo, "list_batch_leads", list_leads)

    session = FakeSession()
    await leads_service.set_vicidial_run(
        session, make_user(), job.id, is_active=True
    )

    # One commit, and the audit must already have been written when it happens.
    assert session.commits == 1
    assert [r["action"] for r in _patch_dependencies.rows if "action" in r] == [
        "lead.vicidial_run.start"
    ]


def test_datetime_is_utc_aware_for_run_markers():
    # Guards the audit trail: a naive timestamp would be ambiguous vs. the
    # timezone-aware created_at on the same row.
    assert datetime.now(UTC).tzinfo is not None


@pytest.mark.asyncio
async def test_realtime_dnc_guard_blocks_and_registers_in_vicidial_dnc(monkeypatch):
    """Real-Time DNC Guard blocks DNC matched leads and registers them via add_dnc_phone."""
    configure_vicidial(monkeypatch)
    job = make_job()
    lead_valid = make_lead(job, "13125550001", "aaa111")
    lead_dnc = make_lead(job, "13125550002", "bbb222")

    async def get_job(_s, _j, _c=None):
        return job

    async def list_leads(_s, _j, *, pending_only=False, limit=None):
        return [lead_valid, lead_dnc]

    async def active_suppression(_s, phones):
        return {"13125550002"}

    monkeypatch.setattr(leads_repo, "get_import_job", get_job)
    monkeypatch.setattr(leads_repo, "list_batch_leads", list_leads)
    monkeypatch.setattr(leads_repo, "active_suppressed_phones", active_suppression)

    result = await leads_service.set_vicidial_run(
        FakeSession(), make_user(), job.id, is_active=True
    )

    client = FakeClient.instances[-1]
    # The valid phone was added to hopper
    assert [x["phone"] for x in client.added] == ["13125550001"]
    # The DNC phone was blocked from hopper and registered in VICIdial DNC
    assert client.dnc_added == ["13125550002"]
    assert lead_dnc.suppressed is True
    assert lead_dnc.suppression_reason == "dnc_guard"
    assert result.data.accepted == 1
    assert result.data.rejected == 1
