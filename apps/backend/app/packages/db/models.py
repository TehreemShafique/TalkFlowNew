"""SQLAlchemy models and shared table projections.

`CallRecording` is the ORM model backing the ``call_recordings`` table created
by ``alembic/versions/….call_recordings``.

The ``*_table`` objects below are **shared, read-only projections** of tables
owned by other modules (calls, leads, campaigns, qa, audit, workers).  They
exist here so the ``recordings`` module can JOIN to build the dashboard payload
without reaching into another module's repository (Rule R3); the tables
themselves are created by their owning module's migrations.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.packages.contracts.enums import (
    CallDirection,
    CallStatus,
    CampaignStatus,
    ExportStatus,
    ImportJobStatus,
    LeadStatus,
    RecordingStatus,
    ScriptNodeType,
    ScriptStatus,
    StorageProvider,
    UserStatus,
)
from app.packages.db.base import Base, utc_now, uuid7

# ``text`` (the column) shadows sqlalchemy.text inside TranscriptTurn; this
# alias keeps the function reachable there.
_sa_text = text


class CallRecording(Base):
    """A transcribed-and-stored call recording plus its pipeline metadata.

    The metadata row is retained indefinitely; only ``storage_key`` /
    ``audio_purged_at`` / ``status`` change when the physical audio is
    purged (blueprint section 15.5).
    """

    __tablename__ = "call_recordings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    call_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
    )
    vicidial_recording_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("leads.id")
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("campaigns.id")
    )

    # Pipeline status enum (see contracts.enums.RecordingStatus).
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RecordingStatus.PENDING.value,
        server_default=text("'pending'"),
    )

    # Storage & file details.
    storage_provider: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=StorageProvider.LOCAL.value,
        server_default=text("'local'"),
    )
    storage_key: Mapped[str | None] = mapped_column(String(512))
    sha256_hash: Mapped[str | None] = mapped_column(String(64))
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    mime_type: Mapped[str | None] = mapped_column(
        String(64), default="audio/wav", server_default=text("'audio/wav'")
    )
    duration_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )

    # Retention & compliance.
    retention_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("retention_policies.id")
    )
    # Hard retention deadline; the purge worker flips READY -> PURGED once
    # `expires_at <= now()` (see recordings.service.purge_expired_recordings).
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_offset_ms: Mapped[int | None] = mapped_column(Integer)
    audio_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=text("clock_timestamp()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=text("clock_timestamp()"),
    )

    __table_args__ = (
        Index("idx_call_recordings_call_id", "call_id"),
        Index("idx_call_recordings_status", "status"),
        Index("idx_call_recordings_lead_id", "lead_id"),
    )

    @property
    def status_enum(self) -> RecordingStatus:
        return RecordingStatus(self.status)

    @property
    def is_ready(self) -> bool:
        return self.status == RecordingStatus.READY.value

    @property
    def is_purged(self) -> bool:
        return self.status == RecordingStatus.PURGED.value

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<CallRecording id={self.id} call_id={self.call_id} status={self.status}>"


# ---------------------------------------------------------------------------
# Auth & RBAC models (port of services/auth-service).
# IDs are UUIDv7 (time-ordered) per TASK section 3; role membership is a
# many-to-many relationship only (the legacy single-role FK was not ported).
# ---------------------------------------------------------------------------
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid7,
    )
    name: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    domain: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    is_system: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )

    assigned_users: Mapped[list[User]] = relationship(
        "User", secondary="user_roles", back_populates="roles"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Role id={self.id} name={self.name!r} domain={self.domain!r}>"


class User(Base):
    """An operator or licensed agent of the control plane."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid7,
    )
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(120))
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    collaborator_pin: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(160))
    extension: Mapped[str | None] = mapped_column(String(40))
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=UserStatus.PENDING.value,
        server_default=text("'PENDING'"),
    )

    roles: Mapped[list[Role]] = relationship(
        "Role", secondary="user_roles", back_populates="assigned_users", lazy="selectin"
    )
    sessions: Mapped[list[UserSession]] = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User id={self.id} email={self.email!r}>"


class UserSession(Base):
    """A live login: one row per issued JWT (``token_id`` = the token's jti)."""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid7,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(256))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
    )

    user: Mapped[User] = relationship("User", back_populates="sessions")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<UserSession id={self.id} token_id={self.token_id!r}>"


