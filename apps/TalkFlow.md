# TalkFlow — Medicare AI Voice Bot
## Frontend Engineering Specification
---

## Document Control

| Field | Value |
|---|---|
| Document type | Frontend engineering specification |
| Audience | Frontend developer(s), backend lead, QA, project manager |
| Frontend stack | Next.js (App Router), React, TypeScript, Tailwind CSS |
| Backend contract | REST + WebSocket |
| Build model | Mock-first, contract-driven, backend-independent until Phase 7 |

### What changed from v1.0

v1.0 described the observability surface of the platform accurately but covered roughly half of the PRD's "Must have" functional requirements. v2.0 closes those gaps and re-baselines priorities against the PRD.

| Area | v1.0 | v2.0 |
|---|---|---|
| Script Management (FR-05) | Absent | Full module — editor, branching, versioning, approval, preview, activation |
| Live Transfer (FR-08) | Absent | Full module — transfer console, states, failure recovery |
| Verifier Workspace | Absent | Dedicated role workspace with disposition capture |
| QA Review (FR-10) | Absent | Queue, sampling, scorecards, tags, calibration |
| Lead Management (FR-01) | Read-only result table | Import wizard, CRUD, assignment, source tracking, lead detail |
| Suppression / DNC | Absent | Dedicated module |
| Campaign configuration (FR-02, FR-03) | Read-only table | Dialing rules, calling hours, retries, DID/caller-ID mapping, script binding |
| Roles | 4 generic roles | 6 PRD roles with permission matrix |
| Call status / disposition | 4 states | Full telephony + disposition taxonomy including AMD/voicemail |
| Reporting | Partial | All 5 PRD reports + export pipeline |
| API contract | GET-only | Full read/write catalogue with response envelope |
| Priorities | Observability-weighted | PRD must-have weighted |

---

# PART I — PRODUCT AND SYSTEM CONTEXT

## 1. Product Overview

TalkFlow is a production-grade, low-latency AI voice platform that automates first-level Medicare qualification calls for SmartBrains BPO. The bot executes an approved conversational script, captures structured eligibility data, and transfers qualified prospects to a licensed human verifier with full context.

Three operating principles govern every screen in this application:

1. **The bot assists; the human decides.** The platform must never present the bot as a licensed agent, and must never render a final coverage decision without a licensed human in the loop.
2. **Everything is auditable.** Every call carries its campaign, its script version, its consent evidence, its disposition, and the identity of every user who touched it.
3. **The frontend is a control plane, never a media plane.** No audio, no inference, no business rule evaluation happens in the browser.

## 2. System Architecture

### 2.1 Realtime path (outside frontend scope)

```text
Caller / PSTN
    ↓
SIP Trunk
    ↓
Asterisk / VICIdial
    ↓
AudioSocket
    ↓
Realtime AI Gateway
    ↓
VAD  →  STT  →  Script Engine + Eligibility Rules  →  (LLM fallback)  →  TTS
    ↓
Asterisk
    ↓
Caller  |  Transfer Bridge → Verifier
```

### 2.2 Control plane (frontend scope)

```text
Realtime Gateway ─┐
Script Engine ────┤
Recording Worker ─┼──→  Application API  ──→  REST  ──→  Next.js Frontend
PostgreSQL ───────┤                       └──→  WS  ───┘
Redis / Queue ────┘
```

The frontend consumes the Application API only. It never opens a socket to Asterisk, VICIdial, a model server, or object storage.

### 2.3 Layer ownership

| Layer | Owner | Frontend involvement |
|---|---|---|
| Voice layer (SIP, Asterisk, VICIdial, transfer bridge) | Backend / Telephony | Displays status only |
| AI conversation layer (VAD, STT, script engine, rules, TTS) | Backend / ML | Displays state and output only |
| Application layer (portal, campaigns, scripts, QA, dashboards) | **Frontend + Backend API** | **Full ownership of UI** |
| Data layer (leads, scripts, calls, transcripts, audit) | Backend | Reads via API |
| Integration layer (CRM, webhooks, imports) | Backend | Configuration UI + status views |
| Operations layer (monitoring, backups, alerting) | Backend / DevOps | Displays health and alerts |

## 3. Actors and Roles

Roles are taken directly from PRD §4. The v1.0 role names (`SUPER_ADMIN`, `SUPERVISOR`, `VIEWER`) are retired.

| Role key | Label | Primary workspace | Responsibility |
|---|---|---|---|
| `MASTER_ADMIN` | Master Admin | Dashboard | Full access: users, campaigns, scripts, integrations, settings, audit |
| `CAMPAIGN_MANAGER` | Campaign Manager | Campaigns | Create/manage campaigns, activate approved scripts, monitor live outcomes, assign teams |
| `VERIFIER` | Verifier / Licensed Agent | Verifier Workspace | Receive transfers, verify caller, set final disposition |
| `QA_MANAGER` | QA Manager | QA Queue | Review recordings/transcripts, score calls, flag compliance issues |
| `REPORTING_USER` | Reporting User | Analytics | View dashboards and permitted exports |
| `IT_OPS` | IT / DevOps | System Health | Monitor infrastructure, integrations, error recovery |

**Critical rule:** role-based UI is a usability feature, not a security feature. The backend is authoritative on every permission. Hiding a button protects nobody.

## 4. End-to-End Business Workflow

This is the workflow the frontend must make visible and operable end to end.

```text
 ┌──────────────────────────────────────────────────────────────────────┐
 │  1. LEAD INTAKE                                                      │
 │     CSV import / API push / CRM sync / inbound DID                   │
 │     → deduplicate → suppression check → assign to campaign           │
 │     UI: Leads module, Import Wizard, Suppression module              │
 └───────────────────────────────┬──────────────────────────────────────┘
                                 ↓
 ┌──────────────────────────────────────────────────────────────────────┐
 │  2. SCRIPT PREPARATION                                               │
 │     Author script → version → submit for approval → approve          │
 │     → activate for campaign (exactly one active per campaign)        │
 │     UI: Script Management module                                     │
 └───────────────────────────────┬──────────────────────────────────────┘
                                 ↓
 ┌──────────────────────────────────────────────────────────────────────┐
 │  3. CAMPAIGN CONFIGURATION                                           │
 │     Dialing hours, retry policy, caller ID pool, DID routing,        │
 │     verifier pool, transfer rules, recording policy                  │
 │     UI: Campaigns module                                             │
 └───────────────────────────────┬──────────────────────────────────────┘
                                 ↓
 ┌──────────────────────────────────────────────────────────────────────┐
 │  4. CALL EXECUTION (backend)                                         │
 │     Dial / answer inbound → greeting → consent → qualification       │
 │     questions → eligibility evaluation                               │
 │     UI: Live Calls monitoring, Live Transcript                       │
 └───────────────────────────────┬──────────────────────────────────────┘
                                 ↓
                ┌────────────────┴─────────────────┐
                ↓                                  ↓
 ┌──────────────────────────┐        ┌───────────────────────────────────┐
 │  5a. QUALIFIED           │        │  5b. NOT QUALIFIED                │
 │  → Transfer to verifier  │        │  → Disposition set → call closed  │
 │  UI: Transfer Console    │        │  UI: Call Detail                  │
 └────────────┬─────────────┘        └───────────────────────────────────┘
              ↓
 ┌──────────────────────────────────────────────────────────────────────┐
 │  6. VERIFICATION                                                     │
 │     Verifier receives caller + summary + transcript + recording link │
 │     → verifies → sets final disposition                              │
 │     UI: Verifier Workspace                                           │
 └───────────────────────────────┬──────────────────────────────────────┘
                                 ↓
 ┌──────────────────────────────────────────────────────────────────────┐
 │  7. QUALITY REVIEW                                                   │
 │     Sampled calls enter QA queue → scorecard → tags → compliance     │
 │     flags → disputes/calibration                                     │
 │     UI: QA module                                                    │
 └───────────────────────────────┬──────────────────────────────────────┘
                                 ↓
 ┌──────────────────────────────────────────────────────────────────────┐
 │  8. REPORTING AND OUTBOUND INTEGRATION                               │
 │     Campaign summary, script performance, lead source quality,       │
 │     bot performance, compliance review → CRM push / export           │
 │     UI: Analytics, Integrations, Audit                               │
 └──────────────────────────────────────────────────────────────────────┘
```

## 5. Frontend Responsibility Boundary

### 5.1 The frontend owns

Authentication UI · Dashboard · Leads and import · Suppression · Campaigns and dialing configuration · Script authoring, versioning, approval and activation · Live call monitoring · Transfer console · Verifier workspace · Call history and call detail · Transcript viewer · Recording playback · QA queue and scorecards · Compliance evidence views · Business analytics · AI performance analytics · System health · Provider status · Integrations configuration · Settings · User management · Audit log views · All loading, empty, error and permission states.

### 5.2 The frontend does not own

Whisper / Parakeet / any STT inference · Silero or any VAD · Qwen or any LLM serving · Chatterbox / CosyVoice / Kokoro or any TTS · AudioSocket · RTP handling · Asterisk dialplan · VICIdial integration · The Medicare eligibility rule engine · Script execution at call time · Redis session state · Queue consumers · Recording worker · Object storage upload · GPU/CUDA concerns · Any decision about whether a caller is qualified.

### 5.3 The two rules that are never negotiable

**Rule A — No media path.** The browser never sits between Asterisk and the AI services. Live audio monitoring, if ever added, is a separate backend-mediated stream and must be approved as a change request.

**Rule B — No business logic.** The frontend renders backend state. It never computes qualification, never decides transfer eligibility, never validates Medicare rules locally.

```typescript
// FORBIDDEN
if (age >= 65 && partA && partB) setQualified(true);

// REQUIRED
render(call.qualification.status); // backend-supplied
```

---

# PART II — INFORMATION ARCHITECTURE

## 6. Complete Route Map

```text
/login
/forgot-password                       (placeholder until backend supports)

/dashboard                             role-aware landing

LEADS
/leads                                 lead list
/leads/import                          import wizard
/leads/[leadId]                        lead detail + call history
/leads/suppression                     DNC / opt-out / suppression lists

CAMPAIGNS
/campaigns                             campaign list
/campaigns/new                         create campaign
/campaigns/[campaignId]                campaign overview
/campaigns/[campaignId]/dialing        hours, retries, caller IDs, pacing
/campaigns/[campaignId]/routing        DID mapping, inbound routing
/campaigns/[campaignId]/script         active script binding + history
/campaigns/[campaignId]/transfer       verifier pool + transfer rules
/campaigns/[campaignId]/performance    campaign analytics

SCRIPTS
/scripts                               script library
/scripts/new                           create script
/scripts/[scriptId]                    script overview + version list
/scripts/[scriptId]/edit               script editor (draft versions only)
/scripts/[scriptId]/versions/[v]       read-only version snapshot
/scripts/[scriptId]/versions/[v]/diff  version comparison
/scripts/[scriptId]/preview            conversation flow simulator
/scripts/approvals                     approval queue

CALLS
/calls                                 call history
/calls/live                            live call monitoring
/calls/[callId]                        call detail (tabbed)

TRANSFERS
/transfers                             transfer monitor (managers)
/transfers/failed                      failed transfer recovery queue

VERIFIER
/verifier                              verifier workspace (incoming + active)
/verifier/history                      verifier's own completed verifications

RECORDINGS
/recordings                            recordings library

QA
/qa                                    QA review queue
/qa/review/[callId]                    review workspace
/qa/scorecards                         scorecard templates
/qa/results                            QA results and trends
/qa/calibration                        calibration sessions

ANALYTICS
/analytics                             business overview
/analytics/campaigns                   daily campaign summary
/analytics/scripts                     script performance by version
/analytics/sources                     lead source quality
/analytics/bot                         bot performance
/analytics/compliance                  compliance review
/analytics/performance                 AI latency / engineering metrics
/analytics/exports                     export history and scheduled exports

SYSTEM
/system                                service health
/system/alerts                         active and historical alerts
/system/integrations                   CRM, webhooks, dialer status

SETTINGS
/settings/general
/settings/telephony
/settings/stt
/settings/tts
/settings/llm
/settings/qualification                eligibility rule sets + versions
/settings/recordings                   recording + retention policy
/settings/compliance                   consent language, calling-hour defaults
/settings/security
/settings/users
/settings/roles

/audit                                 audit log
/profile                               own account

```

## 7. Navigation Model by Role

Sidebar items render from a single `navigation.ts` config filtered by permission key. Never hardcode per-role menus in components.

