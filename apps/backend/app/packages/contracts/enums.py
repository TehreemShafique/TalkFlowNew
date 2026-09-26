"""Shared domain enums used across control-plane modules."""

from __future__ import annotations

from enum import StrEnum


class RecordingStatus(StrEnum):
    """Lifecycle of a recording's audio pipeline.

    Mirrors the frontend enum (apps/TalkFlow.md section 11.8) so the wire
    contract never diverges from the worker's writes.
    """

    PENDING = "pending"
    WAITING_FOR_SOURCE = "waiting_for_source"
    FETCHING = "fetching"
    VALIDATING = "validating"
    STORING = "storing"
    READY = "ready"
    FAILED = "failed"
    PURGED = "purged"


class StorageProvider(StrEnum):
    LOCAL = "local"
    S3 = "s3"
    MINIO = "minio"


class AuditResult(StrEnum):
    """Outcome of an audited action."""

    GRANTED = "granted"
    DENIED = "denied"
    SUCCESS = "success"
    FAILED = "failed"


class ScriptStatus(StrEnum):
    """Governance lifecycle of a conversational script and script versions.

    Mirrors frontend ScriptStatus interface (apps/TalkFlow.md section 11.6):
    ``draft | pending_approval | approved | active | archived | rejected``.
    """

    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    ACTIVE = "active"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class ScriptNodeType(StrEnum):
    """Type of node in a conversational flow graph."""

    GREETING = "greeting"
    CONSENT = "consent"
    QUESTION = "question"
    STATEMENT = "statement"
    CONDITION = "condition"
    FALLBACK = "fallback"
    TRANSFER = "transfer"
    CLOSING = "closing"
    OPT_OUT = "opt_out"


class CampaignStatus(StrEnum):
    """Governance lifecycle of a dialing campaign.

    Mirrors the frontend ``Campaign`` interface (apps/TalkFlow.md section 11):
    ``draft | active | paused | stopped | archived``.
    """

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    ARCHIVED = "archived"


class UserStatus(StrEnum):
    """Admin approval state of a user account (port of auth-service)."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class RoleDomain(StrEnum):
    """Functional domain a role belongs to (port of auth-service)."""

    SYSTEM = "system"
    OPERATIONS = "operations"
    QUALITY = "quality"
    VERIFICATION = "verification"
    REPORTING = "reporting"


class CallDirection(StrEnum):
    """Direction of a call relative to the dialer.

    Mirrors the frontend contract (apps/TalkFlow.md section 26): ``outbound``
    for calls the campaign dialed, ``inbound`` for calls received on a DID.
    """

    OUTBOUND = "outbound"
    INBOUND = "inbound"


class CallStatus(StrEnum):
    """Lifecycle of a call through the AI Voice Bot + dialer loop.

    ``in_progress`` / ``transferring`` are the "live" states surfaced by
    GET /calls/live (matches the partial index on ``calls.status``).
    """

    QUEUED = "queued"
    DIALING = "dialing"
    RINGING = "ringing"
    ANSWERED = "answered"
    IN_PROGRESS = "in_progress"
    TRANSFERRING = "transferring"
    TRANSFERRED = "transferred"
    COMPLETED = "completed"
    FAILED = "failed"


class TransferStatus(StrEnum):
    """Lifecycle of a transfer (apps/TalkFlow.md section 11.5)."""

    NOT_APPLICABLE = "not_applicable"
    INITIATED = "initiated"
    RINGING_VERIFIER = "ringing_verifier"
    BRIDGED = "bridged"
    COMPLETED = "completed"
    FAILED_NO_VERIFIER = "failed_no_verifier"
    FAILED_TIMEOUT = "failed_timeout"
    FAILED_REJECTED = "failed_rejected"
    FAILED_TECHNICAL = "failed_technical"
    RETRY_SCHEDULED = "retry_scheduled"
    FALLBACK_QUEUED = "fallback_queued"
    CALLBACK_CREATED = "callback_created"


class QualificationStatus(StrEnum):
    """Live qualification outcome of a call (apps/TalkFlow.md section 11.4).

    ``qualified`` / ``disqualified`` are terminal; ``incomplete`` means the
    evidence needed to decide was never captured.
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


class Speaker(StrEnum):
    """Side of the conversation a transcript turn came from."""

    BOT = "bot"
    CALLER = "caller"
    VERIFIER = "verifier"
    SYSTEM = "system"


class LeadStatus(StrEnum):
    """Lifecycle of a lead (apps/TalkFlow.md section 11.7)."""

    NEW = "new"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"
    CALLBACK = "callback"
    DO_NOT_CALL = "do_not_call"
    EXHAUSTED = "exhausted"
    INVALID = "invalid"
    SUPPRESSED = "suppressed"


class SuppressionReason(StrEnum):
    """Why a number is on the do-not-call register (section 19.4)."""

    INTERNAL_DNC = "internal_dnc"
    FEDERAL_DNC = "federal_dnc"
    CALLER_REQUEST = "caller_request"
    COMPLAINT = "complaint"
    LITIGATOR = "litigator"
    INVALID = "invalid"


class VicidialRunStatus(StrEnum):
    """Execution state of a lead list inside the VICIdial dialer.

    ``RUNNING`` means the list has been pushed into the dialer hopper and is
    eligible for dialing; ``INTERRUPTED`` means an operator toggled the run off
    (TalkFlow-side state only - the non-agent API has no pause function).
    """

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"


class ImportJobStatus(StrEnum):
    """Lifecycle of a lead CSV import job (section 12 ``LeadImportJob``)."""

    UPLOADING = "uploading"
    MAPPING = "mapping"
    VALIDATING = "validating"
    IMPORTING = "importing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExportStatus(StrEnum):
    """Lifecycle of a server-generated export job (section 28.8)."""

    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class ExportFormat(StrEnum):
    """Supported output format for export jobs (CSV only today)."""

    CSV = "csv"