# ---------------------------------------------------------------------------
# Scripts (conversational flow graphs & versioning). Owned by modules/scripts.
# ---------------------------------------------------------------------------
class Script(Base):
    """Conversational script container holding version history."""

    __tablename__ = "scripts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid7,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="en-US",
        server_default=text("'en-US'"),
    )
    current_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    active_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "script_versions.id",
            use_alter=True,
            name="fk_scripts_active_version_id",
            ondelete="SET NULL",
        ),
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ScriptStatus.DRAFT.value,
        server_default=text("'draft'"),
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=text("clock_timestamp()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=text("clock_timestamp()"),
    )

    versions: Mapped[list[ScriptVersion]] = relationship(
        "ScriptVersion",
        back_populates="script",
        cascade="all, delete-orphan",
        foreign_keys="ScriptVersion.script_id",
    )

    __table_args__ = (
        Index("ix_scripts_status", "status"),
        Index("ix_scripts_name", "name"),
    )


class ScriptVersion(Base):
    """Immutable snapshot version of a script node graph."""

    __tablename__ = "script_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid7,
        server_default=text("gen_random_uuid()"),
    )
    script_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("scripts.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ScriptStatus.DRAFT.value,
        server_default=text("'draft'"),
    )
    entry_node_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="node-1", server_default=text("'node-1'")
    )
    nodes: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    rule_set_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    change_note: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=text("clock_timestamp()"),
    )
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id")
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_reason: Mapped[str | None] = mapped_column(String(500))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    script: Mapped[Script] = relationship(
        "Script",
        back_populates="versions",
        foreign_keys=[script_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "script_id", "version", name="uq_script_versions_script_id_version"
        ),
        Index("ix_script_versions_script_id", "script_id"),
        Index("ix_script_versions_status", "status"),
    )


class ScriptActivation(Base):
    """Activation audit record linking script versions to campaigns."""

    __tablename__ = "script_activations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid7,
        server_default=text("gen_random_uuid()"),
    )
    script_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("scripts.id", ondelete="CASCADE"), nullable=False
    )
    script_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("script_versions.id", ondelete="CASCADE"), nullable=False
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("campaigns.id", ondelete="CASCADE")
    )
    activated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id")
    )
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=text("clock_timestamp()"),
    )

    __table_args__ = (
        Index("ix_script_activations_script_id", "script_id"),
        Index("ix_script_activations_campaign_id", "campaign_id"),
    )


# ---------------------------------------------------------------------------
# Campaigns (governance + VICIdial mapping).  Owned by modules/campaigns.
# ---------------------------------------------------------------------------
class Campaign(Base):
    """A dialing campaign and its governance configuration."""

    __tablename__ = "campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid7,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CampaignStatus.DRAFT.value,
        server_default=text("'draft'"),
    )

    # Script binding references.
    script_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("scripts.id", ondelete="SET NULL")
    )
    active_script_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("script_versions.id", ondelete="SET NULL")
    )
    rule_set_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    compliance_profile_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))

    # VICIdial dialer mapping.
    vicidial_campaign_id: Mapped[str | None] = mapped_column(String(64))
    closer_in_group: Mapped[str | None] = mapped_column(String(120))

    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="America/New_York",
        server_default=text("'America/New_York'"),
    )

    # Opaque governance config stored verbatim (camelCase JSON on the wire).
    dialing: Mapped[dict | None] = mapped_column(JSONB)
    transfer: Mapped[dict | None] = mapped_column(JSONB)
    recording: Mapped[dict | None] = mapped_column(JSONB)
    retention: Mapped[dict | None] = mapped_column(JSONB)

    # Optimistic-locking counter; bumped on every successful mutation.
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=text("clock_timestamp()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=text("clock_timestamp()"),
    )

    vicidial_lists: Mapped[list[CampaignVicidialList]] = relationship(
        "CampaignVicidialList",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_campaigns_status", "status"),
    )

    @property
    def status_enum(self) -> CampaignStatus:
        return CampaignStatus(self.status)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Campaign id={self.id} name={self.name!r} status={self.status}>"