| Nav group | MASTER_ADMIN | CAMPAIGN_MANAGER | VERIFIER | QA_MANAGER | REPORTING_USER | IT_OPS |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| Dashboard | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Leads | ✓ | ✓ | – | – | – | – |
| Suppression | ✓ | ✓ | – | view | – | – |
| Campaigns | ✓ | ✓ | – | view | view | – |
| Scripts | ✓ | ✓ | – | view | – | – |
| Live Calls | ✓ | ✓ | – | view | – | view |
| Transfers | ✓ | ✓ | own | view | – | – |
| Verifier Workspace | ✓ | – | ✓ | – | – | – |
| Call History | ✓ | ✓ | own | ✓ | view | – |
| Recordings | ✓ | ✓ | own | ✓ | – | – |
| QA | ✓ | view | – | ✓ | view | – |
| Analytics | ✓ | ✓ | – | ✓ | ✓ | – |
| Performance (AI) | ✓ | – | – | – | – | ✓ |
| System Health | ✓ | – | – | – | – | ✓ |
| Integrations | ✓ | – | – | – | – | ✓ |
| Settings | ✓ | limited | – | limited | – | limited |
| Users & Roles | ✓ | – | – | – | – | – |
| Audit | ✓ | – | – | view | – | view |

`own` = scoped to records the user personally handled.

**Default landing route per role:** Master Admin and Campaign Manager → `/dashboard`; Verifier → `/verifier`; QA Manager → `/qa`; Reporting User → `/analytics`; IT/Ops → `/system`.

## 8. Application Shell

```text
┌───────────────────────────────────────────────────────────────────┐
│ TOP BAR                                                           │
│  [☰] TalkFlow    [global search]   [live ●] [alerts 3] [user ▾]   │
├────────────┬──────────────────────────────────────────────────────┤
│            │  BREADCRUMB / PAGE HEADER        [primary action]    │
│  SIDEBAR   ├──────────────────────────────────────────────────────┤
│            │                                                      │
│  grouped   │  PAGE CONTENT                                        │
│  nav,      │                                                      │
│  collapsi- │                                                      │
│  ble,      │                                                      │
│  active    │                                                      │
│  highlight │                                                      │
│            │                                                      │
├────────────┴──────────────────────────────────────────────────────┤
│ TOAST STACK (bottom-right)      CONFIRMATION MODALS (centered)    │
└───────────────────────────────────────────────────────────────────┘
```

Shell requirements:

- Sidebar collapses to icon rail below 1280px and to an overlay drawer below 1024px.
- Live connection indicator is global and always visible: `Live: Connected | Reconnecting | Disconnected`.
- Alert bell surfaces unacknowledged system alerts and failed transfers.
- Global search (⌘K / Ctrl+K) searches calls, leads, and campaigns via a single backend endpoint. Ship in Phase 5; reserve the slot in Phase 1.
- Verifier role gets a **persistent incoming-transfer banner** that is visible on every route, not only inside `/verifier`.

## 9. Design System

The application must read as an operations console: dense, legible, fast, unremarkable. Not a marketing site.

### 9.1 Foundations

| Token group | Decision |
|---|---|
| Component library | shadcn/ui on Radix primitives. Do not hand-roll dialogs, selects, tabs, or tooltips. |
| Icons | Lucide React only |
| Charts | Recharts |
| Font | Inter (UI), JetBrains Mono (IDs, timestamps, latency values) |
| Base size | 14px body, 13px table cells, 12px metadata |
| Density | Compact. Table row height 40px. Card padding 16px. |
| Radius | 6px controls, 8px cards |
| Elevation | Borders over shadows. One shadow level for overlays only. |
| Motion | 120–180ms transitions. No decorative animation. |

### 9.2 Semantic colour

| Meaning | Token | Applied to |
|---|---|---|
| Success | green | Qualified, Healthy, Transfer completed, Approved |
| Danger | red | Disqualified, Offline, Transfer failed, Rejected |
| Warning | amber | Incomplete, Degraded, Pending approval, Retry scheduled |
| Info | blue | Active, In progress, Ringing |
| Neutral | slate | Pending, Draft, Unknown, Archived |
| Accent | violet | Primary actions, active nav, focus rings |

Colour never carries meaning alone. Every status renders as icon + label + colour.

### 9.3 Explicitly avoid

Gradients, glassmorphism, oversized headings, hero sections, decorative illustrations, animated counters, parallax, and any layout that wastes vertical space above the fold of a data table.

## 10. Shared Component Inventory

**Primitives (`components/ui/`)** — Button, IconButton, Input, Textarea, Select, MultiSelect, Combobox, Checkbox, Radio, Switch, Slider, DatePicker, DateRangePicker, TimePicker, Tabs, Dialog, Drawer, Popover, Tooltip, DropdownMenu, Toast, Progress, Skeleton, Badge, Avatar, Separator, ScrollArea, Command (⌘K).

**Data (`components/data/`)** — DataTable (server-driven: pagination, sort, filter, column visibility, row selection, sticky header, empty/loading/error slots), FilterBar, SavedFilters, SearchInput (debounced), Pagination, BulkActionBar, ExportButton, ColumnPicker.

**Status (`components/status/`)** — StatusBadge, CallStatusBadge, QualificationBadge, DispositionBadge, TransferStatusBadge, ScriptStatusBadge, HealthBadge, QaScoreBadge, ConnectionIndicator.

**Domain (`components/domain/`)** — StatCard, TrendStat, CallTable, LiveCallCard, CallSummaryPanel, QualificationPanel, ConsentEvidenceCard, TranscriptViewer, TranscriptMessage, TranscriptSearch, RecordingPlayer, WaveformScrubber, CallTimeline, LatencyCard, ScriptNodeCard, ScriptFlowCanvas, ScriptVersionBadge, ScriptDiffViewer, TransferCard, VerifierCallPanel, ScorecardForm, TagPicker, LeadCard, ImportStepper, HealthCard, ProviderCard, AlertBanner.

**Feedback (`components/feedback/`)** — LoadingSkeleton (per layout shape), EmptyState, ErrorState, PermissionDenied, ConfirmationDialog, DestructiveConfirmation (requires typed confirmation for irreversible actions).

---

# PART III — DOMAIN MODEL AND CONTRACTS

## 11. Enumerations

These enums are shared truth between frontend and backend. They must be agreed before mock data is written. All values are lower `snake_case` on the wire.

### 11.1 Call direction

```text
outbound | inbound
```

### 11.2 Call status (telephony lifecycle)

```text
queued            waiting to be dialled
dialing           dial initiated
ringing           remote ringing
answered          media established
in_progress       bot conversation running
transferring      transfer in flight
transferred       bridged to verifier
completed         call ended normally
failed            technical failure
```

### 11.3 Call outcome / disposition (business result)

```text
TELEPHONY OUTCOMES
no_answer            busy              rejected
voicemail_detected   amd_machine       amd_uncertain
invalid_number       network_failure   abandoned

CONVERSATION OUTCOMES
caller_hung_up_early     consent_refused     opted_out
language_barrier         silence_no_response script_completed

QUALIFICATION OUTCOMES
qualified_transferred    qualified_transfer_failed
disqualified_age         disqualified_no_part_a
disqualified_no_part_b   disqualified_coverage
disqualified_state       disqualified_other
incomplete               callback_requested

VERIFIER OUTCOMES
verified_accepted    verified_rejected    verifier_no_contact
```

Without this taxonomy, contact rate, answered calls, and transfer success rate required by PRD FR-11 cannot be computed. v1.0's four-state enum is insufficient.

### 11.4 Qualification status

```text
pending | in_progress | qualified | disqualified | incomplete | failed
```

### 11.5 Transfer status

```text
not_applicable | initiated | ringing_verifier | bridged | completed
failed_no_verifier | failed_timeout | failed_rejected | failed_technical
retry_scheduled | fallback_queued | callback_created
```

### 11.6 Script status

```text
draft | pending_approval | approved | active | archived | rejected
```

### 11.7 Lead status

```text
new | queued | in_progress | contacted | qualified | disqualified
callback | do_not_call | exhausted | invalid | suppressed
```

### 11.8 Recording status

```text
pending | waiting_for_source | fetching | validating | storing | ready | failed | purged
```

### 11.9 QA review status

```text
unassigned | assigned | in_review | completed | disputed | calibrated
```

### 11.10 Health status

```text
healthy | degraded | offline | unknown
```

## 12. Core TypeScript Models

Place in `src/types/`. These are the contract. Any backend divergence is a blocking issue, not a frontend workaround.

```typescript
// ---------- common ----------
export type ISODateTime = string; // always UTC, e.g. "2026-09-11T14:21:06Z"

export interface Paginated<T> {
  data: T[];
  meta: {
    page: number;
    pageSize: number;
    total: number;
    totalPages: number;
    sort?: string;
    order?: "asc" | "desc";
  };
}

export interface ApiError {
  code: string;          // machine-readable, e.g. "script.not_approved"
  message: string;       // human-safe, displayable
  status: number;
  details?: Record<string, string[]>; // field-level validation
  traceId?: string;
}

// ---------- auth ----------
export type Role =
  | "MASTER_ADMIN" | "CAMPAIGN_MANAGER" | "VERIFIER"
  | "QA_MANAGER" | "REPORTING_USER" | "IT_OPS";

export interface CurrentUser {
  id: string;
  name: string;
  email: string;
  role: Role;
  permissions: string[];   // authoritative list from backend
  status: "active" | "disabled" | "invited";
  timezone: string;
  lastLoginAt?: ISODateTime;
}

// ---------- lead ----------
export interface Lead {
  id: string;
  firstName?: string;
  lastName?: string;
  phone: string;
  altPhone?: string;
  email?: string;
  state?: string;
  zipCode?: string;
  dateOfBirth?: string;
  age?: number;
  source: string;
  sourceBatchId?: string;
  campaignId?: string;
  status: LeadStatus;
  attempts: number;
  lastAttemptAt?: ISODateTime;
  nextAttemptAt?: ISODateTime;
  assignedTo?: string;
  suppressed: boolean;
  suppressionReason?: string;
  customFields?: Record<string, string>;
  createdAt: ISODateTime;
  updatedAt: ISODateTime;
}

export interface LeadImportJob {
  id: string;
  fileName: string;
  status: "uploading" | "mapping" | "validating" | "importing" | "completed" | "failed";
  totalRows: number;
  importedRows: number;
  duplicateRows: number;
  suppressedRows: number;
  invalidRows: number;
  errorReportUrl?: string;
  campaignId?: string;
  createdBy: string;
  createdAt: ISODateTime;
}

// ---------- script ----------
export type ScriptNodeType =
  | "greeting" | "consent" | "question" | "statement"
  | "condition" | "fallback" | "transfer" | "closing" | "opt_out";

export interface ScriptNode {
  id: string;
  type: ScriptNodeType;
  label: string;
  prompt: string;                   // spoken text
  captureField?: string;            // e.g. "medicare_part_a"
  captureType?: "boolean" | "number" | "text" | "zip" | "date" | "choice";
  choices?: string[];
  required: boolean;
  maxRetries: number;
  noResponseMs: number;
  fallbackPrompt?: string;
  transitions: ScriptTransition[];
  allowBargeIn: boolean;
}

export interface ScriptTransition {
  id: string;
  when: "always" | "yes" | "no" | "no_response" | "invalid" | "expression";
  expression?: string;              // evaluated by BACKEND only
  nextNodeId?: string;
  endCall?: boolean;
  disposition?: string;
}

export interface ScriptVersion {
  version: number;
  status: ScriptStatus;
  nodes: ScriptNode[];
  entryNodeId: string;
  ruleSetId?: string;               // eligibility rule set bound to this version
  changeNote?: string;
  createdBy: string;
  createdAt: ISODateTime;
  submittedBy?: string;
  submittedAt?: ISODateTime;
  approvedBy?: string;
  approvedAt?: ISODateTime;
  rejectedReason?: string;
  activatedAt?: ISODateTime;
  campaignIds: string[];
}

export interface Script {
  id: string;
  name: string;
  description?: string;
  language: string;
  currentVersion: number;
  activeVersion?: number;
  status: ScriptStatus;
  versions: ScriptVersionSummary[];
  createdAt: ISODateTime;
  updatedAt: ISODateTime;
}

// ---------- campaign ----------
export interface Campaign {
  id: string;
  name: string;
  status: "draft" | "active" | "paused" | "stopped" | "archived";
  scriptId?: string;
  activeScriptVersion?: number;
  vicidialCampaignId?: string;
  inboundDids: string[];
  callerIds: string[];
  dialing: {
    timezone: string;
    allowedDays: number[];              // 0-6
    allowedHours: { start: string; end: string }[];
    maxAttempts: number;
    retryIntervalMinutes: number;
    dailyCallCap?: number;
    concurrencyLimit?: number;
    amdEnabled: boolean;
    voicemailAction: "hangup" | "leave_message" | "retry";
  };
  transfer: {
    verifierGroupId?: string;
    ringTimeoutSeconds: number;
    maxTransferAttempts: number;
    fallbackAction: "queue" | "callback" | "voicemail" | "end";
    warmTransfer: boolean;
  };
  recording: { enabled: boolean; retentionDays: number };
  createdAt: ISODateTime;
  updatedAt: ISODateTime;
}

// ---------- call ----------
export interface QualificationField {
  field: string;
  label: string;
  value: string | number | boolean | null;
  capturedAt?: ISODateTime;
  transcriptRef?: string;   // links to transcript turn
  confidence?: number;
  required: boolean;
}

export interface Qualification {
  status: QualificationStatus;
  fields: QualificationField[];
  disqualificationReason?: string;
  ruleSetId?: string;
  ruleSetVersion?: number;
  evaluatedAt?: ISODateTime;
}

export interface ConsentEvidence {
  captured: boolean;
  consentLanguageVersion?: string;
  capturedAt?: ISODateTime;
  recordingOffsetMs?: number;   // jump-to point in audio
  transcriptRef?: string;
  method: "verbal" | "ivr_keypress" | "not_captured";
}

export interface TransferRecord {
  status: TransferStatus;
  initiatedAt?: ISODateTime;
  bridgedAt?: ISODateTime;
  endedAt?: ISODateTime;
  verifierId?: string;
  verifierName?: string;
  attempts: number;
  waitSeconds?: number;
  failureReason?: string;
  fallbackAction?: string;
}

export interface Call {
  id: string;
  reference: string;              // human-readable, e.g. "TF-20981"
  direction: CallDirection;
  status: CallStatus;
  disposition?: Disposition;
  leadId?: string;
  campaignId: string;
  campaignName: string;
  scriptId?: string;
  scriptVersion?: number;
  caller: { number: string; masked: string; name?: string; state?: string };
  didUsed?: string;
  callerIdUsed?: string;
  attemptNumber: number;
  startedAt: ISODateTime;
  answeredAt?: ISODateTime;
  endedAt?: ISODateTime;
  durationSeconds?: number;
  talkTimeSeconds?: number;
  qualification: Qualification;
  consent: ConsentEvidence;
  transfer: TransferRecord;
  recording?: { status: RecordingStatus; durationSeconds?: number; sizeBytes?: number };
  qaStatus?: QaReviewStatus;
  qaScore?: number;
  currentNodeId?: string;         // live only
  liveState?: LiveCallState;      // live only
}

export type LiveCallState =
  | "connecting" | "greeting" | "listening" | "caller_speaking"
  | "thinking" | "tts_generating" | "bot_speaking" | "interrupted"
  | "transferring" | "ending";

// ---------- transcript ----------
export interface TranscriptTurn {
  id: string;
  speaker: "bot" | "caller" | "verifier" | "system";
  text: string;
  startMs: number;
  endMs?: number;
  nodeId?: string;
  isFinal: boolean;
  confidence?: number;
  redacted?: boolean;
}

// ---------- qa ----------
export interface ScorecardCriterion {
  id: string;
  label: string;
  description?: string;
  weight: number;
  type: "boolean" | "scale_1_5" | "na_allowed";
  autoFail: boolean;
}

export interface QaReview {
  id: string;
  callId: string;
  status: QaReviewStatus;
  reviewerId?: string;
  reviewerName?: string;
  scorecardId: string;
  scores: { criterionId: string; value: number | boolean | null; note?: string }[];
  totalScore?: number;
  autoFailed: boolean;
  tags: string[];
  complianceFlags: string[];
  comments?: string;
  disputed: boolean;
  disputeNote?: string;
  reviewedAt?: ISODateTime;
}

// ---------- system ----------
export interface ServiceHealth {
  key: string;
  label: string;
  status: HealthStatus;
  latencyMs?: number;
  version?: string;
  activeRequests?: number;
  lastCheckedAt: ISODateTime;
  message?: string;
}

export interface SystemAlert {
  id: string;
  severity: "critical" | "warning" | "info";
  source: string;
  title: string;
  message: string;
  raisedAt: ISODateTime;
  acknowledgedBy?: string;
  acknowledgedAt?: ISODateTime;
  resolvedAt?: ISODateTime;
}
```