class CampaignVicidialList(Base):
    """Mapping of one VICIdial list (``list_id``) to a TalkFlow campaign."""

    __tablename__ = "campaign_vicidial_lists"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid7,
        server_default=text("gen_random_uuid()"),
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    vicidial_list_id: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=text("clock_timestamp()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=text("clock_timestamp()"),
    )

    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="vicidial_lists")

    __table_args__ = (
        UniqueConstraint(
            "campaign_id", "vicidial_list_id", name="uq_campaign_vicidial_lists"
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<CampaignVicidialList campaign_id={self.campaign_id} "
            f"list_id={self.vicidial_list_id!r} active={self.active}>"
        )


# ---------------------------------------------------------------------------
# Leads + import jobs (owned by modules/leads).  The physical ``leads`` table
# is extended in-place by the module's migration (e5f6a7b8c9d0 created the
# stub, this metadata keeps the ORM in lock-step for create_all scratch DBs).
# ``import_job_id`` is intentionally a soft reference (no FK): jobs are
# created after leads in the migration chain.
# ---------------------------------------------------------------------------
class Lead(Base):
    """A lead record - the dialer's master contact data + import metadata."""

    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    first_name: Mapped[str | None] = mapped_column(String(120))
    last_name: Mapped[str | None] = mapped_column(String(120))
    phone_normalized: Mapped[str | None] = mapped_column(String(32), index=True)
    alt_phone: Mapped[str | None] = mapped_column(String(32))
    phone_raw: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(254))
    state: Mapped[str | None] = mapped_column(String(8))
    zip_code: Mapped[str | None] = mapped_column(String(16))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    age: Mapped[int | None] = mapped_column(Integer)

    source: Mapped[str | None] = mapped_column(String(120))
    source_batch_id: Mapped[str | None] = mapped_column(String(64))
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=LeadStatus.NEW.value,
        server_default=text("'new'"),
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    suppressed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    suppression_reason: Mapped[str | None] = mapped_column(String(32))

    custom_fields: Mapped[dict | None] = mapped_column(JSONB)
    imported: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    import_job_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=text("clock_timestamp()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=text("clock_timestamp()"),
    )

    __table_args__ = (
        Index("ix_leads_status", "status"),
        Index("ix_leads_campaign_id", "campaign_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Lead id={self.id} phone={self.phone_normalized!r} status={self.status}>"


class LeadImportJob(Base):
    """A resumable CSV import (upload -> mapping -> validating -> commit).

    The parsed source rows and the saved column mapping travel inside the job
    row so a double-commit can never re-read the upload and duplicate leads
    (section 19.2: import is resumable and idempotent).
    """

    __tablename__ = "lead_import_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid7,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=ImportJobStatus.UPLOADING.value,
        server_default=text("'uploading'"),
    )
    total_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    imported_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    duplicate_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    suppressed_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    invalid_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    columns: Mapped[list | None] = mapped_column(JSONB)
    mapping: Mapped[dict | None] = mapped_column(JSONB)
    rows: Mapped[list | None] = mapped_column(JSONB)
    options: Mapped[dict | None] = mapped_column(JSONB)
    validation: Mapped[dict | None] = mapped_column(JSONB)
    error_report_key: Mapped[str | None] = mapped_column(String(512))
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=text("clock_timestamp()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=text("clock_timestamp()"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<LeadImportJob id={self.id} file={self.file_name!r} status={self.status}>"


# ---------------------------------------------------------------------------
# Suppression / DNC register (owned by modules/suppression).  One row per
# suppression event; soft deletion via ``removed_at`` keeps the audit trail.
# The partial unique index enforces one ACTIVE entry per number.
# ---------------------------------------------------------------------------
class SuppressionEntry(Base):
    __tablename__ = "suppression_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid7
    )
    phone_normalized: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str | None] = mapped_column(String(120))
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=text("clock_timestamp()"),
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_reference: Mapped[str | None] = mapped_column(String(255))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=text("clock_timestamp()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=text("clock_timestamp()"),
    )

    __table_args__ = (
        Index("ix_suppression_entries_phone", "phone_normalized"),
        Index("ix_suppression_entries_reason", "reason"),
        Index(
            "uq_suppression_entries_active_phone",
            "phone_normalized",
            unique=True,
            postgresql_where=text("removed_at IS NULL"),
        ),
    )

    @property
    def is_active(self) -> bool:
        return self.removed_at is None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<SuppressionEntry id={self.id} phone={self.phone_normalized!r} "
            f"reason={self.reason!r} active={self.is_active}>"
        )