## 13. API Response Envelope

Every endpoint returns one of three shapes. Freeze this before mocks are written.

```jsonc
// single resource
{ "data": { /* object */ } }

// collection
{ "data": [ /* items */ ], "meta": { "page": 1, "pageSize": 25, "total": 1248, "totalPages": 50 } }

// error
{ "error": { "code": "script.not_approved", "message": "Script must be approved before activation.", "status": 409, "details": { "version": ["not approved"] }, "traceId": "..." } }
```

Rules: pagination is offset-based (`page`, `pageSize`); filters are flat query params; sorting is `sort=field&order=asc`; all timestamps are UTC ISO-8601 with `Z`; all IDs are strings.

## 14. REST Endpoint Catalogue

```text
AUTH
POST   /api/v1/auth/login
POST   /api/v1/auth/logout
POST   /api/v1/auth/refresh
GET    /api/v1/auth/me

LEADS
GET    /api/v1/leads
POST   /api/v1/leads
GET    /api/v1/leads/{id}
PATCH  /api/v1/leads/{id}
POST   /api/v1/leads/bulk-assign
POST   /api/v1/leads/import                 multipart upload
GET    /api/v1/leads/import/{jobId}
POST   /api/v1/leads/import/{jobId}/mapping
POST   /api/v1/leads/import/{jobId}/commit
GET    /api/v1/leads/import/{jobId}/errors   downloadable report
GET    /api/v1/suppression
POST   /api/v1/suppression
POST   /api/v1/suppression/import
DELETE /api/v1/suppression/{id}
GET    /api/v1/suppression/check?phone=

SCRIPTS
GET    /api/v1/scripts
POST   /api/v1/scripts
GET    /api/v1/scripts/{id}
PATCH  /api/v1/scripts/{id}
POST   /api/v1/scripts/{id}/duplicate
GET    /api/v1/scripts/{id}/versions
GET    /api/v1/scripts/{id}/versions/{v}
POST   /api/v1/scripts/{id}/versions                create draft from version
PATCH  /api/v1/scripts/{id}/versions/{v}            edit draft only
POST   /api/v1/scripts/{id}/versions/{v}/submit
POST   /api/v1/scripts/{id}/versions/{v}/approve
POST   /api/v1/scripts/{id}/versions/{v}/reject
POST   /api/v1/scripts/{id}/versions/{v}/activate   body: { campaignId }
GET    /api/v1/scripts/{id}/versions/{v}/diff?against={v2}
POST   /api/v1/scripts/{id}/versions/{v}/simulate   preview flow
GET    /api/v1/scripts/approvals                    pending queue

CAMPAIGNS
GET    /api/v1/campaigns
POST   /api/v1/campaigns
GET    /api/v1/campaigns/{id}
PATCH  /api/v1/campaigns/{id}
POST   /api/v1/campaigns/{id}/start
POST   /api/v1/campaigns/{id}/pause
POST   /api/v1/campaigns/{id}/stop
GET    /api/v1/campaigns/{id}/stats

CALLS
GET    /api/v1/calls
GET    /api/v1/calls/live
GET    /api/v1/calls/{id}
PATCH  /api/v1/calls/{id}/disposition
GET    /api/v1/calls/{id}/transcript
GET    /api/v1/calls/{id}/timeline
GET    /api/v1/calls/{id}/performance
GET    /api/v1/calls/{id}/script-path
GET    /api/v1/calls/{id}/recording
GET    /api/v1/calls/{id}/recording/playback-url
POST   /api/v1/calls/{id}/recording/download-token

TRANSFERS
GET    /api/v1/transfers
GET    /api/v1/transfers/failed
POST   /api/v1/transfers/{id}/retry
POST   /api/v1/transfers/{id}/create-callback

VERIFIER
GET    /api/v1/verifier/queue
GET    /api/v1/verifier/active
POST   /api/v1/verifier/availability          body: { available: boolean }
POST   /api/v1/verifier/calls/{id}/accept
POST   /api/v1/verifier/calls/{id}/reject
POST   /api/v1/verifier/calls/{id}/disposition
GET    /api/v1/verifier/history

QA
GET    /api/v1/qa/queue
POST   /api/v1/qa/assign
GET    /api/v1/qa/reviews/{id}
POST   /api/v1/qa/reviews
PATCH  /api/v1/qa/reviews/{id}
POST   /api/v1/qa/reviews/{id}/dispute
GET    /api/v1/qa/scorecards
POST   /api/v1/qa/scorecards
GET    /api/v1/qa/results
GET    /api/v1/qa/tags

RECORDINGS
GET    /api/v1/recordings

ANALYTICS
GET    /api/v1/analytics/summary
GET    /api/v1/analytics/campaigns
GET    /api/v1/analytics/scripts
GET    /api/v1/analytics/sources
GET    /api/v1/analytics/bot
GET    /api/v1/analytics/compliance
GET    /api/v1/analytics/performance
POST   /api/v1/exports                     body: { report, filters, format }
GET    /api/v1/exports
GET    /api/v1/exports/{id}/download

SYSTEM
GET    /api/v1/health
GET    /api/v1/providers
GET    /api/v1/alerts
POST   /api/v1/alerts/{id}/acknowledge
GET    /api/v1/integrations
PATCH  /api/v1/integrations/{key}
POST   /api/v1/integrations/{key}/test
GET    /api/v1/integrations/{key}/failures
POST   /api/v1/integrations/{key}/failures/{id}/retry

SETTINGS / ADMIN
GET    /api/v1/settings
PATCH  /api/v1/settings
GET    /api/v1/rule-sets
POST   /api/v1/rule-sets
GET    /api/v1/users
POST   /api/v1/users
PATCH  /api/v1/users/{id}
POST   /api/v1/users/{id}/disable
GET    /api/v1/roles
GET    /api/v1/audit
GET    /api/v1/search?q=
```

## 15. WebSocket Event Catalogue

Single authenticated connection per session. Clients subscribe to channels; the server fans out only what the role may see.

```text
CHANNELS
dashboard                 aggregate counters
calls.live                all live calls (managers, QA)
call.{callId}             one call's detail stream
verifier.{userId}         personal transfer queue
transfers                 transfer monitor
system                    health + alerts
```

```text
EVENTS
call.started              call.answered           call.state_changed
call.node_changed         call.completed          call.failed
transcript.partial        transcript.final
qualification.field_updated                       qualification.evaluated
consent.captured
transfer.initiated        transfer.ringing        transfer.bridged
transfer.completed        transfer.failed         transfer.retry_scheduled
verifier.transfer_offered verifier.transfer_taken verifier.transfer_expired
recording.status_changed
campaign.stats_updated    dashboard.counters_updated
system.health_changed     system.alert_raised     system.alert_resolved
lead.import_progress
```

Every event carries `type`, `timestamp`, `seq` (monotonic per channel), and a correlation id (`call_id`, `lead_id`, `job_id`).

```jsonc
{
  "type": "transfer.ringing",
  "seq": 10482,
  "timestamp": "2026-09-11T14:21:06Z",
  "call_id": "96cfeefd-fc31-4ac7-b856-74f7ff717ab8",
  "payload": { "verifier_id": "u_312", "attempt": 1, "timeout_seconds": 25 }
}
```

Client requirements: authenticate on open, resubscribe on reconnect, exponential backoff (1s → 30s cap), drop events with `seq` lower than the last applied per channel, reconcile via REST refetch after any reconnect gap, and clean up subscriptions on unmount.

## 16. Error Taxonomy and Handling

| Status | Meaning | UI behaviour |
|---|---|---|
| 400 | Validation | Inline field errors from `details`; do not toast |
| 401 | Session expired | Clear auth state, redirect to `/login?reason=expired`. No retry loop. |
| 403 | Forbidden | Render `PermissionDenied` panel in place of content |
| 404 | Not found | Render not-found state with back link |
| 409 | Conflict (e.g. activating unapproved script) | Blocking dialog explaining the conflict |
| 422 | Business rule rejection | Inline message using `error.message` verbatim |
| 429 | Rate limited | Toast with retry-after; disable the action temporarily |
| 5xx | Server failure | `ErrorState` with Retry; log `traceId` to console in non-production only |

Never render a stack trace, a raw JSON body, or a `traceId` to a non-admin user.

---

# PART IV — MODULE SPECIFICATIONS

Each module below follows the same structure: purpose, screens, behaviour, states, permissions, and acceptance criteria.

## 17. Authentication and Session

**Screens:** `/login`, `/forgot-password` (placeholder).

**Login page:** email, password with show/hide, remember me, submit with loading state, inline error, session-expired notice when `?reason=expired`, product wordmark. No marketing copy.