# ---------------------------------------------------------------------------
# Export jobs (owned by modules/exports).  Request -> queued -> processing ->
# ready; the CSV artifact lives in object storage (``storage_key``) and the
# download is permission-gated + audit-logged (section 28.8).
# ---------------------------------------------------------------------------
class ExportJob(Base):
    __tablename__ = "exports"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid7,
    )
    report: Mapped[str] = mapped_column(String(64), nullable=False)
    format: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default="csv",
        server_default=text("'csv'"),
    )
    filters: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=ExportStatus.QUEUED.value,
        server_default=text("'queued'"),
    )
    row_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    storage_key: Mapped[str | None] = mapped_column(String(512))
    error: Mapped[str | None] = mapped_column(String(512))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=text("clock_timestamp()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=text("clock_timestamp()"),
    )

    __table_args__ = (
        Index("ix_exports_report", "report"),
        Index("ix_exports_status", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ExportJob id={self.id} report={self.report!r} status={self.status}>"


# ---------------------------------------------------------------------------
# Calls (owned by modules/calls).  In the dev database ``calls``,
# ``transcript_turns`` and ``call_events`` are range-partitioned monthly (see
# alembic 9f0a1b2c3d4e).  These ORM classes describe the **plain** equivalent
# used by ``Base.metadata.create_all`` (tests / scratch DBs) so the suite never
# depends on Alembic.  FKs this migration cannot declare against the
# partitioned parents (a child FK to ``calls.id`` would require a unique index
# on the partition key) are kept here and replaced by bare indexes there.
# ``reference``/``direction``/``status``/``attempt_number`` carry the same
# server defaults there, so legacy stub rows copy cleanly.
# ---------------------------------------------------------------------------
class Call(Base):
    """One dialer call plus its AI Voice Bot / outcome metadata."""

    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    reference: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("''")
    )
    direction: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=CallDirection.OUTBOUND.value,
        server_default=text("'outbound'"),
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=CallStatus.QUEUED.value,
        server_default=text("'queued'"),
    )
    disposition: Mapped[str | None] = mapped_column(String(64))

    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("leads.id", ondelete="SET NULL")
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("campaigns.id", ondelete="SET NULL")
    )
    # Soft references: the scripts module is not built yet (no FK by design).
    script_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    script_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    # Stamp applied when the call is ingested (roadmap section 660: script
    # version + rule-set version + channel + Agent name used are all recorded
    # **at open** so late reconciliation never needs to guess them).
    rule_set_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))

    channel_id: Mapped[str | None] = mapped_column(String(64))
    # The Agent alias the voice bot actually used for this call (STEP 15: set
    # from talkflow.call.opened.v1 ``agentAlias``).
    agent_alias_used: Mapped[str | None] = mapped_column(String(64))
    vicidial_call_id: Mapped[str | None] = mapped_column(String(64))
    vicidial_lead_id: Mapped[str | None] = mapped_column(String(64))
    vicidial_list_id: Mapped[str | None] = mapped_column(String(64))
    vicidial_status: Mapped[str | None] = mapped_column(String(32))

    caller_number: Mapped[str | None] = mapped_column(String(32))
    caller_state: Mapped[str | None] = mapped_column(String(8))
    did_used: Mapped[str | None] = mapped_column(String(32))
    caller_id_used: Mapped[str | None] = mapped_column(String(32))

    attempt_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    talk_time_seconds: Mapped[int | None] = mapped_column(Integer)

    qualification_status: Mapped[str | None] = mapped_column(String(32))
    disqualification_reason: Mapped[str | None] = mapped_column(String(64))
    transfer_status: Mapped[str | None] = mapped_column(String(32))
    verifier_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    qa_status: Mapped[str | None] = mapped_column(String(32))
    qa_score: Mapped[float | None] = mapped_column(Float)

    # Multi-tenant scope column the repository enforces (Rule R5).
    tenant_id: Mapped[str | None] = mapped_column(String(36))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=text("clock_timestamp()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=text("clock_timestamp()"),
    )

    __table_args__ = (
        Index("ix_calls_tenant_id", "tenant_id"),
        Index("ix_calls_campaign_id_started_at", "campaign_id", "started_at"),
        Index("ix_calls_script_version_id_started_at", "script_version_id", "started_at"),
        Index("ix_calls_lead_id_started_at", "lead_id", "started_at"),
        Index("ix_calls_vicidial_call_id", "vicidial_call_id"),
        # Rule 2 (idempotent open): one live channel == one call.  Unique here
        # on the plain test table; the partitioned dev table cannot declare a
        # unique constraint on a non-partition-key column, so the migration
        # relies on the ingest worker's channel lookup instead.  The unique
        # constraint doubles as the lookup index (kind=unique), replacing the
        # bare channel index.
        UniqueConstraint("channel_id", name="uq_calls_channel_id"),
        Index("ix_calls_reference", "reference"),
        Index(
            "ix_calls_live_status",
            "status",
            postgresql_where=text("status IN ('in_progress','transferring')"),
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Call id={self.id} reference={self.reference!r} status={self.status}>"


class TranscriptTurn(Base):
    """A single AI Voice Bot transcript line with timing + confidence."""

    __tablename__ = "transcript_turns"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    call_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False
    )
    speaker: Mapped[str] = mapped_column(String(32), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_ts_ms: Mapped[int | None] = mapped_column(Integer)
    end_ts_ms: Mapped[int | None] = mapped_column(Integer)
    node_id: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    redacted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=_sa_text("false")
    )
    # Full-text vector maintained by PostgreSQL itself (GENERATED ALWAYS AS
    # to_tsvector('english', text) STORED) so /transcript search over the
    # partitioned table never drifts from the stored text.  Read-only here; the
    # ingestion worker must not insert into it (generated columns reject
    # writes), it stays excluded from INSERT statements automatically.
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', text)", persisted=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=_sa_text("clock_timestamp()"),
    )

    __table_args__ = (
        UniqueConstraint("call_id", "seq", name="uq_transcript_turns_call_seq"),
        Index("ix_transcript_turns_call_start_ms", "call_id", "start_ts_ms"),
        Index(
            "transcript_tsv_idx",
            "tsv",
            postgresql_using="gin",
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<TranscriptTurn call_id={self.call_id} seq={self.seq} speaker={self.speaker!r}>"


class CallEvent(Base):
    """One raw (deduplicated) event from the call's event stream."""

    __tablename__ = "call_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    call_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False
    )
    external_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(96), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    event_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=text("now()"),
    )

    __table_args__ = (
        UniqueConstraint("call_id", "external_event_id", name="uq_call_events_call_external"),
        Index("ix_call_events_call_id_event_ts", "call_id", "event_ts"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<CallEvent call_id={self.call_id} type={self.type!r}>"


class CallQualificationField(Base):
    """One captured qualification-evidence value for a call."""

    __tablename__ = "call_qualification_fields"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    call_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False
    )
    field: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255))
    value: Mapped[dict | None] = mapped_column(JSONB)
    captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("now()")
    )
    transcript_ref: Mapped[str | None] = mapped_column(String(128))
    confidence: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        Index("ix_call_qualification_fields_call_id_field", "call_id", "field"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<CallQualificationField call_id={self.call_id} field={self.field!r}>"


class CallPerformance(Base):
    """Per-call AI Voice Bot latency snapshot (milliseconds)."""

    __tablename__ = "call_performance"

    call_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("calls.id", ondelete="CASCADE"),
        primary_key=True,
    )
    vad_ms: Mapped[float | None] = mapped_column(Float)
    stt_ms: Mapped[float | None] = mapped_column(Float)
    decide_ms: Mapped[float | None] = mapped_column(Float)
    llm_ttft_ms: Mapped[float | None] = mapped_column(Float)
    llm_total_ms: Mapped[float | None] = mapped_column(Float)
    tts_ttfa_ms: Mapped[float | None] = mapped_column(Float)
    tts_total_ms: Mapped[float | None] = mapped_column(Float)
    total_turn_ms: Mapped[float | None] = mapped_column(Float)
    turn_count: Mapped[int | None] = mapped_column(Integer)
    stt_provider: Mapped[str | None] = mapped_column(String(32))
    tts_provider: Mapped[str | None] = mapped_column(String(32))
    llm_provider: Mapped[str | None] = mapped_column(String(32))

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<CallPerformance call_id={self.call_id}>"