**Session behaviour:**

- Token stored per backend guidance. Prefer httpOnly cookie; if bearer token is mandated, keep it in memory with silent refresh, never in `localStorage`.
- All dashboard routes sit behind an auth guard in the `(dashboard)` layout.
- On any `401`, clear state once, cancel in-flight queries, disconnect WebSocket, redirect.
- Idle timeout warning at T-2 minutes with "Stay signed in".
- On logout: clear query cache, close socket, wipe any cached call data.

**Acceptance:** unauthenticated access to any dashboard route redirects; expired session shows an explicit message; no infinite refresh loop under a persistently failing refresh endpoint.

## 18. Dashboard

**Route:** `/dashboard`. Role-aware content, same shell.

### 18.1 KPI row (PRD FR-11)

```text
Calls Today        Answered        Contact Rate      Active Calls
Qualified          Qualification   Transfers         Transfer Rate
                   Rate
Verifier           Avg Handle      Avg Call          Disqualified
Acceptance Rate    Time            Duration
```

Each KPI card shows: value, label, period-over-period delta with direction, and a sparkline where the backend supplies a series. Cards link to the filtered view that explains them.

### 18.2 Panels

| Panel | Content |
|---|---|
| Live activity | Active calls count by state, verifiers available, transfers in flight. WebSocket-driven. |
| Calls over time | Line chart, hourly for today / daily for ranges |
| Outcome breakdown | Stacked bar: qualified / disqualified / incomplete / no-contact |
| Disqualification reasons | Horizontal bar, top 6 reasons (PRD FR-11 explicitly requires this) |
| Campaign leaderboard | Calls, qualification rate, transfer rate, active script version |
| Recent calls | Last 10, compact, links to detail |
| Attention required | Failed transfers, failed imports, unacknowledged alerts, scripts awaiting approval |

### 18.3 Role variants

- Campaign Manager: scoped to assigned campaigns.
- QA Manager: replaces transfer KPIs with QA backlog, average QA score, open compliance flags.
- Verifier: replaced entirely by `/verifier`.
- IT/Ops: replaces business KPIs with service health, error rate, queue depth.

**Acceptance:** every KPI traces to a documented backend field; no KPI is computed in the browser from raw rows.

## 19. Leads Module *(new in v2 — PRD FR-01)*

### 19.1 Lead list — `/leads`

Server-driven table.

| Column | Notes |
|---|---|
| Name | links to lead detail |
| Phone | masked by permission |
| State / ZIP | |
| Source | lead vendor / batch |
| Campaign | |
| Status | `LeadStatus` badge |
| Attempts | `2 / 5` format |
| Last attempt | relative + absolute on hover |
| Next attempt | scheduled retry |
| Assigned to | |
| Suppressed | flag icon with reason tooltip |

**Filters:** status, campaign, source, batch, state, ZIP, age range, attempts range, date created, last attempt range, suppressed yes/no, has qualified call.
**Search:** name, phone, email, lead ID.
**Bulk actions:** assign to campaign, change status, add to suppression, export selection. All bulk actions require confirmation showing the affected count and are audit-logged.

### 19.2 Import wizard — `/leads/import`

A five-step stepper. Each step is a distinct URL state so a refresh does not lose progress.

```text
STEP 1  UPLOAD
        Drag-drop CSV/XLSX. Show file name, size, row count estimate.
        Client-side guard: extension, size cap, non-empty.

STEP 2  MAP FIELDS
        Table: source column → TalkFlow field → sample values (first 3 rows).
        Required: phone. Recommended: first name, last name, state, zip, dob.
        Unmapped columns can be stored as custom fields.
        Save mapping as a reusable template per source.

STEP 3  VALIDATE
        Backend validates. Display counts:
          valid | invalid format | duplicates in file | duplicates in system
          | suppressed / DNC matches | outside allowed states
        Downloadable error report (row number + reason).
        Options: skip invalid, skip duplicates, update existing.

STEP 4  ASSIGN
        Target campaign, initial status, priority, optional assigned user.

STEP 5  COMMIT
        Progress bar driven by lead.import_progress WebSocket events.
        Summary on completion with links to imported set.
```

**Rules:** the browser never parses or validates the full file — it uploads and renders backend results. Import is resumable and idempotent; a double-commit must not double-import.

### 19.3 Lead detail — `/leads/[leadId]`

Header: name, phone, status, campaign, source, suppression state, primary actions (call now if permitted, add to suppression, edit, reassign).

Tabs: **Overview** (all fields, editable inline with permission) · **Call history** (every attempt, outcome, disposition, recording link) · **Qualification** (latest captured values with the call they came from) · **Activity** (audit trail scoped to this lead).

### 19.4 Suppression / DNC — `/leads/suppression` *(PRD §8)*

Table: phone, reason (`internal_dnc`, `federal_dnc`, `caller_request`, `complaint`, `litigator`, `invalid`), source, added by, added at, expires at, evidence reference.

Actions: add single, bulk import, search-check a number before dialling, remove (Master Admin only, with typed confirmation and mandatory reason).

**Acceptance:** a suppressed number is visibly blocked everywhere it appears; the suppression check endpoint is reachable from the lead detail page; every add/remove appears in the audit log.

## 20. Campaigns Module *(expanded — PRD FR-02, FR-03)*

### 20.1 Campaign list — `/campaigns`

Columns: name, status, active script + version, leads remaining, calls today, contact rate, qualification rate, transfer rate, average duration, verifier group. Row actions: start / pause / stop (confirmation required), open, duplicate.

### 20.2 Campaign overview — `/campaigns/[id]`

Summary header with live counters, active script chip linking to the exact version, and status control. Below: today's funnel (leads dialled → answered → consented → qualified → transferred → verified), and an alert strip for misconfiguration (no active script, no verifier group, outside calling hours, empty lead pool).

### 20.3 Dialing configuration — `/campaigns/[id]/dialing`

```text
Timezone                        select (campaign-local, drives calling hours)
Allowed days                    Mon–Sun toggles
Allowed hours                   one or more windows, e.g. 09:00–20:00
Max attempts per lead           number
Retry interval                  minutes, with per-outcome overrides:
                                  no_answer → 240m   busy → 30m
                                  voicemail → 1440m  network_failure → 15m
Daily call cap                  optional
Concurrency limit               optional
AMD enabled                     switch
Voicemail action                hangup | leave message | retry
Suppression enforcement         read-only indicator (always on)
```

The form must show a live "next available calling window" computed from the selected timezone so a Pakistan-based operator immediately understands US dialling hours.

### 20.4 Routing — `/campaigns/[id]/routing`

Inbound DID list with per-DID script override, caller-ID pool for outbound, VICIdial campaign mapping (read-only if backend-owned), and overflow queue target.

### 20.5 Script binding — `/campaigns/[id]/script`

Shows the currently active script and version, who activated it and when, and the full activation history for this campaign. Changing the active script opens the activation dialog described in §21.7.

### 20.6 Transfer configuration — `/campaigns/[id]/transfer`

Verifier group, ring timeout, max transfer attempts, warm vs cold transfer, fallback action (`queue` / `callback` / `voicemail` / `end`), and the transfer message node reference from the active script.

**Acceptance:** a campaign cannot be started from the UI while the backend reports it as unconfigured; the API's rejection reason is displayed verbatim rather than pre-empted by frontend validation.

## 21. Script Management Module *(new in v2 — PRD FR-05, §7)*

This is the flagship requirement of PRD v1.1 and was entirely absent from v1.0. It is P0.

### 21.1 Concepts

- A **Script** is a named container. It has many **Versions**.
- Only a **draft** version is editable. Approved and active versions are immutable.
- Exactly **one approved version may be active per campaign** at any time.
- Every call record stores the script id and version it ran, permanently.
- Editing an approved script creates a **new draft version**. It never mutates history.

### 21.2 Version lifecycle

```text
  draft ──submit──▶ pending_approval ──approve──▶ approved ──activate──▶ active
    ▲                      │                           │                    │
    │                   reject                    duplicate            superseded
    └──────edit────────────┘                          │                    │
                                                      ▼                    ▼
                                                    draft               archived
```

State transitions are backend-enforced. The UI disables invalid actions and explains why on hover.

### 21.3 Script library — `/scripts`

Columns: name, language, active version, draft version, status, campaigns using it, last edited by, last edited at, qualification rate of the active version (from analytics). Actions: new, duplicate, open, archive.

### 21.4 Script editor — `/scripts/[id]/edit`

Three-pane layout.

```text
┌────────────┬──────────────────────────────┬───────────────────┐
│ NODE LIST  │  NODE EDITOR                 │  FLOW PREVIEW     │
│            │                              │                   │
│ 1 Greeting │  Label                       │  visual graph of  │
│ 2 Consent  │  Type      [question ▾]      │  nodes and        │
│ 3 Name     │  Prompt    [spoken text]     │  transitions;     │
│ 4 Age      │  Capture   [age / number]    │  click to select; │
│ 5 Part A   │  Required  [x]               │  highlights       │
│ 6 Part B   │  Max retries [2]             │  orphaned nodes   │
│ 7 ZIP      │  No-response [4000 ms]       │  and dead ends    │
│ 8 Transfer │  Fallback prompt [...]       │                   │
│ 9 Closing  │  Barge-in   [x]              │                   │
│ + Add node │  Transitions:                │                   │
│            │    yes → Part B              │                   │
│            │    no  → Disqualify (no_part_a)│                 │
│            │    no_response → Fallback    │                   │
└────────────┴──────────────────────────────┴───────────────────┘
```

**Node types:** greeting, consent, question, statement, condition, fallback, transfer, closing, opt_out.

**Editor requirements:**

- Autosave drafts with explicit "Saved ·  14:22" indicator and manual save.
- Character/duration estimate per prompt (approximate speech seconds) so authors keep turns short.
- Variable insertion (`{first_name}`, `{campaign_name}`) from a backend-supplied token list.
- Validation panel listing structural problems: unreachable nodes, missing transitions, no transfer path, no opt-out node, required capture field missing, consent node not before first data capture. Submission is blocked while structural errors exist.
- Condition expressions are authored as structured rows (field, operator, value), never as free-form code, and are evaluated only by the backend.
- Keyboard navigation between nodes; no drag-only interactions.

### 21.5 Preview / simulator — `/scripts/[id]/preview`

A conversation simulator that walks the flow. The frontend sends the chosen answers to `POST /versions/{v}/simulate` and renders the backend's resolved path. It must never evaluate the branching itself.

Displays: bot turn, available caller responses, the node reached, the fields captured so far, and the terminal outcome. Includes a "path taken" trace and an option to replay a real call's answers against a draft version.

### 21.6 Version history and diff

`/scripts/[id]` lists every version with version number, status, author, timestamps, approver, change note, campaigns it was active on, and date range of activity.

`/scripts/[id]/versions/[v]/diff?against=[v2]` renders a side-by-side comparison: added, removed and modified nodes; prompt text diffs at word level; transition changes; and rule set changes.

### 21.7 Approval and activation

**Approval queue — `/scripts/approvals`:** pending versions with author, submitted date, change note, diff link, and approve/reject actions. Rejection requires a reason. Approvers cannot approve their own submission if the backend enforces separation of duties; the UI reflects that rule.

**Activation dialog:** select campaign(s), show the currently active version being replaced, show a diff summary, warn that in-flight calls continue on the old version while new calls use the new one, and require typed confirmation of the version number. Activation is audit-logged with actor, timestamp, campaign, and both version numbers.

### 21.8 Acceptance criteria

- An approved version cannot be edited from the UI under any interaction path.
- Activating a non-approved version is impossible from the UI and is rejected by the backend.
- Every call detail page links to the exact script version that ran.
- Version history survives edits; no destructive overwrite exists in the UI.
- Analytics can be filtered by script version (§33.3).

## 22. Live Calls Monitoring

**Route:** `/calls/live`.

### 22.1 Layout

Header strip: active calls, by state, verifiers available, transfers in flight, connection indicator.

Grid of live call cards (default) with a table toggle for high volume.

```text
┌───────────────────────────────────────────────────┐
│ TF-20981          ● CALLER SPEAKING       01:37   │
│ (214) ***-8219 · Medicare Q4 · script v7          │
│ Node: Asking Part B          Attempt 2            │
├───────────────────────────────────────────────────┤
│ Consent  ✓    Name  Daniel Smith    Age  67       │
│ Part A   ✓    Part B  …waiting      ZIP  —        │
├───────────────────────────────────────────────────┤
│ [ View transcript ]              [ Open detail ]  │
└───────────────────────────────────────────────────┘
```

### 22.2 Live state indicators

`connecting · greeting · listening · caller_speaking · thinking · tts_generating · bot_speaking · interrupted · transferring · ending`

All states come from `call.state_changed` events. The frontend never infers state from timing, transcript content, or absence of events.

### 22.3 Live transcript

Chronological turns with distinct styling for bot, caller and system. Partial ASR results render in a muted style and are replaced in place by the final turn. Auto-scroll pins to the bottom unless the user scrolls up, in which case a "jump to latest" control appears.

Debug mode (admin/IT only) additionally exposes partial vs final markers, node ids, and confidence values.

### 22.4 Performance

Cap the rendered live set (default 50 cards) with an overflow counter. Batch WebSocket updates into animation frames. Never re-render the entire grid on a single transcript event.

## 23. Transfer Module *(new in v2 — PRD FR-08)*

### 23.1 Transfer monitor — `/transfers`

Live table of transfers: call reference, caller, campaign, qualified at, transfer status, verifier, wait time, attempts, outcome. Filterable by status and campaign, sortable by wait time.

A prominent counter strip: `In flight · Waiting for verifier · Failed today · Average wait`.

### 23.2 Transfer state display

```text
initiated ──▶ ringing_verifier ──▶ bridged ──▶ completed
                   │
                   ├──▶ failed_no_verifier
                   ├──▶ failed_timeout
                   ├──▶ failed_rejected
                   └──▶ failed_technical
                            │
                            ├──▶ retry_scheduled
                            ├──▶ fallback_queued
                            └──▶ callback_created
```

Each failed transfer shows the failure reason, the fallback action taken, and the caller's current disposition.

### 23.3 Failed transfer recovery — `/transfers/failed`

PRD §13 names transfer failure as a key risk with alerting and fallback as mitigation. This queue is the operational answer.

Per row: caller, campaign, qualification summary, failure reason, time since failure, attempts made. Actions: retry transfer, create callback task, assign to a specific verifier, mark as lost with reason. Every action is confirmed and audit-logged.

An unresolved failed transfer older than a configurable threshold raises a banner in the shell for Campaign Managers.

### 23.4 Acceptance

- Transfer status appears as a column in call history and as a tab in call detail.
- A qualified call that failed to transfer is never displayed as a successful outcome anywhere, including analytics.
- Retry actions are idempotent from the UI (button disables on submit, no double-fire).

## 24. Verifier Workspace *(new in v2 — PRD §4, §5 step 5)*

The Verifier is a first-class PRD role whose entire job had no interface in v1.0.

### 24.1 Availability control

A persistent availability toggle in the shell: `Available · Busy · Away`. Changing it calls the backend; the UI reflects the backend's confirmed state, not the optimistic one. Going unavailable while a transfer is offered is blocked with an explanation.

### 24.2 Incoming transfer

When `verifier.transfer_offered` arrives, a full-width banner appears on every route with an audible cue (user-enabled, default on):

```text
┌──────────────────────────────────────────────────────────────┐
│ ● INCOMING TRANSFER — Daniel Smith · Medicare Q4    00:18    │
│   Age 67 · Part A ✓ · Part B ✓ · ZIP 75001 · TX              │
│                                  [ Decline ]   [ Accept ]    │
└──────────────────────────────────────────────────────────────┘
```

A countdown reflects the campaign's ring timeout. On expiry the banner clears itself from a server event, never from a local timer alone.

### 24.3 Active verification screen — `/verifier`

```text
┌─────────────────────────────┬──────────────────────────────┐
│ CALLER SUMMARY              │  BOT CONVERSATION            │
│  Daniel Smith               │  full transcript of the      │
│  (214) 555-8219  · TX       │  qualification portion,      │
│  Lead source: Vendor A      │  scrollable, searchable      │
│  Campaign: Medicare Q4      │                              │
│  Script: v7                 │                              │
├─────────────────────────────┤                              │
│ QUALIFICATION CAPTURED      │                              │
│  Consent      ✓ 00:12       │                              │
│  Age          67            │                              │
│  Medicare A   Yes           │                              │
│  Medicare B   Yes           │                              │
│  ZIP          75001         │                              │
│  Result       QUALIFIED     │                              │
├─────────────────────────────┼──────────────────────────────┤
│ VERIFICATION NOTES          │  DISPOSITION                 │
│  [free text]                │  [ verified_accepted ▾ ]     │
│                             │  reason (if rejected)        │
│                             │  [ Submit & Close ]          │
└─────────────────────────────┴──────────────────────────────┘
```

Requirements: the qualification panel is read-only; the verifier corrects data only through an explicit "correct value" action that records the original alongside the correction; submission requires a disposition; closing without disposition is blocked.

### 24.4 Verifier history — `/verifier/history`

The verifier's own completed verifications with disposition, duration, and QA outcome where available. Scoped to `own` records.

### 24.5 Acceptance

- The incoming-transfer banner is visible regardless of current route.
- Accept/decline is driven by server confirmation; two verifiers can never both hold one call.
- Final disposition writes through `POST /verifier/calls/{id}/disposition` and appears in the call record and audit log.

## 25. Call History

**Route:** `/calls`. Server-driven table, the workhorse screen for supervisors and QA.

**Columns (configurable, with sensible defaults):** reference, date/time, direction, caller (masked by permission), lead name, campaign, script version, duration, call status, disposition, qualification, transfer status, verifier, consent, recording, QA score.

**Filters:** date range, campaign, script + version, direction, call status, disposition (grouped by category), qualification status, transfer status, verifier, has recording, consent captured, QA status, QA score range, duration range, attempt number, state, ZIP, age range, lead source.

**Search:** call reference, caller number, lead name, lead id.

**Requirements:** server-side pagination, sorting and filtering; debounced search (300ms); saved filter presets per user; filter state encoded in the URL so views are shareable; column visibility persisted locally; export of the current filtered view via the export pipeline (never a client-side dump).

**Never** fetch the full history into the browser. **Never** render thousands of rows at once.

## 26. Call Detail

**Route:** `/calls/[callId]`. Tabs: Overview · Transcript · Recording · Script Path · Transfer · Timeline · Performance · QA · Technical.

### 26.1 Overview

Header: reference, direction, status badge, disposition badge, campaign, script version chip (links to the exact version), lead link, attempt number, start/end/duration, DID and caller ID used.

Panels:
- **Qualification** — every field with captured value, capture timestamp, and a link that jumps the transcript to the turn it came from. Final result rendered exactly as the backend returns it. Disqualification reason shown when present.
- **Consent evidence** — captured yes/no, consent language version, timestamp, and a "play from consent" control that seeks the recording to `recordingOffsetMs`.
- **Transfer summary** — status, verifier, wait time, attempts, failure reason.
- **Outcome** — bot disposition and verifier disposition side by side, with the actor and timestamp for each.

### 26.2 Transcript tab

Full chronological transcript with speaker labels, timestamps, and node references. Features: in-transcript search with highlight and match count, copy all, copy turn, jump-to-timestamp synchronised with the recording player, redaction indicator for masked segments, and export to TXT/JSON/PDF via the export pipeline once the endpoint exists.

Long transcripts must remain smooth: virtualise beyond 200 turns.

### 26.3 Recording tab

Player: play/pause, seek, waveform or progress bar, current position, total duration, volume, playback speed (0.5× / 1× / 1.25× / 1.5× / 2×), skip ±10s, download.

Recording states render as informative panels, never as a broken player: `pending`, `waiting_for_source`, `fetching`, `validating`, `storing`, `ready`, `failed`, `purged`.

**Security (unchanged from v1.0, still mandatory):** playback uses a short-lived signed URL fetched from the backend at play time; the URL is refreshed on expiry; permanent object-storage URLs are never embedded, logged, or persisted; downloads go through an authenticated backend endpoint and are audit-logged.

### 26.4 Script path tab *(new)*

Shows the exact node sequence the call traversed against the version that ran, with the answer captured at each node and the transition taken. This is how QA proves script adherence and how a script author debugs drop-off.

### 26.5 Transfer tab *(new)*

Timeline of the transfer attempt(s): initiated, ringing which verifier, bridged or failed, fallback action, resulting callback. Actions to retry or create a callback appear here for permitted roles.

### 26.6 Timeline tab

Millisecond-level event stream across categories `CALL · VAD · ASR · SCRIPT · RULES · LLM · TTS · INTERRUPTION · TRANSFER · RECORDING · SYSTEM`, filterable by category, rendered from backend-supplied events only.

### 26.7 Performance tab

Per-call latency: VAD speech-start, VAD endpoint, ASR first partial, ASR final, rule evaluation, LLM first token (when fallback used), TTS first audio, speech-end → first response audio, barge-in stop. Presented as labelled cards plus a per-turn latency chart. Kept out of the business dashboard.

### 26.8 QA tab

If reviewed: score, scorecard used, reviewer, tags, compliance flags, comments, dispute state. If not reviewed: an action to send the call to the QA queue (permitted roles only).

### 26.9 Technical tab

Connection id, call UUID, Asterisk channel, gateway node, STT/TTS/LLM provider and model, rule set id and version, recording pipeline status, backend version. Admin and IT/Ops only. Never exposes credentials, tokens, internal URLs, or storage paths.

## 26A. Recordings Library

**Route:** `/recordings`. Table across all calls with recording-centric filters: date, campaign, verifier, status, duration, size, consent captured, QA status. Inline mini-player for quick listening, link through to full call detail, bulk download request (queued server-side, never a browser zip), and a clear indicator for recordings past retention.

## 27. QA Module *(new in v2 — PRD FR-10, §8)*

PRD requires a sampled daily review during pilot. That requires a queue, a scorecard, and a result set.

### 27.1 Review queue — `/qa`

Table: call reference, date, campaign, script version, duration, disposition, transfer outcome, assigned reviewer, review status, priority flag.

Sampling controls (QA Manager): generate a review set by campaign, date range, sample size or percentage, and bias (e.g. prioritise disqualified, failed transfers, complaint-tagged, or short calls). The backend performs sampling; the UI requests it.

Assignment: assign to reviewer, bulk assign, reassign, unassign.

### 27.2 Review workspace — `/qa/review/[callId]`

```text
┌──────────────────────────────┬─────────────────────────────┐
│ RECORDING + TRANSCRIPT       │  SCORECARD                  │
│  synchronised player;        │   Greeting delivered   ✓/✗  │
│  click a transcript turn to  │   Consent captured     ✓/✗  │
│  seek; keyboard shortcuts    │   Script adherence     1–5  │
│  (space, ←/→, 1–5)           │   No misleading claim  ✓/✗ ⚠│
│                              │   Data accuracy        1–5  │
│  Script path shown alongside │   Transfer handling    1–5  │
│  so deviations are visible   │  ─────────────────────────  │
│                              │   Tags      [ + ]           │
│                              │   Compliance flags [ + ]    │
│                              │   Comments  [ ... ]         │
│                              │   Score: 86%   [ Submit ]   │
└──────────────────────────────┴─────────────────────────────┘
```

Criteria marked `autoFail` (for example a misleading claim or missing consent) force the total to zero and raise a compliance flag regardless of other scores. Drafts are saved automatically so a reviewer can leave and return.

### 27.3 Scorecards — `/qa/scorecards`

Create and version scorecard templates: criteria, weights, type, auto-fail flag, applicable campaigns. Editing a scorecard creates a new version; historical reviews keep the version they were scored on.

### 27.4 Results and calibration

`/qa/results` — score trends over time, by campaign, by script version, by reviewer; tag frequency; compliance flag frequency; auto-fail rate; open disputes.

`/qa/calibration` — a set of calls scored by multiple reviewers with variance highlighted, used to align reviewer standards.

### 27.5 Acceptance

- QA score and status appear on the call record and in call history filters.
- Auto-fail criteria produce a visible compliance flag that surfaces in the compliance report.
- No QA action can alter the original call data; reviews are a separate record.

## 28. Analytics

Five reports, mapped one-to-one to PRD §10, plus the engineering view.

### 28.1 `/analytics` — business overview

Date range, campaign and source filters applied across all panels. Funnel: leads → dialled → answered → consented → qualified → transferred → verified accepted, with conversion percentage at each step.

### 28.2 `/analytics/campaigns` — Daily Medicare Campaign Summary

Total calls, answered calls, contact rate, qualified leads, transfers, verifier accepted, disqualified, by day and by campaign. Table plus trend chart, exportable.

### 28.3 `/analytics/scripts` — Script Performance

Per script **version**: qualification rate, transfer rate, fallback count, caller drop-off point, average duration, complaint count. Includes a node-level drop-off funnel showing where callers hang up, and a version-vs-version comparison view. This is the analytic that justifies the whole script-versioning requirement.

### 28.4 `/analytics/sources` — Lead Source Quality