class CallNodePath(Base):
    """The script node sequence a call traversed (script-path tab)."""

    __tablename__ = "call_node_path"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    call_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int | None] = mapped_column(Integer)
    node_id: Mapped[str | None] = mapped_column(String(64))
    node_type: Mapped[str | None] = mapped_column(String(32))
    node_name: Mapped[str | None] = mapped_column(String(255))
    entered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transition_taken: Mapped[str | None] = mapped_column(String(64))
    meta: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (
        Index("ix_call_node_path_call_id_seq", "call_id", "seq"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<CallNodePath call_id={self.call_id} node_id={self.node_id!r}>"


# ---------------------------------------------------------------------------
# Read-only projections of sibling tables used by recordings JOINs (Rule R3).
# Owned and extended by their home modules; only the columns this module
# consumes are projected here.
# ---------------------------------------------------------------------------
_shared = MetaData()

calls_table = Table(
    "calls",
    _shared,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("tenant_id", String(36), nullable=True),
    Column("started_at", DateTime(timezone=True)),
    Column("duration_seconds", Integer),
    Column("disposition", String(32)),
    Column("qualification_status", String(32)),
    Column("disqualification_reason", String(64)),
    Column("lead_id", Uuid(as_uuid=True)),
    Column("campaign_id", Uuid(as_uuid=True)),
    Column("verifier_id", Uuid(as_uuid=True)),
)

leads_table = Table(
    "leads",
    _shared,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("first_name", String(120)),
    Column("last_name", String(120)),
    Column("phone_normalized", String(32), index=True),
    Column("status", String(24), nullable=False, server_default=text("'new'")),
    Column(
        "suppressed",
        Boolean,
        nullable=False,
        server_default=text("false"),
    ),
    Column("suppression_reason", String(32)),
    Column("alt_phone", String(32)),
    Column("phone_raw", String(64)),
    Column("email", String(254)),
    Column("state", String(8)),
    Column("zip_code", String(16)),
    Column("date_of_birth", Date),
    Column("age", Integer),
    Column("source", String(120)),
    Column("source_batch_id", String(64)),
    Column("campaign_id", Uuid(as_uuid=True)),
    Column("attempts", Integer),
    Column("last_attempt_at", DateTime(timezone=True)),
    Column("next_attempt_at", DateTime(timezone=True)),
    Column("assigned_to", Uuid(as_uuid=True)),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
)

campaigns_table = Table(
    "campaigns",
    _shared,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("name", String(160)),
    Column("status", String(24)),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
)

# Suppression register (owned by modules/suppression) - projects only what the
# CSV import wizard needs to classify rows: active vs removed (Rule R3).
suppression_entries_table = Table(
    "suppression_entries",
    _shared,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("phone_normalized", String(32), nullable=False),
    Column("reason", String(32), nullable=False),
    Column("removed_at", DateTime(timezone=True), nullable=True),
)

# AI Voice Bot transcript lines joined per call (Rule R3 - read-only projection;
# owned by the calls module migration).  Ordered by ``seq`` so the drawer
# renders the conversation in spoken order.
call_transcripts_table = Table(
    "call_transcripts",
    _shared,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("call_id", Uuid(as_uuid=True), nullable=False),
    Column("seq", Integer, nullable=False),
    Column("speaker", String(32), nullable=False),
    Column("time", String(16), nullable=False),
    Column("text", String(4000), nullable=False),
)

qa_reviews_table = Table(
    "qa_reviews",
    _shared,
    Column("id", Uuid(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("call_id", Uuid(as_uuid=True), nullable=False),
    Column("recording_id", Uuid(as_uuid=True), nullable=True),
    Column("status", String(32)),
    Column("score", Float),
    Column("auto_failed", Boolean),
    Column("consent_verified", Boolean),
    Column("qual_verified", Boolean),
    Column("transfer_verified", Boolean),
    Column("notes", String(4000)),
    Column("audited_by", Uuid(as_uuid=True)),
    Column("created_at", DateTime(timezone=True)),
    Column("updated_at", DateTime(timezone=True)),
    Index("uq_qa_reviews_call_id", "call_id", unique=True),
)

audit_log_table = Table(
    "audit_log",
    _shared,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("ts", DateTime(timezone=True)),
    Column("actor_id", Uuid(as_uuid=True)),
    Column("actor_role", String(64)),
    Column("action", String(96)),
    Column("resource_type", String(64)),
    Column("resource_id", String(64)),
    Column("result", String(32)),
    Column("ip", String(64)),
    Column("user_agent", String(256)),
    Column("metadata", JSON),
    Column("trace_id", String(64)),
)

outbox_table = Table(
    "outbox",
    _shared,
    Column("id", Uuid(as_uuid=True), server_default=text("gen_random_uuid()"), primary_key=True),
    Column("aggregate_type", String(64)),
    Column("aggregate_id", String(64)),
    Column("channel", String(96)),
    Column("event_type", String(96)),
    Column("payload", JSON),
    Column("created_at", DateTime(timezone=True), server_default=text("now()")),
    Column("dispatched_at", DateTime(timezone=True)),
    Column("attempts", Integer, server_default=text("0")),
)

retention_policies_table = Table(
    "retention_policies",
    _shared,
    Column("id", Uuid(as_uuid=True), primary_key=True),
    Column("name", String(120)),
    Column("audio_days", Integer),
)