Per source and batch: qualification rate, duplicate rate, bad-number rate, contact rate, callback rate, transfer-to-accepted ratio, cost per qualified lead if the backend supplies cost.

### 28.5 `/analytics/bot` — Bot Performance

Script completion rate, fallback rate, silence/no-response count, average call duration, transfer success rate, barge-in frequency, average turns per call.

### 28.6 `/analytics/compliance` — Compliance Review

Consent captured rate, opt-out requests, complaint tags, script deviation count, auto-fail count, QA score distribution, calls dialled outside permitted hours (should be zero; any non-zero value renders as a critical alert).

### 28.7 `/analytics/performance` — AI latency

VAD, STT, rule evaluation, LLM, TTS, end-to-end response, barge-in stop. P50 / P95 / P99 selector. Filters: date, provider, model, campaign, node. Used to compare providers and GPU configurations. Restricted to Master Admin and IT/Ops.

### 28.8 Exports — `/analytics/exports`

All exports are server-generated jobs: request → queued → ready → download. History shows requester, report, filters, format, row count, timestamp. Exports are permission-gated and audit-logged per PRD §8. The browser never assembles a CSV from paginated fetches.

## 29. System Health, Alerts and Integrations

### 29.1 `/system` — service health

Cards for Asterisk, VICIdial, AI Gateway, STT, TTS, LLM, Script Engine, Rule Engine, Redis, PostgreSQL, Queue, Recording Worker, Object Storage, CRM connector. Each card: status, last check, latency, version, active requests, message when degraded. Driven by `system.health_changed` events with REST fallback polling.

Services not present in the deployed MVP must be hidden by configuration rather than rendered as `unknown` forever.

### 29.2 `/system/alerts`

Active and historical alerts with severity, source, message, raised at, acknowledge action, resolution. Critical alerts also surface as a shell banner. PRD §11 requires clear incident alerts; PRD §13 requires transfer-failure alerting.

### 29.3 `/system/integrations` *(new — PRD FR-13, §11)*

Per integration (CRM, dialer, webhook endpoints, lead vendor API): enabled state, endpoint (masked), auth status, last successful sync, failure count, test-connection action. A failure queue lists failed pushes with payload summary, error, attempt count, and a retry action. Credentials are never displayed in plaintext and are never returned to the browser.

## 30. Settings

| Page | Contents |
|---|---|
| `/settings/general` | Display name, default timezone, date format, default page size, default dashboard range |
| `/settings/telephony` | Asterisk/VICIdial/AudioSocket connection status, default call timeout, AMD defaults. Status only; credentials backend-side. |
| `/settings/stt` | Active provider, model, language, status. Options populated from backend capability list. |
| `/settings/tts` | Provider, model, voice, speed, default voice, preview (only once a safe backend preview endpoint exists) |
| `/settings/llm` | Provider, model, max tokens, temperature, fallback enable. Must not offer any option that makes the LLM authoritative for qualification. |
| `/settings/qualification` | Eligibility **rule sets** with versions: required fields, age rules, state rules, Part A/B requirements, campaign overrides. Read/author here, evaluated by backend. Each rule set version is bindable to a script version. |
| `/settings/recordings` | Recording enabled, retention days, download permitted roles, playback permitted roles, purge policy |
| `/settings/compliance` | Consent language versions, default calling hours, DNC enforcement, complaint tag list, opt-out keywords |
| `/settings/security` | Session timeout, password policy display, MFA status, IP allowlist if supported |
| `/settings/users` | User list, invite, edit role, enable/disable, reset password, last login |
| `/settings/roles` | Role definitions and permission matrix (read-only unless custom roles are supported) |

All settings writes require confirmation, show the previous value, and are audit-logged.

## 31. Audit Log

**Route:** `/audit`. Columns: timestamp, actor, role, action, resource type, resource id, result, IP, metadata summary.

Must capture at minimum: login/logout, failed login, script created/edited/submitted/approved/rejected/activated, campaign started/paused/stopped, campaign config changed, lead import committed, lead edited, suppression added/removed, disposition changed, recording played, recording downloaded, export requested, user created/role changed/disabled, settings changed, integration credentials updated.

Filters: date range, actor, action type, resource type, result. Exportable. Metadata never contains secrets.

---

# PART V — END-TO-END FRONTEND WORKFLOW

This part describes how the modules connect in daily use. Each journey is a navigation contract: the developer must ensure every arrow below is a real, working link or action in the application.

## 32. Journey 1 — Campaign Manager launches a campaign

```text
/login
  → /dashboard                      sees "No active script" warning in Attention panel
  → /leads/import                   Step 1 upload CSV
      Step 2 map columns → Step 3 validate (12 duplicates, 4 DNC matches skipped)
      Step 4 assign to campaign → Step 5 commit (progress via WebSocket)
  → /leads?campaign=medicare-q4     confirms 3,842 leads in "new" status
  → /scripts/new                    creates "Medicare Q4 v1" draft
  → /scripts/{id}/edit              authors greeting → consent → name → age
                                    → Part A → Part B → ZIP → transfer → closing
      validation panel clears       no orphan nodes, consent precedes capture
  → /scripts/{id}/preview           simulates a qualified path and a disqualified path
  → submit for approval             status → pending_approval
  → (Master Admin) /scripts/approvals → reviews diff → approves
  → /campaigns/{id}/script          activates v1 for Medicare Q4 (typed confirmation)
  → /campaigns/{id}/dialing         sets timezone America/Chicago, 09:00–20:00 Mon–Sat,
                                    max 5 attempts, no_answer retry 240m, AMD on
  → /campaigns/{id}/transfer        binds verifier group, 25s ring, fallback = callback
  → /campaigns/{id}                 "Start campaign" enabled; confirms; status → active
  → /calls/live                     watches first calls connect
```

## 33. Journey 2 — A single call, end to end, as seen in the UI

```text
BACKEND EVENT                         FRONTEND SURFACE
call.started                       →  new card appears on /calls/live
call.answered                      →  card state → greeting
call.state_changed (listening)     →  live indicator updates
transcript.partial / .final        →  live transcript streams in
consent.captured                   →  consent chip turns ✓ with timestamp
call.node_changed (ask_age)        →  node label updates, "Age" field shows pending
qualification.field_updated        →  Age 67 appears in the card
qualification.evaluated            →  QUALIFIED badge, card moves to transferring
transfer.initiated                 →  row appears on /transfers
verifier.transfer_offered          →  banner appears in that verifier's shell
transfer.bridged                   →  verifier lands on /verifier active screen
                                      with summary + transcript + qualification
verifier disposition submitted     →  call closes, disposition written
call.completed                     →  card leaves /calls/live, row lands in /calls
recording.status_changed (ready)   →  recording tab becomes playable
(QA sampling)                      →  call appears in /qa queue
QA review submitted                →  QA score shows on call detail and in analytics
```

## 34. Journey 3 — Verifier's shift

```text
/login → default route /verifier
  → sets availability to Available (shell toggle)
  → idle state: "Waiting for transfers · 4 verifiers available"
  → banner: INCOMING TRANSFER, 25s countdown → Accept
  → /verifier active screen
      reads caller summary, qualification, and bot transcript
      speaks to caller, corrects ZIP (records original + correction)
      selects disposition verified_accepted, adds notes → Submit & Close
  → returns to idle; call appears in /verifier/history
  → end of shift: sets availability to Away (blocked if a transfer is in flight)
```

## 35. Journey 4 — QA Manager's daily review

```text
/login → /qa
  → generates sample: Medicare Q4, yesterday, 5% sample, bias = disqualified + failed transfers
  → assigns 20 calls across 3 reviewers
  → opens /qa/review/{callId}
      plays recording synced to transcript, compares against script path
      finds a missing consent → auto-fail criterion triggered
      tags: consent_missing, script_deviation → submits
  → /analytics/compliance                shows the new auto-fail in today's counts
  → /scripts/{id}/versions/7/diff?against=8  checks whether v8 fixed the consent node
  → raises the finding with the Campaign Manager
```

## 36. Journey 5 — Transfer failure recovery

```text
system.alert_raised (transfer_failure_rate)
  → shell alert badge increments
  → /system/alerts                acknowledges
  → /transfers/failed             12 qualified callers not transferred
      cause: no verifier available between 18:00–19:00
  → per row: Create callback  (bulk action for all 12)
  → /campaigns/{id}/transfer      raises verifier group size / changes fallback to queue
  → /analytics/campaigns          confirms transfer rate recovers next day
```

## 37. Journey 6 — Supervisor investigating one lead

```text
/leads?search=214-555-8219
  → /leads/{leadId}               3 attempts, last one qualified
  → Call history tab → /calls/{callId}
  → Overview: qualification + consent evidence
  → "Play from consent" seeks recording to 00:12
  → Script Path tab: confirms the caller heard v7 wording
  → Transfer tab: bridged to verifier Ayesha at 00:58
  → QA tab: scored 92%
```

## 38. Cross-module linking contract

Every one of these links must exist and work:

| From | To |
|---|---|
| Any call reference anywhere | `/calls/[callId]` |
| Call detail → script version chip | `/scripts/[id]/versions/[v]` |
| Call detail → lead | `/leads/[leadId]` |
| Call detail → campaign | `/campaigns/[campaignId]` |
| Call detail → verifier | verifier profile / filtered history |
| Live call card → detail | `/calls/[callId]` |
| Transfer row → call | `/calls/[callId]` |
| QA review → call | `/calls/[callId]` |
| Lead detail → each call attempt | `/calls/[callId]` |
| Analytics data point | filtered `/calls` view that produced it |
| Dashboard KPI | the filtered list behind it |
| Audit entry | the resource it acted on |

A number on a dashboard that cannot be drilled into is a defect.

---

# PART VI — CROSS-CUTTING ENGINEERING

## 39. Folder Structure

```text
apps/web/
├── src/
│   ├── app/
│   │   ├── (auth)/login/page.tsx
│   │   ├── (dashboard)/
│   │   │   ├── layout.tsx                auth guard + shell + socket provider
│   │   │   ├── dashboard/
│   │   │   ├── leads/{,import,[leadId],suppression}/
│   │   │   ├── campaigns/[campaignId]/{dialing,routing,script,transfer,performance}/
│   │   │   ├── scripts/{,new,approvals,[scriptId]/{edit,preview,versions/[version]}}/
│   │   │   ├── calls/{,live,[callId]}/
│   │   │   ├── transfers/{,failed}/
│   │   │   ├── verifier/{,history}/
│   │   │   ├── recordings/
│   │   │   ├── qa/{,review/[callId],scorecards,results,calibration}/
│   │   │   ├── analytics/{,campaigns,scripts,sources,bot,compliance,performance,exports}/
│   │   │   ├── system/{,alerts,integrations}/
│   │   │   ├── settings/…
│   │   │   └── audit/
│   │   └── layout.tsx
│   │
│   ├── components/{ui,data,status,domain,feedback,layout}/
│   │
│   ├── features/                         co-located feature logic
│   │   ├── leads/{api.ts,hooks.ts,schemas.ts,components/}
│   │   ├── scripts/
│   │   ├── calls/
│   │   ├── transfers/
│   │   ├── verifier/
│   │   ├── qa/
│   │   └── analytics/
│   │
│   ├── lib/
│   │   ├── api/{client.ts,endpoints.ts,errors.ts}
│   │   ├── auth/{guard.ts,session.ts,permissions.ts}
│   │   ├── websocket/{client.ts,channels.ts,reducer.ts,provider.tsx}
│   │   ├── format/{date.ts,phone.ts,duration.ts,number.ts}
│   │   └── utils/
│   │
│   ├── config/{routes.ts,navigation.ts,permissions.ts,status.ts,api.ts,features.ts}
│   ├── store/                            Zustand slices (ui, socket, filters)
│   ├── types/
│   └── mocks/{handlers/,fixtures/,server.ts}
│
├── .env.example
└── package.json
```

**Rule:** pages compose; they do not fetch, transform, or decide. All data access lives in `features/*/api.ts` and is consumed through `features/*/hooks.ts`.

## 40. State Management

| Concern | Mechanism |
|---|---|
| Server data | TanStack Query. Query keys namespaced by feature and filters. |
| Realtime deltas | WebSocket reducer writes into the Query cache via `setQueryData`; components never subscribe to the socket directly. |
| UI state (sidebar, modals, column visibility) | Zustand, persisted where appropriate |
| Filters and pagination | URL search params, parsed and validated with Zod |
| Forms | React Hook Form + Zod resolver |
| Auth/session | React context over an auth store, hydrated from `/auth/me` |

Explicitly forbidden: ad-hoc `fetch` inside components, a global "app state" god-store, duplicating server data into Zustand, and more than one WebSocket connection per session.

## 41. Realtime Architecture

```text
        ┌──────────────────────┐
        │  WebSocket client    │  single connection, auth on open,
        │  (lib/websocket)     │  backoff reconnect, heartbeat
        └──────────┬───────────┘
                   ↓
        ┌──────────────────────┐
        │  Channel subscriber  │  subscribe/unsubscribe by route
        └──────────┬───────────┘
                   ↓
        ┌──────────────────────┐
        │  Event reducer       │  dedupe by seq, apply to Query cache,
        │                      │  batch into animation frames
        └──────────┬───────────┘
                   ↓
        ┌──────────────────────┐
        │  Feature hooks       │  useLiveCalls, useCallStream(id),
        │                      │  useVerifierQueue, useSystemEvents
        └──────────┬───────────┘
                   ↓
             Components
```

Reconnect protocol: on reconnect, resubscribe to active channels, then refetch the affected queries once to close the gap. Never replay missed events from a client-side buffer.

Degraded mode: if the socket cannot connect after three attempts, fall back to polling (live calls 5s, dashboard 30s, health 30s) and display `Live: Disconnected — using polling`.

## 42. Permissions in the UI

```typescript
// config/permissions.ts — keys only; the backend owns enforcement
export const PERMISSIONS = {
  SCRIPT_EDIT: "script.edit",
  SCRIPT_APPROVE: "script.approve",
  SCRIPT_ACTIVATE: "script.activate",
  CAMPAIGN_CONTROL: "campaign.control",
  LEAD_IMPORT: "lead.import",
  SUPPRESSION_REMOVE: "suppression.remove",
  RECORDING_DOWNLOAD: "recording.download",
  CALLER_NUMBER_FULL: "caller.number.full",
  TRANSFER_RETRY: "transfer.retry",
  QA_REVIEW: "qa.review",
  EXPORT_CREATE: "export.create",
  USER_MANAGE: "user.manage",
} as const;
```

Usage: `usePermission(PERMISSIONS.SCRIPT_APPROVE)` gates rendering. A user who reaches a forbidden route via URL sees the `PermissionDenied` panel, not a redirect loop. A `403` from any API call renders the same panel in place.

## 43. Security Rules

The frontend must never contain: database, Redis, queue, Asterisk or VICIdial credentials; cloud storage keys; STT/TTS/LLM provider secrets; internal service tokens; private URLs; SSH keys. Only `NEXT_PUBLIC_API_BASE_URL` and `NEXT_PUBLIC_WS_URL` belong in browser-visible config.

Additional rules:

- Recording and export URLs are short-lived and fetched at use time; never stored, never logged, never put in `localStorage`.
- Caller numbers, names, DOB and ZIP are masked unless the user holds the relevant permission; masking uses one shared formatter, never per-component logic.
- No personal data in query strings that are logged or shared — use POST bodies for search payloads containing PII where the backend supports it.
- No sensitive payload logging in production builds; console logging of call data is stripped by build configuration.
- Clear the entire query cache and socket state on logout and on session expiry.
- Content Security Policy and `X-Frame-Options` set at the Next.js level.
- Any destructive action uses `DestructiveConfirmation` with typed confirmation.

## 44. Performance Budgets

| Metric | Budget |
|---|---|
| First contentful paint (dashboard, warm) | < 1.5s |
| Route transition | < 300ms perceived, skeleton within 100ms |
| Table render, 50 rows | < 100ms |
| Live grid update under 50 concurrent calls | no dropped frames; batched at 60fps |
| Transcript render, 1,000 turns | virtualised, < 16ms per scroll frame |
| Bundle, initial route | < 300KB gzipped |

Techniques: route-level code splitting, dynamic import for charts and the script editor canvas, virtualisation for transcripts and long tables, memoised table rows, and `select` in Query to avoid re-renders on unrelated field changes.

## 45. Loading, Empty, Error and Permission States

Every data-backed surface implements all four. No exceptions, no blank screens, no spinners over already-rendered content.

| State | Pattern |
|---|---|
| Loading | Shape-matched skeletons (KPI, table, chart, transcript, player, card grid) |
| Empty (no data yet) | Icon, one-line explanation, primary action where one exists ("Import leads", "Create script") |
| Empty (filters exclude everything) | Distinct message with "Clear filters" |
| Error | Short human message, Retry, and a support reference in non-production |
| Permission | `PermissionDenied` panel with the role required |
| Offline / socket down | Shell-level banner, not per-component noise |

## 46. Formatting Rules

- All timestamps arrive UTC and are rendered in the user's configured timezone, with campaign-local time shown wherever calling hours are relevant (dialing config, call time in history for a US campaign viewed from Pakistan). Show the timezone abbreviation whenever ambiguity is possible.
- Durations render `mm:ss` under an hour, `h:mm:ss` above.
- Latency renders in ms, monospace, with a unit label.
- Phone numbers use one formatter with `full` and `masked` modes; masked form is `(214) ***-8219`.
- Percentages carry one decimal place; counts use thousands separators.
- Never manipulate backend timestamps by string slicing.

## 47. Accessibility

Semantic HTML, full keyboard operability (including the script editor and the QA scorecard), visible focus rings, labelled form controls with associated error text, accessible dialogs with focus trapping and restoration, ARIA live regions for the incoming-transfer banner and connection status, WCAG AA contrast, and no meaning conveyed by colour alone. Tables use proper headers and scope so screen readers remain usable.

## 48. Responsive Targets

| Width | Behaviour |
|---|---|
| ≥1920px | Full layout, wider tables, side-by-side panels |
| 1440px | Primary design target |
| 1366px | Sidebar collapses to icon rail; tables scroll horizontally |
| 1024px (tablet) | Sidebar becomes drawer; call detail tabs stack; QA workspace stacks vertically |
| <768px | Read-only essentials: dashboard, call list, call detail, verifier banner. The script editor and QA workspace are explicitly desktop-only and display a message. |

The Verifier incoming-transfer banner must work on tablet, since verifiers may float between stations.

## 49. Mock Layer

Use MSW (Mock Service Worker) rather than imported fixture objects. Reasons: the network boundary is exercised from day one, loading and error states are testable, and the switch to real APIs is a base-URL change rather than a refactor.

Requirements: every endpoint in §14 has a handler; handlers respect pagination, filtering and sorting parameters; fixtures include realistic volume (2,000+ calls, 5,000+ leads, 6 scripts with multiple versions, 3 campaigns, 40 QA reviews); error and empty responses are triggerable via a dev toggle; a mock WebSocket server emits a scripted live-call sequence including a transfer failure.

**Rule:** no component may depend on a field the real contract does not define. Any mock-only field is a defect.

## 50. Quality Standards

- TypeScript `strict`; `any` is a review blocker; no `@ts-ignore` without a linked issue.
- No component over ~250 lines; no file over ~400.
- Status-to-style mapping lives once in `config/status.ts`.
- Routes, endpoints, permissions and enums are centralised; no string literals for these in components.
- ESLint + Prettier enforced in CI; production build must pass with zero type errors and zero lint errors.
- Conventional commits, PRs scoped to one module, screenshots required for UI changes.

## 51. Testing Strategy

| Level | Tool | Scope |
|---|---|---|
| Unit | Vitest | Formatters (phone, duration, timezone), permission resolver, WebSocket reducer (dedupe, ordering, gap handling), filter serialisation, scorecard scoring |
| Component | Testing Library | Status badges, DataTable states, RecordingPlayer states, ScorecardForm validation, ImportStepper transitions, TransferBanner countdown |
| Integration | Testing Library + MSW | Login → dashboard; filter → table → detail; script draft → submit → approve → activate; import wizard end to end; transfer offered → accepted → disposition |
| E2E | Playwright | The six journeys in Part V, run against mocks in CI and against staging before release |

Minimum bar for acceptance: all Part V journeys pass as E2E tests against the mock server.

---

# PART VII — DELIVERY PLAN

## 52. Priority Re-baseline

v1.0 classified a recording player with five playback speeds as P0 while omitting script management, live transfer, the verifier workspace, QA and lead import entirely. The corrected classification below is anchored to PRD priority levels.

### P0 — Required for pilot (PRD "Must have")

```text
Application shell, routing, auth guard, permission framework
Login and session handling
Dashboard with PRD KPI set
Leads list + import wizard + suppression                    FR-01
Campaign list + dialing/routing/transfer configuration      FR-02, FR-03
Script Management: editor, versioning, approval, activation FR-05
Call history with full filter set
Call detail: overview, qualification, consent evidence,
             transcript, recording, script path
Live calls monitoring + live transcript                     FR-04
Transfer monitor + failed transfer recovery                 FR-08
Verifier workspace                                          FR-08
Disposition capture
Recording playback with signed URLs                         FR-09
Role permission enforcement in UI                           FR-12
Loading / empty / error / permission states
```

### P1 — Required for production launch

```text
QA module: queue, review workspace, scorecards, results     FR-10
Analytics: campaign summary, script performance,
           lead source quality, bot performance             FR-11
Compliance report and consent evidence reporting
Export pipeline
System health + alerts
Integrations configuration and failure recovery             FR-13
Audit log
Call timeline tab
User management
```

### P2 — Post-launch

```text
AI performance analytics (P50/P95/P99), provider cards
QA calibration sessions
Saved filter presets, column customisation
Global ⌘K search
Dark mode
Advanced script simulator (replay real calls against drafts)
Scheduled exports
Custom roles
```

## 53. Development Phases

Each phase has a hard exit criterion. A phase is not complete until its criterion is demonstrably met against the mock server.

---

### Phase 0 — Contract Freeze *(prerequisite, no UI work)*

**Work:** Agree with the backend lead on every enum in §11, the response envelope in §13, the endpoint list in §14, the WebSocket catalogue in §15, and the error taxonomy in §16. Produce a signed-off `contracts.md` or OpenAPI document.

**Why this is a phase:** v1.0 deferred type alignment to integration time. That guarantees a rewrite. Nothing else starts until this is frozen.

**Exit:** Backend and frontend both sign the contract document. Enums are published as a shared TypeScript file.

---

### Phase 1 — Foundation

**Work:** Next.js App Router scaffold, Tailwind + shadcn/ui setup, design tokens, application shell (sidebar, top bar, breadcrumbs, toast, modal host), route skeletons for every route in §6, auth guard, permission framework, API client with error normalisation, TanStack Query setup, Zustand stores, MSW mock server with all handlers, TypeScript types from the frozen contract, shared component primitives, loading/empty/error/permission components.

**Exit:** Every route in §6 renders with correct shell, correct nav visibility per role, and a skeleton state. Production build passes with zero type errors. Switching a single env var points the app at a real backend.

---

### Phase 2 — Leads and Campaigns

**Work:** Lead list with full filters and bulk actions, lead detail, import wizard (all five steps), suppression module, campaign list, campaign create, campaign overview, dialing configuration with calling-window preview, routing configuration, transfer configuration, campaign start/pause/stop with confirmations.

**Exit:** A user can import a CSV, see validation results, assign leads to a campaign, configure dialing rules including US calling hours from a Pakistan-local browser, and attempt to start a campaign — with the UI correctly blocking on "no active script".

---

### Phase 3 — Script Management

**Work:** Script library, script creation, the three-pane editor with all node types, transition authoring, structural validation panel, autosave, version history, diff viewer, approval queue, approve/reject flow, activation dialog with campaign binding, preview simulator wired to the simulate endpoint.

**Exit:** The full lifecycle `draft → submit → approve → activate` works end to end against mocks. An approved version cannot be edited by any interaction path. Version history shows every transition with actor and timestamp. A campaign displays the exact active version.

---

### Phase 4 — Calls, Transcripts and Recordings

**Work:** Call history table with the full filter and column set, saved views via URL state, call detail with Overview, Transcript, Recording, Script Path, Timeline and Technical tabs, transcript viewer with search and timestamp sync, recording player with all states and signed-URL handling, recordings library.

**Exit:** A supervisor can filter to a specific disposition, open a call, read the transcript, play from the consent marker, and see which script version ran. Transcript of 1,000 turns scrolls without jank.

---

### Phase 5 — Realtime, Transfer and Verifier

**Work:** WebSocket client, channel subscription, event reducer with dedupe and gap reconciliation, reconnect and polling fallback, live calls page, live transcript, transfer monitor, failed transfer queue with retry and callback actions, verifier availability control, incoming transfer banner (shell-level), verifier active screen, disposition submission, verifier history.

**Exit:** The mock socket script drives a complete call from start through a successful transfer and through a failed transfer with fallback. Killing the socket mid-call degrades to polling and recovers without a page refresh or duplicated rows.

---

### Phase 6 — QA and Analytics

**Work:** QA queue with sampling request and assignment, review workspace with synced player and transcript, scorecard form with auto-fail behaviour, tags and compliance flags, scorecard templates, QA results, all five PRD analytics reports, export request and download flow.

**Exit:** A QA Manager can sample, assign, review and score a call, and the auto-fail appears in the compliance report. Every analytics figure drills through to the filtered call list behind it.

---

### Phase 7 — Operations, Settings and Backend Integration

**Work:** System health, alerts, integrations configuration and failure queue, all settings pages, eligibility rule sets, user management, roles view, audit log. Then: point the app at the real API, replace mock auth with real auth, wire real WebSocket authentication, reconcile every contract divergence, verify permission behaviour against real role tokens.

**Exit:** The application runs entirely against the staging backend with no mock handlers active. Every contract divergence is either fixed in backend or formally accepted and documented.

---

### Phase 8 — Hardening and Release

**Work:** Responsive pass across all breakpoints, accessibility audit and fixes, security review against §43, performance profiling against §44 budgets, long-table and long-transcript stress tests, WebSocket chaos testing (drops, duplicates, out-of-order, long outage), session expiry testing, E2E suite for all six journeys, production build optimisation, README and `.env.example`, handover documentation.

**Exit:** All items in §56 checked. E2E suite green. Sign-off.

---

## 54. Roadmap

Estimates assume one senior frontend developer working full-time, with a second developer able to parallelise Phases 2–4 and 5–6.

| Phase | Scope | Solo | With 2 devs |
|---|---|:--:|:--:|
| 1 | Foundation 
| 2 | Leads and campaigns
| 3 | Script management 
| 4 | Calls, transcripts, recordings 
| 5 | Realtime, transfer, verifier 
| 6 | QA and analytics 
| 7 | Operations, settings, integration 
| 8 | Hardening and release

### Critical path

```text
Phase 0 contract freeze
    → Phase 1 foundation
        → Phase 3 script management  ← longest and highest-risk module
            → Phase 5 verifier + transfer
                → Phase 7 integration
                    → Phase 8 release
```

Phases 2, 4 and 6 can be resequenced. Phase 3 cannot start late without pushing the whole pilot, because a campaign cannot run without an active script.

## 55. Definition of Done (per page)

A page ships only when all of the following are true:

```text
□ Loading state implemented with shape-matched skeleton
□ Empty state implemented (no data, and filtered-to-nothing variants)
□ Error state with retry
□ Permission-denied state
□ All data typed against the frozen contract; no any
□ All API access through the feature API layer
□ No business logic or rule evaluation in the component
□ No hardcoded URLs, enums, or status styles
□ Filters/pagination reflected in the URL where applicable
□ Responsive at 1440, 1366, and 1024
□ Keyboard operable; focus visible; controls labelled
□ No sensitive data logged or persisted
□ Every link in §38 that originates on this page works
□ Integration test covering the primary interaction
```

## 56. Acceptance Checklist

**Foundation**
```text
□ Builds and type-checks clean   □ All routes render   □ Role-based nav correct
□ Auth guard enforced            □ 401 handled once, no loop
□ Permission-denied renders in place of forbidden content
```

**Leads**
```text
□ List with server-side filter/sort/paginate   □ Import wizard all 5 steps
□ Validation report downloadable               □ Duplicate + DNC handling shown
□ Lead detail with call history                □ Suppression add/import/remove
□ Bulk actions confirmed and audited
```

**Campaigns**
```text
□ Create and edit   □ Dialing hours with timezone preview   □ Retry policy per outcome
□ DID and caller-ID configuration   □ Verifier group and fallback   □ Start/pause/stop
□ Misconfiguration warnings surfaced
```

**Scripts**
```text
□ Editor with all node types        □ Transition authoring
□ Structural validation blocks submit  □ Autosave
□ Version history complete          □ Diff viewer
□ Approval queue with reject reason  □ Activation with typed confirmation
□ Approved versions immutable in UI  □ Preview simulator uses backend evaluation
```

**Calls**
```text
□ Full filter set    □ Saved/shareable URL state   □ Call detail all tabs
□ Script path tab    □ Consent evidence with jump-to-audio
□ Disposition displayed distinctly from qualification
```

**Live, Transfer, Verifier**
```text
□ Live grid updates without refresh     □ States come only from backend events
□ Reconnect + polling fallback          □ No duplicate rows after reconnect
□ Transfer monitor + failed queue       □ Retry and callback actions
□ Verifier availability toggle          □ Shell-level incoming banner
□ Accept/decline server-confirmed       □ Disposition required to close
```

**Recordings**
```text
□ All 8 recording states   □ Signed URL fetched at play time and refreshed
□ No permanent URL in code, storage, or logs   □ Download audit-logged
□ Playback speeds and seek
```

**QA**
```text
□ Sampling request   □ Assignment   □ Synced player/transcript
□ Scorecard with auto-fail   □ Tags and compliance flags   □ Results view
```

**Analytics**
```text
□ All 5 PRD reports   □ Date/campaign/source filters   □ Script-version comparison
□ Drill-through from every figure   □ Server-side exports with history
```

**Operations**
```text
□ Health cards   □ Alerts with acknowledge   □ Integration status and retry queue
□ All settings pages   □ Rule sets with versions   □ User management   □ Audit log
```

**Security**
```text
□ No secrets in the bundle or NEXT_PUBLIC_*   □ No permanent media URLs
□ PII masked by permission via a single formatter   □ No PII in logged query strings
□ Cache and socket cleared on logout   □ Destructive actions confirmed
```

**Quality**
```text
□ No raw fetch in components   □ No duplicated status maps   □ No business logic in UI
□ Performance budgets met   □ WCAG AA contrast   □ E2E journeys green
```

## 57. Deliverables

```text
1.  Complete Next.js source, one repository, documented branch strategy
2.  Frozen contract document (or OpenAPI) agreed with backend
3.  Shared TypeScript types package or directory
4.  Application shell and design token system
5.  Reusable component library (ui, data, status, domain, feedback)
6.  All P0 modules, fully stated (loading/empty/error/permission)
7.  MSW mock layer with realistic fixtures and a scripted live-call scenario
8.  REST integration layer with normalised error handling
9.  WebSocket layer with reconnect, dedupe and polling fallback
10. Permission framework and role matrix implementation
11. Unit, component and integration tests per §51
12. Playwright E2E covering the six Part V journeys
13. README: setup, run, mock mode, environment, build, deploy
14. .env.example containing only safe public configuration
15. Handover document: architecture decisions, known gaps, P2 backlog
```

## 58. Non-Negotiable Architecture Rules

```text
R1   The frontend is a control plane. It never sits in the media path.
R2   The frontend never computes qualification, eligibility, or transfer decisions.
R3   Script branching is authored in the UI and evaluated only by the backend.
R4   Approved script versions are immutable; history is never overwritten.
R5   Every call record carries and displays the script version that ran.
R6   Recordings are reached only through short-lived, backend-issued URLs.
R7   No infrastructure credential or provider secret exists in frontend code or config.
R8   Realtime state comes from dashboard WebSocket events, never from a direct
     connection to Asterisk, VICIdial, or any model server.
R9   Permission enforcement is backend-authoritative; the UI only reflects it.
R10  API access, WebSocket handling, types, state and rendering stay separated.
R11  Suppression and calling-hour rules are enforced by the backend; the UI
     displays and configures them but never bypasses or re-implements them.
R12  Every displayed number must be traceable to a documented backend field.
```

## 59. Open Questions

These require answers from SmartBrains or the backend team before the phases they affect.

| # | Question | Blocks | Owner |
|---|---|---|---|
| 1 | Confirm the six PRD roles are final, and whether custom roles are needed | Phase 1 | SmartBrains |
| 2 | Warm transfer (bot introduces, verifier joins) or cold transfer (bot drops)? Affects the verifier screen and transfer states | Phase 5 | SmartBrains ops |
| 3 | Does a verifier need live listen-in or barge on an in-progress bot call? Not in PRD; common BPO expectation | Phase 5 | SmartBrains |
| 4 | Are eligibility rules versioned independently of scripts, or bound to a script version? | Phase 3 | Backend |
| 5 | Consent recording requirements: single-party or two-party states; is a separate consent audio segment stored? | Phase 4 | Compliance |
| 6 | Retention period for recordings and transcripts, and who may purge | Phase 7 | SmartBrains |
| 7 | Which CRM and dialer are integration targets, and is the push synchronous? | Phase 7 | SmartBrains IT |
| 8 | Does the pilot include inbound calls, or outbound only? Inbound DID routing UI can be deferred if outbound-only | Phase 2 | SmartBrains |
| 9 | Expected peak concurrent calls — determines live-grid virtualisation strategy | Phase 5 | Backend |
| 10 | Is Kafka in the MVP deployment? If not, remove it from health monitoring | Phase 7 | Backend |
| 11 | Is script authoring multilingual (English only for pilot)? | Phase 3 | SmartBrains |
| 12 | Export formats required: CSV only, or XLSX and PDF | Phase 6 | SmartBrains |

## 60. Appendix A — PRD Requirement Traceability

| PRD ID | Requirement | Priority | Frontend module | Spec section | Phase |
|---|---|---|---|---|---|
| FR-01 | Lead management | Must | Leads + Import | §19 | 2 |
| FR-02 | Outbound calling rules | Must | Campaign dialing config | §20.3 | 2 |
| FR-03 | Inbound handling / DID routing | Must | Campaign routing | §20.4 | 2 |
| FR-04 | AI voice script execution | Must | Live calls, script path | §22, §26.4 | 3, 5 |
| FR-05 | Dashboard script management | Must | Script Management | §21 | 3 |
| FR-06 | Consent capture | Must | Consent evidence, script consent node | §21.4, §26.1 | 3, 4 |
| FR-07 | Eligibility rules | Must | Rule sets settings, qualification panel | §30, §26.1 | 4, 7 |
| FR-08 | Live transfer | Must | Transfer module + Verifier workspace | §23, §24 | 5 |
| FR-09 | Call recording and metadata | Must | Recording tab, library | §26.3, §26A | 4 |
| FR-10 | QA review | Should | QA module | §27 | 6 |
| FR-11 | Dashboards | Must | Dashboard + Analytics | §18, §28 | 1, 6 |
| FR-12 | Role permissions | Must | Permission framework | §7, §42 | 1 |
| FR-13 | CRM integration | Should | Integrations | §29.3 | 7 |
| §7 | Script add/edit/version/approve/activate | Must | Script Management | §21 | 3 |
| §8 | Compliance controls | Must | Suppression, consent, compliance report, audit | §19.4, §28.6, §31 | 2, 6 |
| §10 | Five reports | Must | Analytics | §28.2–28.6 | 6 |
| §11 | Reliability / error recovery | Must | Alerts, integration failure queue, transfer recovery | §23.3, §29.2, §29.3 | 5, 7 |
| §13 | Transfer failure risk | Must | Failed transfer queue + alerting | §23.3 | 5 |

## 61. Appendix B — Gaps Closed Against v1.0

| Gap in v1.0 | Severity | Closed in |
|---|---|---|
| No script management of any kind | Critical — PRD flagship feature | §21 |
| No live transfer handling | Critical — core workflow step | §23 |
| No verifier role or workspace | Critical — a PRD role with no UI | §24 |
| No lead import or lead CRUD | Critical — FR-01 | §19 |
| No suppression / DNC | Critical — compliance exposure | §19.4 |
| No QA module | High — FR-10 | §27 |
| Role model did not match PRD | High — permissions built on wrong basis | §3, §42 |
| Call status enum missing AMD, voicemail, no-answer | High — contact rate uncomputable | §11.3 |
| Disposition not modelled separately from qualification | High | §11.3, §12 |
| Script version not attached to calls | High — audit requirement | §12, §26 |
| Dialing rules, calling hours, retries absent | High — FR-02 | §20.3 |
| Inbound DID routing absent | Medium — FR-03 | §20.4 |
| Three of five PRD reports missing | Medium | §28 |
| Exports deferred despite being in scope | Medium | §28.8 |
| CRM/webhook integration UI absent | Medium — FR-13 | §29.3 |
| Consent treated as a boolean, no evidence trail | Medium — compliance | §26.1 |
| No alerting surface | Medium | §29.2 |
| API contract was GET-only | High — symptom of missing features | §14 |
| Response envelope undefined | High — guaranteed integration rework | §13, Phase 0 |
| No state-management decision | Medium | §40 |
| Design direction unactionable | Medium — rework risk | §9 |
| Priorities inverted against PRD | High | §52 |

---

**End of specification.**

*This document supersedes TALKFLOW_FRONTEND_DEVELOPMENT_SPEC.md v1.0 in full. Where the two conflict, this document governs. Changes to the contract in Part III require agreement from both the frontend and backend leads and a version increment of this document.*
