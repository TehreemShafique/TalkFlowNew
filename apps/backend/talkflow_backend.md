# TalkFlow — Medicare AI Voice Bot
## Complete Backend Blueprint: Architecture, Ground Rules, and Roadmap to Production


---

# PART 0 — THE VERIFIED ENVIRONMENT

## 1. What Is Actually Running

### 1.1 Telephony

```text
Asterisk 18.26.4-vici    built 2026-08-22, x86_64 Linux
VICIdial 2.14
```

`-vici` denotes the VICIdial project's patched Asterisk build. VICIdial maintains its own packaging; the underlying Asterisk 18 branch is upstream end-of-life.

### 1.2 Application code

| Path | What it is | Language |
|---|---|---|
| `services/ai-gateway/` | Realtime conversational engine — AudioSocket server, Silero VAD, streaming ASR, deterministic qualification state machine, LLM fallback via vLLM, TTS with barge-in, speech normalization, recording coordinator. ~18,000 lines. | Python 3.11, FastAPI, asyncio |
| `services/recording-worker/` | Kafka consumer. SFTP pull from Asterisk, SHA-256 validation, storage to local or S3, writes `call_recordings`. | Python, aiokafka, asyncpg |
| `services/tts-worker/` | Chatterbox generative TTS behind HTTP. | Python |
| `apps/dashboard/` | Next.js 16.3.2, React 19.2.8, Tailwind 4. | JavaScript (JSX) |

### 1.3 Infrastructure already deployed

PostgreSQL 16, Redis 7, Kafka 3.7 (KRaft, three partitions), vLLM serving Qwen2.5-1.5B-Instruct-AWQ, plus the GPU-reserved gateway and recording worker. **The control plane introduces no new infrastructure.** It occupies what is already there.

### 1.4 The database today

One table: `call_recordings`. No calls, leads, campaigns, scripts, users, transcripts, transfers or audit. Qualification state lives in gateway process memory keyed by connection id and is lost on restart.

## 2. What VICIdial Already Provides

This section is the single most important correction in this document. **Before building anything, understand what exists.**

VICIdial 2.14 ships two HTTP APIs, both requiring a `vicidial_users` account with API access enabled:

```text
Non-Agent API   /vicidial/non_agent_api.php    system-level, no agent session
Agent API       /agc/api.php                   requires an active agent session
```

### 2.1 Capabilities the control plane must NOT rebuild

| Capability | VICIdial mechanism | Verified detail |
|---|---|---|
| **Outbound dialing and pacing** | Campaign `dial_method`, `dial_level`, hopper | `campaigns_list` returns `dial_method`, `dial_level`, `lead_order`, `dial_statuses`, `dial_timeout`, `dial_prefix`. Methods include `RATIO`, `ADAPT_*` including `ADAPT_PERCENTMAX` (added 251205). |
| **Lead queueing** | `vicidial_hopper` | `add_lead` with `add_to_hopper=Y`, `hopper_priority` (−99…99); `hopper_bulk_insert` for up to 1000 lead IDs at a time |
| **Local and state call-time enforcement** | List `local_call_time`, state call-time rules | `hopper_local_call_time_check=Y` validates local **and** state call time before hopper insertion. Returns `NOT ADDED TO HOPPER, OUTSIDE OF LOCAL TIME` with the lead's GMT offset and state. |
| **Time-zone derivation** | `tz_method` | `COUNTRY_AND_AREA_CODE` (default), `POSTAL_CODE`, `NANPA_PREFIX`, `OWNER_TIME_ZONE_CODE` |
| **DNC checking at load** | `dnc_check`, `campaign_dnc_check` | Values `Y`, `N`, or `AREACODE`. Campaign-level and system-internal lists. |
| **DNC list management** | `add_dnc_phone`, `delete_dnc_phone` | Takes `campaign_id` or the literal `SYSTEM_INTERNAL`. Deletion requires the "Delete From DNC Lists" user permission. |
| **Duplicate detection** | `duplicate_check` | `DUPLIST`, `DUPCAMP`, `DUPSYS`, plus alt-phone, title-alt-phone and name-phone variants, each combinable with a day window: `DUPSYS90DAY`, and 1/2/3/7/14/15/21/28/30/60/90/180/360 day options |
| **Number validation** | `usacan_prefix_check`, `usacan_areacode_check`, `nanpa_ac_prefix_check` | Fourth-digit validation, area-code validation with 10-digit length check, NANPA prefix validation if the data set is loaded |
| **Answering machine detection** | Campaign AMD settings | AMD is a VICIdial campaign feature using Asterisk's AMD application. **Do not build this.** |
| **Call recording** | MixMonitor + `recording_log` | `recording_lookup` returns `start_time\|user\|recording_id\|lead_id\|duration\|location` where location is an HTTP URL to the WAV |
| **Agent and closer routing** | In-groups, `vicidial_closer_log` | Human verifiers log in as VICIdial agents in a closer in-group |
| **Real-time agent availability** | `in_group_status`, `agent_ingroup_availability`, `agent_status` | `agent_ingroup_availability` (added 260822) returns per-in-group available counts, optionally as JSON with configurable key names |
| **Scheduled callbacks** | `vicidial_callbacks` | `callback=Y` with `callback_status`, `callback_datetime` (accepts `NOW` or `xDAYS`), `callback_type` (`USERONLY`/`ANYONE`), `callback_user`, `callback_comments` |

### 2.2 Capabilities the control plane reads from VICIdial

| Need | Function | Returns |
|---|---|---|
| Campaign inventory and dial configuration | `campaigns_list` | `campaign_id\|campaign_name\|active\|user_group\|dial_method\|dial_level\|lead_order\|dial_statuses\|dial_timeout\|dial_prefix\|manual_dial_prefix\|three_way_dial_prefix` |
| Hopper depth and composition | `hopper_list` | `hopper_order,priority,lead_id,list_id,phone_number,phone_code,state,status,count,gmt_offset,rank,alt,hopper_source,vendor_lead_code,source_id,age_days,last_call_time` |
| Per-call detail | `callid_info` with `detail=YES` | `call_id,custtime,call_date,campaign_id,list_id,status,user,phone` |
| Call history by number | `phone_number_log` | `phone_number\|call_date\|list_id\|length_in_sec\|lead_status\|hangup_reason\|call_status\|source_id\|user` |
| Lead record | `lead_all_info`, `lead_field_info`, `lead_search` | Full `vicidial_list` row including `status`, `vendor_lead_code`, `source_id`, `list_id`, `gmt_offset_now`, `entry_list_id`, `lead_id` |
| Agent state | `agent_status` | `status,call_id,lead_id,campaign_id,calls_today,full_name,user_group,user_level,pause_code,real_time_sub_status,phone_number,vendor_lead_code,session_id,computer_ip`. Sub-status values: `DEAD`, `DISPO`, `3-WAY`, `PARK`, `RING`, `PREVIEW`, `DIAL`. |
| Recording location | `recording_lookup` | Searchable by `agent_user`, `lead_id`, `date`, `uniqueid`, `extension`; `duration=Y` adds seconds |

### 2.3 Capabilities the control plane writes to VICIdial

| Action | Function | Notes |
|---|---|---|
| Push a lead | `add_lead` | Returns `lead_id`; supports custom fields when `custom_fields=Y` and the list defines them |
| Update a lead or its status | `update_lead` | Can match by `lead_id`, `vendor_lead_code` or `phone_number` via `search_method`; `insert_if_not_found=Y` upserts |
| Bulk status change | `batch_update_lead` | Comma-separated `lead_ids`, single field value set. **No per-lead admin log entries are written** — the control plane's own audit must cover this. |
| **Write a disposition back to a call log** | `update_log_entry` | Takes `call_id` (uniqueid or the 20-character ID), `group` (campaign or in-group), `status`. Updates `vicidial_log` or `vicidial_closer_log`. |
| Queue a lead for immediate dial | `add_lead`/`update_lead` with `add_to_hopper=Y&hopper_priority=99` | The "speed to lead" path |
| Suppress a number | `add_dnc_phone` | Campaign-scoped or `SYSTEM_INTERNAL` |
| Schedule a callback | `update_lead` with `callback=Y` | `callback_datetime=NOW` or `xDAYS` |

### 2.4 Verified operational caveats

These come from the API documentation itself and must shape the integration design.

1. **Permission model is coarse and per-function.** Most write functions require `user_level ≥ 8` plus a specific flag (`modify_leads`, `modify_lists`, `modify_campaigns`, `modify_users`, "view reports", "AGC Admin Access"). A single API account with everything enabled is a large blast radius. **Use three separate API accounts** — read-only, lead-write, disposition-write — each with the minimum flags.
2. **`phone_number` is not indexed by default** in `vicidial_log` and `vicidial_closer_log`. The documentation explicitly advises adding indexes before relying on `phone_number_log`. Adding them is a DBA task on the VICIdial MySQL instance, not something the control plane can do.
3. **Hard result limits**: `recording_lookup` and `did_log_export` cap at 100,000 rows; `lead_status_search` caps at 2,000; `hopper_bulk_insert` caps at 1,000 lead IDs per call.
4. **Output formats** are `pipe` (default), `csv`, `tab`, `json`, `newline` via the `stage` parameter. **Always request `stage=json`** — pipe parsing of free-text fields is fragile.
5. **Errors are HTTP 200 with a text body** beginning `ERROR:`, `NOTICE:` or `SUCCESS:`. The adapter must parse the prefix, never rely on status codes.
6. **CORS support was added in 2021; PHP 8 compatibility and JSON output landed in 2026** (rev 260519-1647). Confirm the deployed `non_agent_api.php` build date matches or exceeds the functions you depend on — `agent_ingroup_availability` requires 260822 or later.
7. **`hopper_bulk_insert` routes by list**, inserting each lead into the hopper of the campaign tied to its `list_id`. The control plane must therefore keep list-to-campaign mapping accurate.

## 3. Verified Risks in the Current Stack

### 3.1 Asterisk 18 is end of life

Asterisk 18 was an LTS release that transitioned to security-fix-only in October 2024 and reached full end of life in October 2025, after which it receives no updates of any kind, including security patches. The system reports a build date of 2026-08-22, which reflects VICIdial's own packaging, not upstream support.

**Consequence:** an unpatched, internet-adjacent SIP stack carrying PHI-adjacent Medicare calls. This is an infrastructure risk item with a named owner and a date, not a footnote. The migration path is complicated by the fact that VICIdial's supported Asterisk version is determined by the VICIdial project, not by Asterisk's own schedule — **do not upgrade Asterisk independently of VICIdial**. The action is to confirm with the VICIdial project which Asterisk branch VICIdial 2.14 or its successor supports, and schedule accordingly.

### 3.2 Other verified issues

| # | Issue | Evidence |
|---|---|---|
| 1 | Postgres password `admin` hardcoded in `docker-compose.yml`, repository public | Repository inspection |
| 2 | Runtime `pip install aiokafka==0.10.0` in the compose command | `docker-compose.yml` |
| 3 | Gateway `/internal/*` diagnostics are unauthenticated | `services/ai-gateway/app/main.py` |
| 4 | No outbox or reconciliation — a Kafka restart at call end orphans the recording | `docs/CURRENT_STATUS.md` |
| 5 | `ASR_PROVIDER=nemo` in `.env.example` while `STT_PROVIDER_CLASS` points at FasterWhisper | Config inspection |
| 6 | Phase numbering conflict between `CURRENT_STATUS.md` and `ROADMAP.md` | Both files |
| 7 | Dashboard has no lint, test or build job in CI | `.github/workflows/ci.yml` |
| 8 | Repository root carries log files, scratch scripts, and a duplicated `services/ai-gateway/services/...` path | Repository inspection |

---

# PART 1 — ARCHITECTURE

## 4. The Integration Model

### 4.1 The decision: VICIdial owns the dialer, TalkFlow owns the business

My earlier recommendation was for TalkFlow to originate calls directly through Asterisk ARI, on the reasoning that splitting compliance enforcement across two systems is dangerous. **That reasoning was right; the conclusion was wrong.**

The correct way to avoid split enforcement is not to duplicate the dialer — it is to make VICIdial the **single enforcement point for dialing** and TalkFlow the **single enforcement point for business logic**, with a strict, audited boundary between them.

Building a parallel ARI originator alongside a running VICIdial would mean two systems deciding who to call, two DNC lists, two calling-hour implementations, two sets of channel accounting, and reconciliation between `vicidial_log` and `calls` that can never be fully correct. It is more code, more risk, and it throws away a dialer the client already operates.

### 4.2 Division of responsibility

```text
╔══════════════════════════════════╦══════════════════════════════════╗
║  VICIDIAL 2.14 + ASTERISK 18     ║  TALKFLOW CONTROL PLANE          ║
║  (authoritative for dialing)     ║  (authoritative for business)    ║
╠══════════════════════════════════╬══════════════════════════════════╣
║  Who gets dialled next (hopper)  ║  Which leads are eligible at all ║
║  Pacing / dial ratio / drops     ║  Lead master record + provenance ║
║  Local + state call-time rules   ║  Consent artefact per lead       ║
║  DNC list enforcement            ║  Suppression master + reasons    ║
║  AMD / voicemail detection       ║  Scripts, versions, approval     ║
║  Carrier trunk + caller ID       ║  Eligibility rule sets           ║
║  MixMonitor recording capture    ║  Call record + transcript        ║
║  Agent/closer in-group routing   ║  Qualification evidence          ║
║  Callback scheduling             ║  Dispositions (4-layer) + QA     ║
║  vicidial_log / closer_log       ║  Analytics, exports, audit       ║
║                                  ║  Verifier context payload        ║
║                                  ║  Recording access + retention    ║
╚══════════════════════════════════╩══════════════════════════════════╝
```

**The one rule that keeps this honest:** every suppression decision is written to **both** systems. A number suppressed in TalkFlow is pushed to VICIdial via `add_dnc_phone` in the same transaction boundary, and the reconciler verifies agreement on a schedule. Two DNC lists that can disagree is the failure mode this architecture must never have.

### 4.3 Verified call flow

```text
 1  TalkFlow: lead imported, validated, consent artefact checked, campaign assigned
 2  TalkFlow → VICIdial:  add_lead(dnc_check=Y, campaign_dnc_check=Y,
                          duplicate_check=DUPSYS90DAY, add_to_hopper=Y,
                          hopper_local_call_time_check=Y, tz_method=...,
                          vendor_lead_code=<talkflow_lead_id>)
                          → returns vicidial lead_id
 3  VICIdial: hopper → pacing → originate → carrier → customer answers
 4  VICIdial: AMD runs. Machine → campaign AM action. Human → continue.
 5  Asterisk dialplan: answered human channel → AudioSocket → ai-gateway:9019
                       (campaign + lead identity passed on the channel — §6.3)
 6  ai-gateway:  loads the active script bundle for that campaign from Redis
                 VAD → ASR → script graph → TTS, with barge-in
 7  ai-gateway → Kafka: call.opened, call.event, call.transcript,
                        call.field, call.closed
 8  TalkFlow workers: persist to PostgreSQL; outbox → Redis → dashboard WS
 9  On QUALIFIED: gateway signals transfer
10  TalkFlow: checks verifier availability via VICIdial in-group status,
              then the channel is transferred into the closer in-group
11  VICIdial: routes to an available human verifier (a VICIdial agent)
12  Verifier screen: TalkFlow serves full caller context in one payload
13  Call ends. MixMonitor writes the WAV.
14  recording-worker: SFTP pull → SHA-256 → object storage → call_recordings
15  TalkFlow → VICIdial: update_log_entry(call_id, group, status)
                         writes the final disposition back
16  Reconcilers: recordings, dispositions, DNC — every 5 minutes
```

### 4.4 Why this is lower risk than the ARI design

| Concern | ARI-direct design | VICIdial-integrated design |
|---|---|---|
| Calling hours | TalkFlow reimplements state + local time | VICIdial enforces, verified at hopper insert |
| DNC | TalkFlow only | Both, with reconciliation |
| AMD | TalkFlow builds it | Already exists |
| Pacing and drop rate | TalkFlow builds it | Already exists, already tuned |
| Human agent routing | TalkFlow builds it | In-groups already exist |
| Telephony dispositions | TalkFlow derives from ARI events | `vicidial_log.status` is authoritative |
| Client operational familiarity | New system to learn | SmartBrains already runs it daily |
| Code to write | Dialer, pacer, AMD, router, call-time engine | One API adapter |

### 4.5 What TalkFlow still needs that VICIdial does not provide

VICIdial has no concept of: versioned approved scripts, eligibility rule sets, conversation transcripts, per-field qualification evidence, consent provenance, QA scorecards, a four-layer disposition taxonomy, role-scoped dashboards, or an append-only audit log. That is the entire justification for the control plane, and it is a strong one.

## 5. Services and Stack

### 5.1 Deployable units

```text
services/
  ai-gateway/        EXISTING  realtime audio + AI            (Python/FastAPI)
  recording-worker/  EXISTING  recording ingest               (Python)
  tts-worker/        EXISTING  generative TTS                 (Python)

  app-api/           NEW       REST control plane             (Python/FastAPI)
  realtime-api/      NEW       dashboard WebSocket            (Python)
  workers/           NEW       consumers + scheduled jobs     (Python)

packages/
  contracts/         NEW       enums, DTOs, events, error codes
  db/                NEW       SQLAlchemy models + single Alembic history
  core/              NEW       logging, tracing, ids, phone, redaction
  storage/           NEW       promoted from recording-worker/app/storage
  vicidial/          NEW       the VICIdial API adapter (§8)
```

`realtime-api` is the **dashboard's** socket server. `ai-gateway` is the **caller's** audio server. They share no code path and must never be conflated in conversation or configuration.

### 5.2 Language: Python

Not a preference — a consequence. Two production Python services already exist with settled patterns (pydantic-settings, structlog, provider DI by class path, asyncpg). Alembic is already configured with a live head. CI already runs ruff and pytest over Python services. A TypeScript backend would buy a shared types package that a JavaScript dashboard cannot consume anyway. The contract is preserved through generated OpenAPI instead (§7.3).

### 5.3 Technology

| Concern | Choice | Justification |
|---|---|---|
| Framework | FastAPI + Uvicorn | Matches gateway; native OpenAPI |
| ORM / migrations | SQLAlchemy 2.0 async + Alembic | Both already present |
| Driver | asyncpg | Already used |
| Validation / settings | pydantic 2.x, pydantic-settings | House pattern |
| Event bus | **Kafka (existing)** | Already deployed and carrying recordings. Topics namespaced `talkflow.<domain>.<event>.v1`, matching `talkflow.recording.requests.v1`. |
| Scheduling | APScheduler for cron-style jobs; Kafka consumers for event-driven | Avoids introducing a second queue system |
| Cache / locks / presence | Redis (existing) | Namespace `cp:` — `TTS_REDIS_DB=0` is already in use |
| WebSocket | `websockets` + Redis pub/sub | Already a dependency |
| Object storage | Extend `packages/storage` (`local`, `s3`) | Providers already written and working |
| VICIdial client | `httpx` async, `stage=json` | §8 |
| Logging / metrics / tracing | structlog, Prometheus, OpenTelemetry | Gateway already uses structlog |
| Lint / test | ruff, pytest, testcontainers | Already the CI standard |

**Not added:** Kubernetes, a second broker, a service mesh, a separate analytics database, an ARI client.

## 6. The Gateway Boundary

### 6.1 The absolute constraint

Nothing the control plane does may add latency to the conversational turn. The gateway maintains a sub-second loop; every control-plane ingest path is fire-and-buffer, never synchronous-and-blocking. The one exception is opt-out (§6.4), which must be durable before the call ends.

### 6.2 Kafka topics

```text
EXISTING
talkflow.recording.requests.v1    gateway → recording-worker
talkflow.recording.ready.v1       recording-worker → control plane
talkflow.recording.failed.v1      recording-worker → control plane

NEW — gateway produces
talkflow.call.opened.v1           channel id, campaign, direction, vicidial ids,
                                  script version, rule set version
talkflow.call.event.v1            state and node transitions
talkflow.call.transcript.v1       final turns, batched
talkflow.call.field.v1            captured fields + confidence + transcript ref
talkflow.call.transfer_req.v1     qualified, requesting a verifier
talkflow.call.closed.v1           terminal state + proposed disposition

NEW — control plane produces
talkflow.call.qualified.v1        → crm-pusher
talkflow.lead.import.v1           → import-processor
talkflow.export.requested.v1      → export-builder
talkflow.dashboard.event.v1       → realtime-api fanout
talkflow.vicidial.sync.v1         → vicidial-adapter (lead push, dispo writeback)
```

Consumer groups versioned `talkflow-<worker>-v1`, manual commit, `earliest` offset reset — matching the existing `talkflow-recording-workers-v1` convention.

### 6.3 The identity problem, and its solution

**The gateway currently has a connection id and nothing else.** It cannot know which campaign a call belongs to, therefore cannot load the right script. This is the single most load-bearing unsolved item in the project.

The solution is a dialplan change, not a code change. Asterisk's AudioSocket application takes a UUID as its first argument. VICIdial exposes the lead and call identifiers as channel variables in the dialplan. The dialplan therefore passes identity at connect time:

```text
; Asterisk dialplan — answered outbound call routed to the bot
exten => _X.,n,Set(TF_UUID=${UNIQUEID})
exten => _X.,n,Set(TF_LEAD=${vicidial_lead_id})
exten => _X.,n,Set(TF_CAMP=${campaign_id})
exten => _X.,n,AudioSocket(${TF_UUID},<gateway-host>:9019)
```

The gateway resolves `TF_UUID` against the control plane's internal lookup (`GET /internal/session/{uniqueid}`), which returns campaign, TalkFlow lead id, script version and rule set version. The control plane knows the mapping because it pushed the lead to VICIdial with `vendor_lead_code` set to the TalkFlow lead id (§8.2).

**Fallback:** if the lookup fails, the gateway queries the VICIdial Non-Agent API `callid_info` with `detail=YES`, which returns `campaign_id`, `list_id` and `lead_id` for a call id. **If both fail, the gateway refuses the call and alerts. There is no path where the bot speaks without knowing which script governs it.**

Exact channel-variable names must be confirmed against the deployed VICIdial dialplan by the telephony admin — this is a first-week task, not an assumption.

### 6.4 Required gateway changes

| Ref | Change | Milestone |
|---|---|---|
| G1 | Publish lifecycle events to Kafka | M3 |
| G2 | Buffer and replay on publish failure — the current `RecordingRequestPublisher` logs and drops | M3 |
| G3 | Accept and resolve call identity at session open (§6.3) | M3 |
| G4 | Load the script bundle from Redis instead of the hardcoded state enum | M5 |
| G5 | Record `recording_offset_ms` at any compliance-relevant utterance | M3 |
| G6 | Detect opt-out keywords and call the suppression API **synchronously** before the call ends | M4 |
| G7 | Emit a transfer request instead of terminating on `qualified` | M7 |
| G8 | Attach `node_id` to every transcript turn | M3 |
| G9 | Emit the frozen latency fields (§21) | M3 |
| G10 | Import enums from `packages/contracts` instead of redefining them | M1 |
| G11 | Put `/internal/*` behind network policy in production | M0 |

**G3, G1 and G4 are the critical three.** Without them the control plane has no data and the bot has no script.

---

# PART 2 — GROUND RULES

## 7. Non-Negotiable Engineering Rules

Twelve rules. Every review checks them. A pull request that breaks one is rejected regardless of whether the feature works.

| # | Rule | Enforced by |
|---|---|---|
| R1 | One Alembic history. Every migration descends from `41960d8b814f`. The recording-worker migration directory is retired into it. | CI single-head check |
| R2 | No business logic in a route handler. Routes validate, call a service, serialise. | Review + import-linter |
| R3 | No module reaches into another module's tables or repositories. Cross-module access is via an injected service. | CI import-boundary contract |
| R4 | Every route carries an explicit permission dependency or an explicit public marker. | CI route-enumeration test |
| R5 | Every repository query takes a `scope` argument with no default. | Type signature; CI fails on a default |
| R6 | Nothing in the control plane may block the realtime loop. | Architecture review |
| R7 | No secret is ever returned by an API, to any role, including Master Admin. | CI response-model scan |
| R8 | Compliance invariants are enforced at the database level, not only in Python. | Integration tests against real Postgres |
| R9 | Every state-changing endpoint is idempotent or version-guarded. | Review checklist |
| R10 | The OpenAPI document is generated, committed and diffed. | CI drift gate |
| R11 | **Every VICIdial write is idempotent and reconciled.** No fire-and-forget call to `non_agent_api.php`. | §8.6 |
| R12 | **Suppression is written to both systems or neither.** | §8.4 |

## 8. The VICIdial Adapter — `packages/vicidial`

The most important new component. It is the only place in the codebase that speaks to VICIdial.

### 8.1 Client design

```python
class VicidialClient:
    """One client per credential profile. Never share an account across roles."""
    base_url: str              # https://<vicidial>/vicidial/non_agent_api.php
    user: str                  # per-profile vicidial_users account
    password: SecretStr
    source: str                # <= 20 chars, appears in VICIdial's API log
    timeout: float = 10.0
```

**Three credential profiles, three accounts, minimum flags each:**

| Profile | VICIdial flags needed | Used for |
|---|---|---|
| `readonly` | user_level ≥ 8, "view reports" | `campaigns_list`, `hopper_list`, `in_group_status`, `agent_ingroup_availability`, `agent_status`, `recording_lookup`, `callid_info`, `phone_number_log`, `lead_all_info` |
| `leadwrite` | user_level ≥ 8, `modify_leads=1` | `add_lead`, `update_lead`, `batch_update_lead`, `hopper_bulk_insert`, `lead_search` |
| `dncwrite` | user_level ≥ 8, `modify_lists`, "Delete From DNC Lists" | `add_dnc_phone`, `delete_dnc_phone`, `update_log_entry` |

Splitting the credentials means a bug in the analytics reader cannot delete a DNC entry.

### 8.2 Identity mapping — the keystone

```text
TalkFlow leads.id (UUID v7)
        │
        │  pushed as vendor_lead_code on add_lead
        ▼
VICIdial vicidial_list.vendor_lead_code  ──►  vicidial_list.lead_id (int)
        │                                              │
        │  stored back on the TalkFlow lead            │
        ▼                                              ▼
TalkFlow leads.vicidial_lead_id                 used in every VICIdial call
```

```text
Asterisk UNIQUEID  ──►  TalkFlow calls.channel_id (UNIQUE)
                   ──►  VICIdial vicidial_log.uniqueid
                   ──►  the AudioSocket UUID argument
```

**`vendor_lead_code` is limited to 20 characters.** A UUID v7 string is 36. Therefore push a **short stable key**, not the raw UUID: a base32-encoded 12-byte prefix, stored on the lead as `external_key` and indexed unique. This is a schema decision, not an implementation detail — get it right in the first migration.

### 8.3 Response parsing

VICIdial returns HTTP 200 with a text body regardless of outcome. Every response is classified before use:

```python
class VicidialOutcome(StrEnum):
    SUCCESS = "SUCCESS"   # body starts with "SUCCESS:"
    NOTICE  = "NOTICE"    # informational, operation may have partially applied
    ERROR   = "ERROR"     # body starts with "ERROR:"
```

`NOTICE` is the dangerous case. `add_lead` can return `SUCCESS: add_lead LEAD HAS BEEN ADDED` followed by `NOTICE: add_lead NOT ADDED TO HOPPER, OUTSIDE OF LOCAL TIME` — the lead exists but will not be dialled. **The adapter parses every line, not just the first**, and surfaces notices as structured fields the control plane acts on.

Always request `stage=json`. Confirm the deployed API build supports it (rev 260519-1647 or later) before relying on it; fall back to pipe parsing with a recorded warning if not.

### 8.4 Suppression synchronisation — R12

```text
TalkFlow suppression write (single transaction):
  1. INSERT suppression_entries
  2. INSERT outbox row  (talkflow.vicidial.sync.v1, action=add_dnc)
  COMMIT
        ↓
  3. vicidial-adapter worker: add_dnc_phone(campaign_id=SYSTEM_INTERNAL)
                              + add_dnc_phone(campaign_id=<each active campaign>)
  4. On success: mark synced_at
  5. On failure: retry with backoff; alert after N attempts
        ↓
  6. dnc-reconciler (hourly): compare TalkFlow suppression against VICIdial
     DNC for a sample; any divergence raises a P1 alert
```

**A suppression that is not yet synced to VICIdial blocks the lead in TalkFlow anyway**, because the lead is removed from the hopper via `update_lead(remove_from_hopper=Y)` in the same worker pass. Belt and braces: the number is blocked by TalkFlow's own hopper management even before VICIdial's DNC list is updated.

Removal is the inverse and requires Master Admin, a mandatory reason and a typed confirmation. Removal is soft in TalkFlow — the entry is retained with `removed_at` — while `delete_dnc_phone` removes it in VICIdial. Proving a number *was* suppressed is a legal necessity, so TalkFlow never erases the record.

### 8.5 Disposition writeback

When TalkFlow closes a call it writes the outcome back so VICIdial's own reports reconcile:

```text
update_log_entry(call_id=<uniqueid>, group=<campaign_id|in_group>, status=<vicidial_status>)
```

This requires the four-layer taxonomy to map onto VICIdial's flat status codes — see §14.3. The mapping is **configuration**, stored in the `dispositions` table, not hardcoded, because SmartBrains may add campaign statuses at any time.

### 8.6 Idempotency and reconciliation — R11

| Operation | Idempotency mechanism |
|---|---|
| `add_lead` | `duplicate_check=DUPSYS90DAY` plus `vendor_lead_code` uniqueness. A retry returns `ERROR: add_lead DUPLICATE PHONE NUMBER IN SYSTEM` with the existing `lead_id`, which the adapter treats as success and records. |
| `update_lead` | Naturally idempotent for field sets; guarded by the TalkFlow entity `version` |
| `add_dnc_phone` | Returns `ERROR: DNC NUMBER ALREADY EXISTS` — treated as success |
| `update_log_entry` | Same status written twice is a no-op; adapter records `last_written_status` and skips a match |
| `hopper_bulk_insert` | Returns per-lead notices including `LEAD IS ALREADY IN THE HOPPER` — parsed, not fatal |

**Three reconcilers, all scheduled:**

| Reconciler | Interval | Compares |
|---|---|---|
| `recording-reconciler` | 5 min | Completed calls with no `ready`/`failed` recording row → re-query `recording_lookup`, requeue SFTP fetch. Closes the orphan gap in `CURRENT_STATUS.md`. |
| `disposition-reconciler` | 15 min | TalkFlow `calls.disposition` vs VICIdial `callid_info` status → re-write divergences, alert on repeated failure |
| `dnc-reconciler` | 60 min | Sampled comparison of suppression lists both ways |

### 8.7 Rate limiting and failure

VICIdial's API is a PHP script against MySQL on a machine that is also running a dialer. **Treat it as a fragile shared resource.**

- Client-side rate limit: default 5 requests/second, configurable, enforced in the adapter.
- Bulk operations use `hopper_bulk_insert` (1,000 per call) and `batch_update_lead` rather than loops.
- Circuit breaker opens after N consecutive failures and raises an alert rather than hammering the dialer.
- Every call is logged with `source` set to a recognisable TalkFlow marker so the VICIdial admin can see what the control plane is doing in VICIdial's own API log.
- **No VICIdial call is ever made from a request handler.** All traffic goes through the worker, driven by the outbox, so a slow dialer cannot stall the dashboard.

## 9. Module Template

Every one of the twenty-plus modules has the same file structure. This is the highest-leverage standard in the document: it makes any module navigable by any developer, makes review mechanical, and makes the twentieth module as fast to build as the third.

```text
app/modules/<module>/
├── router.py       FastAPI routes; permissions; response models
├── service.py      business rules; transactions; events; audit
├── repository.py   queries; scope-aware
├── schemas.py      module-local request/response (re-exports contracts)
├── errors.py       module error codes, registered centrally
├── events.py       outbox payload builders
└── policies.py     pure functions: guards, validators, state machines

tests/modules/<module>/
├── test_policies.py     pure unit tests, no I/O
├── test_service.py      with a real database (testcontainers)
├── test_router.py       HTTP contract, permissions, error envelope
└── test_invariants.py   DB triggers and constraints — attempt the violation
```

`policies.py` is where the highest-risk logic lives and it has **no database access**. The campaign start guard, the script version state machine, the rule evaluator, the compliance profile checker — all pure, all exhaustively testable in milliseconds, all at 100% branch coverage.

Guards return **every** problem, not the first:

```python
def can_start_campaign(c: CampaignSnapshot) -> list[ErrorCode]:
    problems = []
    if not c.active_script_version_id: problems.append(E.CAMPAIGN_NO_ACTIVE_SCRIPT)
    if not c.rule_set_version_id:      problems.append(E.CAMPAIGN_NO_RULE_SET)
    if not c.vicidial_campaign_id:     problems.append(E.CAMPAIGN_NO_VICIDIAL_MAPPING)
    if not c.vicidial_list_ids:        problems.append(E.CAMPAIGN_NO_LIST_MAPPING)
    if not c.closer_in_group:          problems.append(E.CAMPAIGN_NO_VERIFIER_GROUP)
    if not c.compliance_profile_id:    problems.append(E.CAMPAIGN_NO_COMPLIANCE_PROFILE)
    return problems
```

One round trip shows the manager every gap instead of five.

## 10. Layering and Cross-Cutting Machinery

```text
  api/         FastAPI routers. HTTP only.
    ↓
  service/     Business rules, transactions, events, audit.
    ↓
  repository/  Data access. Scope-aware. No business rules.
    ↓
  model/       SQLAlchemy ORM.
```

Enforced by an `import-linter` contract in CI. A route handler longer than about fifteen lines is doing something it should not.

| Concern | Mechanism |
|---|---|
| Envelope | Response generics `DataResponse[T]`, `PagedResponse[T]` — keeps OpenAPI accurate, unlike body-rewriting middleware |
| Errors | One exception hierarchy, one handler, `{ error: { code, message, status, details, traceId } }` |
| Error registry | `contracts/errors.py` enumerates every code; `docs/error-codes.md` generated from it. A free-form string fails review. |
| Pagination | `page`, `pageSize` (default 25, max 100), `sort`/`order` whitelisted per resource |
| Idempotency | `Idempotency-Key` header + `idempotency_keys` table storing key, actor, route, request hash, response, expiry |
| Audit | `@audited(action, resource_type)` writing in the caller's transaction |
| Tracing | Middleware assigns `trace_id`, binds to structlog and OpenTelemetry, returns it in the error envelope |
| Rate limiting | Redis sliding window — auth 5/min, export 10/hr, import 20/hr, general 300/min |
| PII masking | **One** serializer. A `MaskedPhone` pydantic type renders full or masked from the actor's `pii.view_full` permission. No second code path. |
| Time | `utcnow()` from `core`; `datetime.now()` fails lint |
| Wire casing | camelCase on the wire, snake_case in Python, via a single alias generator in `contracts` |

## 11. Testing, CI, Observability, Security

### 11.1 Testing

| Layer | Scope | Gate |
|---|---|---|
| Unit | `policies.py` — guards, state machines, rule evaluation, compliance checks | 100% branch coverage |
| Integration | Service + real Postgres + real Redis via testcontainers | Every service method: one happy path, every documented failure mode |
| Invariant | Attempt each DB trigger/constraint violation **in raw SQL** | Every rule in §16.3 has a test that tries to break it |
| Contract | Router tests: status, envelope, error code, permission | Every route: authorised, unauthorised, invalid input |
| **VICIdial adapter** | Against a **recorded-response fixture set** captured from the real API, plus a live smoke suite run against the staging dialer | Every function used, every documented ERROR and NOTICE string parsed correctly |
| E2E | Seeded scenario through a real test call on the staging extension | Nightly and pre-release |

Coverage gate: 85% overall, 100% on policies.

**Concurrency tests are mandatory for five flows:** simultaneous script activation, double import commit, two verifiers accepting one transfer, two managers editing one campaign, and a suppression written while the same lead is being pushed to the hopper.

**The VICIdial fixture set deserves emphasis.** The adapter's correctness depends on parsing exact strings like `NOTICE: add_lead NOT ADDED TO HOPPER, OUTSIDE OF LOCAL TIME`. Capture real responses once, commit them, and test against them. A mocked `"SUCCESS"` string proves nothing.

### 11.2 CI

```text
 1  lint              ruff check + format
 2  types             mypy --strict on packages/ and service layers
 3  boundaries        import-linter (R2, R3)
 4  security          route permission enumeration (R4)
                      response-model secret scan (R7)
                      pip-audit, gitleaks
 5  migrations        single-head check; upgrade on fresh DB;
                      upgrade→downgrade→upgrade round trip
 6  contract          regenerate openapi.json; fail on diff without a
                      CONTRACT_VERSION bump (R10)
 7  test              unit + integration + invariant + contract + adapter fixtures
 8  dashboard         eslint + next build           ← absent today, add it
 9  build             docker build all services, tag with commit SHA
── merge to main ──
10  publish → 11 deploy:staging → 12 e2e against staging dialer
── tagged release ──
13  manual approval → deploy:prod → migrate → rolling restart → smoke
```

Migration rules: expand/contract only; no migration holds a lock on `calls` or `transcript_turns` for more than a second; index creation uses `CONCURRENTLY`; every migration tested against a restored copy of production data once production has data.

### 11.3 Observability

structlog JSON with `trace_id`, `service`, `module`, `actor_id`, `route`, `duration_ms`. **PII redacted by a processor in the structlog chain**, not by developer discipline.

```text
talkflow_http_requests_total{service,route,method,status}
talkflow_http_request_duration_seconds{service,route}
talkflow_kafka_consumer_lag{topic,group}
talkflow_outbox_pending_total
talkflow_ws_fanout_lag_seconds
talkflow_vicidial_api_calls_total{function,outcome}
talkflow_vicidial_api_duration_seconds{function}
talkflow_vicidial_reconcile_divergences_total{reconciler}
talkflow_transfer_outcomes_total{campaign,outcome}
talkflow_recording_pipeline_duration_seconds{stage}
```

Alerts are rows in `alerts` with acknowledge and resolve states. Minimum rules: transfer failure rate, outbox pending, Kafka consumer lag, recording backlog, **VICIdial API circuit open**, **any reconciler divergence**, CRM failure queue, dependency offline.

### 11.4 Security

| Control | Standard |
|---|---|
| Auth | JWT access 15 min in memory; opaque refresh hashed, httpOnly/Secure/SameSite=Strict, rotated with reuse detection; Argon2id passwords |
| Authorization | Permission dependency on every route (R4) + `AccessScope` on every query (R5) |
| PII at rest | AES-GCM for date of birth and any captured health-adjacent answer; phone indexed but access-controlled |
| PII in transit | Single masking serializer keyed on `pii.view_full` |
| Recordings | 5-minute presigned playback URL; single-use download token; both audited; bucket private; **the VICIdial `recording_lookup` HTTP location is never passed to the browser** |
| VICIdial credentials | Three separate accounts, minimum flags, in the secret manager, never returned by any API |
| Secrets | Secret manager injected at boot; the `admin` Postgres password is rotated and removed from the public repository in M0 |
| Gateway endpoints | `/internal/*` unreachable from outside the private network in production |
| Gateway service auth | Scoped token, IP-allowlisted, able to write only to calls it opened |
| Headers | Strict CORS allowlist, no wildcard, HSTS |

---

# PART 3 — THE CONVERSATION, THE DATA, AND THE RULES

## 12. The Production Script

### 12.1 What it is now

```text
1  GREETING   "Hi, how are you doing today? This is {agent_alias}."
2  PITCH      "I'm calling because your health and groceries benefit
               have not been claimed yet, and they're about to close out."
3  QUESTION   "So do you currently have Medicare Part A and B?"
4  QUESTION   "And are you between the age of 60 to 87?"
5  CONFIRM    "Alright, great."
6  TRANSFER   "Now let me bring the senior on the line for further
               discussion. Please stay on the line."
```

`{agent_alias}` rotates across a configured set (Adriana, Alex, Parker, Ashley).

### 12.2 What changed from the implemented engine

The gateway's current state machine collects consent, name, age (as a number), Part A, Part B and ZIP. The production script collects **two booleans**. This is a substantial simplification and a substantial change.

| Element | Implemented today | Production script | Consequence |
|---|---|---|---|
| Consent | `waiting_for_consent` state, `consent` boolean | **Absent** | No consent evidence record. §15. |
| Full name | `collecting_name` | **Absent** | The verifier screen has no caller name. Name must come from the VICIdial lead record if the vendor supplied one. |
| Age | `collecting_age`, captured as an integer | **A yes/no range confirmation** | Cannot compute eligibility, cannot store a derived age, cannot report age distribution. DQ reason granularity collapses to "age range denied". |
| Part A | `collecting_part_a` | **Merged into one question with Part B** | Cannot distinguish `disqualified_no_part_a` from `disqualified_no_part_b`. One combined DQ reason only. |
| Part B | `collecting_part_b` | Merged as above | As above |
| ZIP | `collecting_zip` | **Absent** | State cannot be derived from the conversation. It must come from the VICIdial lead (`state`, `postal_code`) or from area-code lookup. This matters, because state determines consent rules (§15.3). |

**Recommendation, recorded not imposed:** splitting question 3 into two questions costs about four seconds of call time and restores the ability to say *why* leads disqualify. With them merged, a campaign whose DQ rate rises has no diagnostic path. The same applies to capturing the age as a number rather than a range confirmation. Both are business decisions for SmartBrains; the platform supports either.

### 12.3 The script as a node graph

This is the exact bundle the script module produces and the gateway executes.

```json
{
  "scriptVersionId": "…",
  "entryNodeId": "n_greeting",
  "agentAliases": ["Adriana", "Alex", "Parker", "Ashley"],
  "nodes": [
    {
      "id": "n_greeting", "type": "greeting", "label": "Greeting",
      "prompt": "Hi, how are you doing today? This is {agent_alias}.",
      "allowBargeIn": true, "noResponseMs": 3000, "maxRetries": 1,
      "fallbackPrompt": "Hello? Can you hear me okay?",
      "ttsAssetStatus": "pending",
      "transitions": [
        { "id": "t_g1", "when": "always",      "nextNodeId": "n_pitch" },
        { "id": "t_g2", "when": "no_response", "nextNodeId": "n_end_silence" }
      ]
    },
    {
      "id": "n_disclosure", "type": "disclosure", "label": "Required disclosure",
      "prompt": "{disclosure_text}", "discussesBenefits": false,
      "complianceRole": "tpmo_disclaimer",
      "transitions": [{ "id": "t_d1", "when": "always", "nextNodeId": "n_pitch" }]
    },
    {
      "id": "n_pitch", "type": "statement", "label": "Benefit pitch",
      "prompt": "I'm calling because your health and groceries benefit have not been claimed yet, and they're about to close out.",
      "discussesBenefits": true,
      "allowBargeIn": true,
      "transitions": [{ "id": "t_p1", "when": "always", "nextNodeId": "n_part_ab" }]
    },
    {
      "id": "n_part_ab", "type": "question", "label": "Medicare Part A & B",
      "prompt": "So do you currently have Medicare Part A and B?",
      "captureField": "medicare_part_ab", "captureType": "boolean",
      "required": true, "maxRetries": 2, "noResponseMs": 4000,
      "fallbackPrompt": "I just need a yes or no — do you have Medicare Part A and B?",
      "allowBargeIn": true,
      "transitions": [
        { "id": "t_ab_y", "when": "yes",         "nextNodeId": "n_age_range" },
        { "id": "t_ab_n", "when": "no",          "nextNodeId": "n_dq" },
        { "id": "t_ab_r", "when": "no_response", "nextNodeId": "n_end_silence" }
      ]
    },
    {
      "id": "n_age_range", "type": "question", "label": "Age range",
      "prompt": "And are you between the age of 60 to 87?",
      "captureField": "age_in_range", "captureType": "boolean",
      "required": true, "maxRetries": 2, "noResponseMs": 4000,
      "fallbackPrompt": "Are you between 60 and 87 years old?",
      "allowBargeIn": true,
      "transitions": [
        { "id": "t_ar_y", "when": "yes",         "nextNodeId": "n_confirm" },
        { "id": "t_ar_n", "when": "no",          "nextNodeId": "n_dq" },
        { "id": "t_ar_r", "when": "no_response", "nextNodeId": "n_end_silence" }
      ]
    },
    {
      "id": "n_confirm", "type": "statement", "label": "Confirmation",
      "prompt": "Alright, great.",
      "transitions": [{ "id": "t_c1", "when": "always", "nextNodeId": "n_transfer" }]
    },
    {
      "id": "n_transfer", "type": "transfer", "label": "Transfer to verifier",
      "prompt": "Now let me bring the senior on the line for further discussion. Please stay on the line.",
      "transferTarget": "closer_in_group",
      "transitions": [
        { "id": "t_t1", "when": "always", "nextNodeId": "n_end_transferred" }
      ]
    },
    { "id": "n_dq",  "type": "closing", "label": "Not qualified",
      "prompt": "I understand — thank you for your time. Have a good day.",
      "terminal": true, "disposition": "disqualified_criteria" },
    { "id": "n_opt_out", "type": "opt_out", "label": "Opt out",
      "prompt": "I understand. I'll remove you from our list. Have a good day.",
      "terminal": true, "disposition": "opted_out", "suppresses": true },
    { "id": "n_end_silence", "type": "closing", "label": "No response",
      "prompt": "I'm not able to hear you. I'll try another time. Goodbye.",
      "terminal": true, "disposition": "silence_no_response" },
    { "id": "n_end_transferred", "type": "closing", "terminal": true,
      "disposition": "qualified_transferred" }
  ],
  "globalTransitions": [
    { "when": "opt_out_keyword", "nextNodeId": "n_opt_out" }
  ]
}
```

Three things in that bundle are not in the spoken script and are there deliberately:

- **`n_disclosure`** is present but not wired into the entry path. It exists so the disclosure can be switched on from the dashboard without a code change. Whether it is required is governed by the campaign's compliance profile (§15.4).
- **`n_opt_out` with a global transition** on opt-out keywords, because revocation must be honoured however it is expressed (§15.2).
- **`discussesBenefits`** on nodes, because the TPMO disclaimer rule is expressed in terms of benefit discussion (§15.1).

### 12.4 The rule set

```json
{
  "ruleSetVersion": 1,
  "name": "Medicare Fronter — Part A&B + Age 60-87",
  "all": [
    { "field": "medicare_part_ab", "operator": "==", "value": true },
    { "field": "age_in_range",     "operator": "==", "value": true }
  ],
  "disqualificationReasons": {
    "medicare_part_ab": "disqualified_no_part_ab",
    "age_in_range":     "disqualified_age_range"
  }
}
```

Evaluated by the backend, called by the gateway mid-call, **re-evaluated server-side at call close**. A discrepancy raises an alert — it means the bot and the platform disagreed, which is a defect, not a data point.

### 12.5 Note on the age band

Medicare eligibility below 65 arises only through disability or end-stage renal disease. A 60–87 screening band will therefore surface a meaningful share of 60–64 callers who answer "yes" to both questions and are not plan-eligible. That is a lead-economics issue rather than a platform issue, and it will show up as a gap between `qualified_transferred` and `verified_accepted`. The analytics module reports both rates separately so the gap is visible from week one.

## 13. Data Model

### 13.1 Migration strategy

**One Alembic history.** The first control-plane migration revises from `41960d8b814f`. The recording-worker's migration directory is retired into `app-api/alembic`. `call_recordings` is not rewritten — it gains a foreign key and its status strings are aligned to the frontend enum in the same migration.

### 13.2 Schema

IDs are UUID v7. Mutable aggregates carry `version`. Timestamps are `TIMESTAMPTZ`, UTC.

**Identity and governance**

```text
users                    id, name, email(uniq), password_hash, role, status,
                         timezone, mfa_enabled, last_login_at
roles / role_permissions
refresh_tokens           id, user_id, token_hash(uniq), family_id, expires_at,
                         revoked_at, replaced_by, user_agent, ip
audit_log                id, ts, actor_id, actor_role, action, resource_type,
                         resource_id, result, ip, user_agent, metadata JSONB,
                         trace_id           ── append-only, trigger-enforced
settings_versions        id, group_key, payload JSONB, version, changed_by
idempotency_keys         key, actor_id, route, request_hash, response JSONB,
                         expires_at
```

**Leads, provenance and suppression**

```text
leads                    id, external_key(uniq, <=20 chars — §8.2),
                         vicidial_lead_id, vicidial_list_id,
                         first_name, last_name, phone_normalized, alt_phone,
                         email, state, zip_code, date_of_birth(enc),
                         source, source_batch_id, vendor_id,
                         campaign_id, status, attempts, last_attempt_at,
                         next_attempt_at, assigned_to, suppressed,
                         custom_fields JSONB, version

lead_consent_artifacts   id, lead_id, artifact_type, captured_at, method,
                         origin_url, origin_ip, disclosure_text_version,
                         vendor_id, evidence_ref, verified_at
                         ── the TCPA record. §15.3.

lead_activity            id, lead_id, actor_id, action, before, after, ts
suppression_entries      id, phone_normalized, reason, source, evidence_ref,
                         added_by, added_at, expires_at, removed_by, removed_at,
                         removal_reason, vicidial_synced_at, vicidial_sync_error
                         ── UNIQUE(phone_normalized) WHERE removed_at IS NULL
lead_import_jobs / lead_import_rows / lead_import_mappings
```

**Campaigns and VICIdial mapping**

```text
campaigns                id, name, status, script_id, active_script_version_id,
                         rule_set_version_id, compliance_profile_id,
                         vicidial_campaign_id, closer_in_group,
                         timezone, transfer JSONB, recording JSONB,
                         retention JSONB, version
campaign_vicidial_lists  campaign_id, vicidial_list_id, active
campaign_config_versions id, campaign_id, payload JSONB, version, changed_by
verifier_groups / verifier_group_members / verifier_availability
```

**Scripts, rules and compliance**

```text
scripts                  id, name, description, language, current_version,
                         active_version, status
script_versions          id, script_id, version, status, nodes JSONB,
                         entry_node_id, rule_set_version_id, agent_aliases JSONB,
                         change_note, created_by, submitted_by, submitted_at,
                         approved_by, approved_at, rejected_reason, activated_at
                         ── immutable unless status='draft' (trigger)
script_activations       id, script_version_id, campaign_id, activated_by,
                         activated_at, deactivated_at
                         ── UNIQUE(campaign_id) WHERE deactivated_at IS NULL
script_prompt_assets     id, script_version_id, node_id, prompt_hash,
                         tts_provider, tts_model, storage_key, status
rule_sets / rule_set_versions
compliance_profiles      id, name, jurisdiction, version, status
compliance_rules         id, profile_id, rule_key, mode, rationale
                         ── mode: enforce | warn | off   §15.4
```

**Calls — partitioned monthly by `started_at`**

```text
calls                    id, reference(uniq), direction, status, disposition,
                         lead_id, campaign_id, campaign_config_version,
                         script_id, script_version_id, rule_set_version_id,
                         compliance_profile_version,
                         channel_id(uniq)          ── Asterisk UNIQUEID
                         vicidial_call_id, vicidial_lead_id, vicidial_list_id,
                         vicidial_status, vicidial_status_written_at,
                         caller_number, caller_state, did_used, caller_id_used,
                         agent_alias_used,
                         attempt_number, started_at, answered_at, ended_at,
                         duration_seconds, talk_time_seconds,
                         qualification_status, disqualification_reason,
                         transfer_status, verifier_id, qa_status, qa_score
call_events              id, call_id, external_event_id, type, payload JSONB,
                         event_ts, received_ts
                         ── UNIQUE(call_id, external_event_id)
call_node_path           id, call_id, node_id, entered_at, exited_at,
                         transition_taken
call_qualification_fields id, call_id, field, label, value, value_type,
                         captured_at, transcript_ref, confidence, required
call_compliance_events   id, call_id, rule_key, satisfied, node_id,
                         recording_offset_ms, transcript_ref, captured_at
                         ── immutable. Replaces the narrow consent table. §15.5
call_performance         call_id PK, vad_ms, stt_ms, decide_ms, llm_ttft_ms,
                         llm_total_ms, tts_ttfa_ms, tts_total_ms,
                         speech_end_to_first_audio_ms, barge_in_stop_ms,
                         total_turn_ms (p50/p95 each), turn_count,
                         stt_provider, stt_model, tts_provider, tts_model,
                         llm_provider, llm_model, gateway_node
call_disposition_history id, call_id, from_disposition, to_disposition,
                         actor_id, reason, ts
transcript_turns         id, call_id, speaker, text, tsv, start_ms, end_ms,
                         node_id, confidence, redacted
                         ── PARTITIONED, GIN(tsv)
```

**Transfers, recordings, QA, platform**

```text
transfers                id, call_id, status, initiated_at, bridged_at, ended_at,
                         verifier_id, attempts, wait_seconds, failure_reason,
                         fallback_action
transfer_attempts        id, transfer_id, attempt_number, verifier_id,
                         offered_at, responded_at, outcome
call_recordings          EXISTING — gains FK to calls(id), retention_policy_id,
                         audio_purged_at; status aligned to the frontend enum
retention_policies       id, name, audio_days, transcript_days, metadata_days,
                         effective_from, created_by
qa_scorecards / qa_scorecard_criteria / qa_reviews / qa_review_scores /
qa_tags / qa_calibrations
dispositions             key, layer, label, category, is_terminal, suppresses,
                         creates_callback, vicidial_status, campaign_id
outbox                   id, aggregate_type, aggregate_id, channel, event_type,
                         seq, payload JSONB, created_at, dispatched_at, attempts
integrations / integration_credentials / integration_failures
webhook_endpoints / webhook_deliveries
exports / alerts / service_health / notifications
agg_campaign_daily / agg_script_version_daily / agg_source_daily /
agg_bot_daily / agg_compliance_daily / agg_dashboard_counters
vicidial_sync_log        id, operation, entity_type, entity_id, request JSONB,
                         outcome, notices JSONB, response_raw, attempts,
                         succeeded_at
```

### 13.3 Database-level invariants

```sql
CREATE TRIGGER audit_log_immutable BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION raise_immutable();

CREATE TRIGGER script_version_immutable BEFORE UPDATE ON script_versions
  FOR EACH ROW WHEN (OLD.status <> 'draft') EXECUTE FUNCTION raise_immutable();

CREATE TRIGGER compliance_event_immutable
  BEFORE UPDATE OR DELETE ON call_compliance_events
  FOR EACH ROW EXECUTE FUNCTION raise_immutable();

CREATE UNIQUE INDEX one_active_script_per_campaign
  ON script_activations (campaign_id) WHERE deactivated_at IS NULL;

CREATE UNIQUE INDEX suppression_active_unique
  ON suppression_entries (phone_normalized) WHERE removed_at IS NULL;

CREATE UNIQUE INDEX call_event_dedupe ON call_events (call_id, external_event_id);
ALTER TABLE calls ADD CONSTRAINT calls_channel_unique UNIQUE (channel_id);
ALTER TABLE leads ADD CONSTRAINT leads_external_key_unique UNIQUE (external_key);
```

### 13.4 Critical indexes

```text
leads             (campaign_id, status, next_attempt_at)
leads             (phone_normalized) · (external_key) UNIQUE · (vicidial_lead_id)
calls             (campaign_id, started_at DESC) · (script_version_id, started_at)
calls             (vicidial_call_id) · (lead_id, started_at DESC)
calls             (status) WHERE status IN ('in_progress','transferring')
transcript_turns  (call_id, start_ms) · GIN(tsv)
transfers         (status, initiated_at) WHERE status LIKE 'failed%'
audit_log         (ts DESC) · (actor_id, ts DESC) · (resource_type, resource_id)
outbox            (dispatched_at) WHERE dispatched_at IS NULL
suppression       (vicidial_synced_at) WHERE vicidial_synced_at IS NULL
```

**Partitioning is not optional.** `calls`, `call_events` and `transcript_turns` are range-partitioned monthly from the first migration, with a job creating next month's partition seven days ahead and alerting on failure. Their dashboard already shows 399.6K calls in a 24-hour filter window; retrofitting partitions later is an outage.

### 13.5 Redis namespace

```text
cp:session:{userId}:sockets          cp:verifier:{userId}:availability
cp:verifier:{userId}:offer           cp:call:live:{callId}
cp:calls:live:index                  cp:script:bundle:{scriptVersionId}
cp:campaign:{id}:active_script       cp:suppression:{phone}
cp:ratelimit:{scope}:{key}           cp:seq:{channel}
cp:vicidial:ratelimit                cp:vicidial:circuit
```

The `cp:` prefix is mandatory — `TTS_REDIS_DB=0` is already in use by the pre-generated asset cache, and a control-plane flush must never evict TTS assets mid-call.

## 14. Dispositions

### 14.1 The problem with the current model

The live dashboard shows DNC, DNQ, CLBK, SALE, DAIR, RAXFER, NP, DC, NI, A, HP, RJ and INITIATED competing for a single field. They originate from four different systems and answer four different questions, so a call can only report one thing about itself, and "SALE %" is computed against a denominator that includes calls where nobody ever spoke.

### 14.2 Four layers plus flags

| Layer | Authoritative source | Values |
|---|---|---|
| **Telephony** | VICIdial `vicidial_log.status`, AMD | `initiated`, `no_answer`, `busy`, `rejected`, `disconnected`, `invalid_number`, `network_failure`, `abandoned`, `amd_machine`, `amd_uncertain`, `voicemail_dropped` |
| **Conversation** | ai-gateway | `dead_air`, `caller_hung_up_early`, `language_barrier`, `silence_no_response`, `opted_out`, `script_completed` |
| **Qualification** | rule set (version stamped) | `qualified`, `disqualified_no_part_ab`, `disqualified_age_range`, `incomplete`, `callback_requested` |
| **Verifier** | human, via VICIdial closer disposition | `verified_accepted`, `verified_rejected`, `verifier_no_contact`, `sale` |
| **Compliance flags** | QA + automatic checks — **multi-value, not a disposition** | `disclosure_missing`, `script_deviation`, `complaint`, `recording_missing`, `opt_out_not_honoured` |

Transfer state is its own field, not a disposition: `not_applicable`, `initiated`, `ringing_verifier`, `bridged`, `completed`, `failed_no_verifier`, `failed_timeout`, `failed_rejected`, `failed_technical`, `retry_scheduled`, `fallback_queued`, `callback_created`.

### 14.3 VICIdial mapping

The `dispositions` table carries a `vicidial_status` column so `update_log_entry` can write back and SmartBrains' existing reports keep reconciling. The mapping is configuration, seeded from their current codes and editable in the dashboard:

```text
TalkFlow layer+value            →  VICIdial status
qualification.qualified +
  transfer.completed            →  RAXFER   (or SALE if the verifier closes)
qualification.disqualified_*    →  DNQ
conversation.opted_out          →  DNC
qualification.callback_requested→  CLBK
conversation.dead_air           →  DAIR
telephony.no_answer             →  NP  (confirm against the campaign's codes)
telephony.amd_machine           →  A
telephony.disconnected          →  DC
conversation.caller_hung_up_early → HP
verifier.verified_rejected      →  RJ
verifier.sale                   →  SALE
```

**These mappings must be confirmed against `vicidial_statuses` and the campaign's own status list before go-live.** They are seeded as a starting point, not as fact.

### 14.4 The metrics that become computable

```text
contact rate        = conversation-layer outcomes / telephony-answered
qualification rate  = qualified / contacted
transfer success    = transfer.completed / qualified
verifier close rate = verifier.sale / transfer.completed
DQ breakdown        = by disqualification_reason
```

Each defined once, in SQL, in `docs/metrics.md`, with the PRD report it serves named in a comment.

---

# PART 4 — COMPLIANCE AS A PLATFORM FEATURE

## 15. Regulatory Requirements and How the Platform Handles Them

This section states verified federal requirements, what the current script and settings do, and how the platform is built so that compliance is a configuration with an audit trail rather than an assumption. **It is written so the decisions are visible and owned, not so the platform refuses to run.**

Every item below names a decision owner. IBTECHNOVA builds the mechanism; SmartBrains and its compliance counsel own the setting.

### 15.1 TPMO disclaimer before benefits are discussed

**Requirement.** CMS requires Third-Party Marketing Organizations — a definition that expressly includes lead-generation firms compensated as part of the chain of enrollment — to convey the TPMO disclaimer verbally during sales calls before any discussion of benefits. The CY2027 Final Rule replaced the previous "within the first minute" timing with this sequence-based standard and simplified the disclaimer language, removing the SHIP reference while retaining Medicare.gov and 1-800-MEDICARE.

**Current script.** Turn 2 — "your health and groceries benefit have not been claimed yet" — is a benefit discussion. No disclaimer node precedes it.

**Platform design.** Script nodes carry `discussesBenefits: true|false` and `complianceRole`. The validator computes reachability: if any node with `discussesBenefits: true` is reachable from the entry node without passing a node whose `complianceRole` is `tpmo_disclaimer`, the rule `tpmo_disclaimer_precedes_benefits` fires. The disclaimer text is versioned in the compliance settings group so "what exactly did we say on 3 March" is answerable for any call.

**Decision owner:** SmartBrains compliance.

### 15.2 Artificial-voice identification and opt-out

**Requirement.** The FCC's Declaratory Ruling of 8 February 2024 confirmed that the TCPA's restrictions on artificial or prerecorded voice encompass current AI technologies that generate human voices. The consequences are that such calls require prior express consent (or prior express written consent for telemarketing) before the call is made; that any artificial or prerecorded voice message must provide identification and disclosure information for the entity making the call; and that telemarketing calls must offer an opt-out mechanism. Statutory damages run $500–$1,500 per call with no cap.

A July 2024 FCC Notice of Proposed Rulemaking proposed defining "AI-generated call" and requiring specific consent plus an in-call disclosure that AI is in use. That rulemaking is a proposal, not a rule — but the disclosure node should exist now so that turning it on later is a setting, not a release.

**Current script.** The bot introduces itself with a rotating human first name. There is no entity identification and no AI disclosure.

**Platform design.** Three separable rules in the compliance profile — `entity_identification`, `ai_disclosure`, `opt_out_mechanism` — each `enforce`, `warn` or `off`. `n_opt_out` with a global keyword transition is in the bundle regardless of profile, because revocation must be honoured however it is expressed (§15.4). The `agent_alias` is recorded on every call in `calls.agent_alias_used`, so which persona spoke on which call is answerable.

**Decision owner:** SmartBrains compliance, with counsel.

### 15.3 Prior consent, which is state-dependent

**Requirement.** Consent must exist **before the platform dials**, and it is not uniform across the country. The Fifth Circuit's decision in *Bradford v. Sovereign Pest Control of Texas* (25 February 2026) held that the TCPA's text requires only prior express consent rather than the heightened prior express written consent for artificial-voice calls — applying the *Loper Bright* framework and concluding the FCC exceeded its authority in 2012. That holding binds Texas, Louisiana and Mississippi. In the other 47 states federal courts continue to apply the FCC's written-consent rule, and Florida separately requires AI-specific written consent. An existing business relationship exempts a caller from the National Do Not Call Registry for manual calls but not from the artificial-voice consent requirement.

**Current state.** The `leads` table has `source` and `source_batch_id` and nothing else. There is no record of what consent was obtained, when, how, or under what disclosure text.

**Platform design.** `lead_consent_artifacts` (§13.2) records artifact type, capture timestamp, method, origin URL, origin IP, disclosure text version, vendor and evidence reference. The lead eligibility check — which runs **before** a lead is pushed to the VICIdial hopper — evaluates the consent artefact against the rule for the lead's state. A lead with no artefact, or an artefact insufficient for its state, is held in `blocked_no_consent` and never reaches the dialer.

Note the dependency created by §12.2: the production script no longer captures ZIP, so **state must come from the VICIdial lead record or area-code lookup**. If lead vendors supply neither, the consent rule cannot be evaluated correctly. That is a lead-intake requirement, not a platform one.

**Decision owner:** SmartBrains, with its lead vendors. The platform cannot manufacture consent that was never obtained.

### 15.4 Revocation

**Requirement.** Since 11 April 2025, consumers may revoke consent by any reasonable method; an automated interactive-voice or key-press opt-out mechanism on a call is a per se reasonable means; all reasonable opt-out requests must be honoured within a reasonable time not exceeding ten business days; callers may not designate an exclusive means of revocation; and revocation of consent for one type of robocall constitutes revocation for all robocalls from that caller.

**Platform design.** Four consequences, all built in:

1. The bot's synchronous opt-out write (G6) is **better than required** — honoured in seconds rather than ten business days.
2. Suppression is **global to the caller**, not campaign-scoped, because revocation is caller-wide. `add_dnc_phone` is called for `SYSTEM_INTERNAL` **and** each active campaign.
3. Because no exclusive means may be designated, suppression accepts intake from multiple channels — in-call keyword, in-call key-press, inbound call, web form — plus a free-text "reasonable manner" intake with a review queue.
4. An SLA clock runs on every intake with an alert before the ten-business-day limit, and `agg_compliance_daily` reports the distribution of honour times.

### 15.5 Recording and retention

**Requirement.** CMS expects TPMOs to capture all marketing and sales calls in their entirety, stored in a HIPAA-compliant manner. The retention floor has been ten years under 42 CFR §422.2274 and §423.2274. The CY2027 Final Rule reduced the minimum for marketing and sales call recordings from ten years to six, effective for recordings made on or after 1 October 2026, with full audio required for the first three years and either audio or a complete transcript acceptable for years four through six. Enrollment records remain at ten years. The six-year figure is a floor, not a ceiling — an FMO or carrier may impose stricter standards that override the CMS minimum.

**Stated requirement for this build.** Call recordings retained **six months**; call dispositions and metadata retained indefinitely.

**Observation, recorded once.** Six months sits below the CMS floor if SmartBrains is the TPMO of record for these calls. Whether that obligation lands on SmartBrains, on the carrier, or on a downstream FMO is a question with a definite answer that nobody on this project has yet confirmed. **It is the single highest-value question in this document and should be answered before the first production call.**

**Platform design — which supports either answer.** Retention is a per-record-class policy, versioned, stamped on each recording at capture:

```text
retention_policies
  audio_days        default 180   ← the stated requirement
  transcript_days   default 2555  ← ~7 years; cheap, and the CY2027 rule
                                     accepts a complete transcript in place of
                                     audio for years 4-6
  metadata_days     NULL          ← indefinite: disposition, script version,
                                     compliance events, QA, audit
```

When audio is purged, `call_recordings.status` becomes `purged`, `audio_purged_at` is set, and **the metadata row is retained** — a purged recording still proves the call happened, which script version ran, what was captured and how it ended. Purge is audited and requires `recording.purge`. Changing a retention policy is a versioned, audited act.

Retaining transcripts far longer than audio is deliberate and cheap: it is the one configuration that keeps a six-month audio window and a multi-year evidentiary record simultaneously viable.

### 15.6 The compliance profile mechanism

Rather than hardcoding any of the above, each campaign references a **versioned compliance profile** — a named set of rules, each set to `enforce`, `warn` or `off`, each with a recorded rationale.

```text
compliance_profiles: "US Medicare TPMO — Default"   version 1
  tpmo_disclaimer_precedes_benefits   enforce
  entity_identification               enforce
  ai_disclosure                       warn
  opt_out_mechanism                   enforce
  recording_notice                    enforce
  consent_artifact_required           enforce
  consent_state_rules                 enforce
```

How the three modes behave:

| Mode | Script validation | Campaign start | Live call | Reporting |
|---|---|---|---|---|
| `enforce` | Submit is refused with node-level errors | Start is refused | Violation raises an alert | Counted as violations |
| `warn` | Submit succeeds with warnings shown to the approver | Start succeeds with a confirmation step | Violation is flagged for QA | Counted as flags |
| `off` | Not evaluated | Not evaluated | Not evaluated | Counted as "not evaluated" |

**Setting any rule to `warn` or `off` requires Master Admin, a typed confirmation, and a mandatory written rationale, and writes an audit entry naming the actor.** The profile version in force is stamped on every call, so the compliance posture of any historical call is reconstructable.

This is the design a professional platform uses. It does not decide the law, it does not silently permit gaps, and it makes every deviation attributable to a named person on a recorded date. The alternative designs — hardcoding the rules so the client's script cannot run, or omitting them so nobody notices — are both worse.

---

# PART 5 — ROADMAP

## 16. Why the Order Is What It Is

Three sequencing principles:

1. **Persist calls before making scripts dynamic.** Call persistence works against the existing hardcoded flow — it needs event publishing, not an engine rewrite. It unblocks four frontend screens weeks earlier and produces the corpus of real calls that script simulation is validated against. Building the script engine first means building it blind.
2. **The VICIdial adapter is foundational, not an integration afterthought.** Leads cannot be dialled, recordings cannot be found, and dispositions cannot be written without it. It lands in M2.
3. **Gateway changes are scheduled deliverables with owners**, not a line in an appendix. They are the dependency that a plan most easily leaves implicit and most expensively discovers late.

## 17. Milestones

```text
M0  Remediation + scaffold        ──┐
M1  Contract + data model           │
M2  Auth/RBAC + VICIdial adapter    │  critical path
M3  Call persistence + gateway      │
M4  Leads/suppression/campaigns     │
M5  Scripts + rules + compliance    │
M6  Script execution in gateway     │
M7  Realtime + transfer + verifier ─┘
M8  Recordings + retention         ── parallel from M3
M9  QA + analytics + exports + ops ── parallel from M3
M10 Hardening + pilot readiness
```

### M0 — Remediation and Scaffold

Rotate the exposed Postgres credential and remove it from `docker-compose.yml`. Remove the runtime `pip install`. Close public access to the gateway's `/internal/*`. Clean the repository root. Resolve the phase-numbering conflict. Scaffold `packages/{contracts,db,core,storage,vicidial}` and `services/{app-api,realtime-api,workers}`. CI skeleton including the dashboard job.

**Also in M0, because it has the longest lead time:** open the Asterisk 18 EOL question with the VICIdial project and the telephony admin, and confirm the deployed `non_agent_api.php` build date and the three API account permissions.

*Exit:* `make setup && make up && make check` passes on a clean clone; no credential in version control; VICIdial API accounts provisioned and a `version` call succeeds from `app-api`.

### M1 — Contract and Data Model

`packages/contracts` complete, with the gateway's `ConversationState`, `QualificationStatus` and `FieldName` reconciled in and imported back (G10). Four-layer disposition taxonomy seeded with the VICIdial mapping. Full schema from §13 including `lead_consent_artifacts`, `compliance_profiles`, `call_compliance_events`, `retention_policies`, `vicidial_sync_log`, and the VICIdial mapping columns. Monthly partitioning and the partition job. All triggers and partial indexes. First migration off `41960d8b814f`; the recording-worker migration directory retired into it. `external_key` generation (≤20 chars, §8.2). `make contract` producing `openapi.json`, dashboard types and MSW mocks.

**ADR required:** is `calls.id` the gateway's existing call id, or is `channel_id` the join key? This determines whether `call_recordings` needs a backfill.

*Exit:* migration applies cleanly to a copy of the live database; every invariant has a passing violation test; frontend generates mocks from the committed spec.

### M2 — Auth, RBAC, Audit, and the VICIdial Adapter

`app-api` with all cross-cutting machinery. Login, refresh with rotation and reuse detection, `/auth/me` with resolved permissions. Permission registry including the keys the earlier handoff omitted — `verifier.view_all_history`, `qa.calibrate`, `audit.export`, `transcript.view`. Users, audit with the append-only trigger, settings, health.

**`packages/vicidial` complete** — three credential profiles, response classifier handling SUCCESS/NOTICE/ERROR line by line, rate limiter, circuit breaker, `vicidial_sync_log`, and the recorded-fixture test suite captured from the real API.

*Exit:* a route without a permission dependency fails CI; an audit row rolls back with its transaction; the adapter round-trips `campaigns_list`, `add_lead`, `add_dnc_phone` and `update_log_entry` against the staging dialer.

### M3 — Call Persistence and Gateway Ingest

**The milestone that turns the bot into a product.**

Backend: call tables, services and repositories; the `call-ingest` Kafka consumer with `(call_id, external_event_id)` dedupe and out-of-order reconciliation by event timestamp; call API including live, transcript, timeline, performance and script-path; live snapshot in Redis under `cp:`; disposition service with the four-layer mapping and writeback to VICIdial via `update_log_entry`.

Gateway: **G1** publish lifecycle events; **G2** buffer and replay; **G3** identity resolution at session open including the dialplan change and the `callid_info` fallback; **G5** compliance-event offsets; **G8** `node_id` on transcript turns; **G9** the frozen latency fields.

*Exit:* a call from `run_test_client.py` lands in Postgres with transcript, fields and disposition; killing `app-api` mid-call loses nothing; the disposition appears in `vicidial_log`; ingest adds no measurable latency to the conversational turn.

### M4 — Leads, Suppression, Campaigns

Leads with server-side filtering; `lead_consent_artifacts` and the state-aware eligibility check; the five-stage import pipeline, streamed and resumable with an idempotent commit; suppression with dual-write to VICIdial (§8.4), multi-channel intake and the ten-business-day SLA clock; campaigns with VICIdial campaign and list mapping, versioned config, optimistic locking and the start guard returning every failure at once. Lead push to the hopper via `add_lead` and `hopper_bulk_insert`. Gateway **G6** — synchronous opt-out.

*Exit:* a 100k-row import commits idempotently; a suppressed number is absent from the VICIdial hopper and present on its DNC list within one worker pass; a lead without a valid consent artefact for its state is never pushed; the dnc-reconciler reports zero divergence.

### M5 — Scripts, Rule Sets, Compliance Profiles

Scripts and versions with DB-level immutability; graph validation including the benefit-reachability rule; approval with separation of duties; activation with the single-active partial index; structural diff; simulation accepting per-node events so `no_response` and `invalid` paths are testable; rule sets fully versioned with approval; compliance profiles with the three modes and the audited override; bundle compilation to Redis with REST fallback; `script_prompt_assets` and the TTS generation pipeline.

*Exit:* the production script of §12.3 is authored in the dashboard, validated, approved and activated; an approved version cannot be mutated by direct SQL; concurrent activation yields exactly one active; setting a compliance rule to `warn` requires a rationale and writes an audit row.

### M6 — Script Execution in the Gateway

**G4.** `app/realtime/qualification/` moves from the hardcoded `ConversationState` enum to a bundle-driven graph walk. The existing extractors, validators, clarification counting, LLM fallback, response planner, speech normalization, TTS and barge-in are reused unchanged; only sequencing and prompt source become data. Backend re-evaluates qualification at close and alerts on disagreement.

*Risk control:* **build the bundle that exactly reproduces today's flow first and prove parity against M3's persisted calls before authoring anything new.** The existing `/internal/qualification/test` harness is the regression suite.

### M7 — Realtime, Transfer, Verifier

Transactional outbox with the dispatcher fanning out to Kafka and Redis **in parallel, not serially**; `seq` assigned from a Postgres sequence at outbox-write time, not Redis `INCR`; `realtime-api` with permission- and scope-checked subscriptions, heartbeat, backpressure and partial coalescing; transfer orchestration using VICIdial in-group availability (`agent_ingroup_availability`) plus TalkFlow's own offer reservation; transfer watchdog every five seconds; verifier service returning full caller context in one payload. Gateway **G7**.

*Exit:* a live call appears within 250 ms; two verifiers accepting one offer produces exactly one winner; every terminal transfer failure produces a durable queue row and an alert.

### M8 — Recordings and Retention *(parallel from M3)*

Recording library and secure serving — 5-minute presigned playback, single-use download token, both audited, VICIdial's HTTP recording location never exposed to the browser; status enum reconciliation between the worker and the frontend; `recording-reconciler` closing the orphan gap; `retention_policies` with the 180-day audio window, long transcript retention, indefinite metadata, and the audited purge that preserves the metadata row.

### M9 — QA, Analytics, Exports, Operations *(parallel from M3)*

Risk-weighted daily QA sampling; versioned scorecards with auto-fail; six `agg_*` rollups on a 60-second incremental worker; the five PRD reports; asynchronous exports with scope-inherited PII omission; health probes including a VICIdial API card; alerts; integrations framework; search with audited phone lookups; notifications.

**No analytics endpoint touches raw `calls`.** Every metric has one SQL definition in `docs/metrics.md`. The dashboard's hardcoded arrays are each traced to an `agg_*` column before those components are wired.

### M10 — Hardening and Pilot Readiness

Load test at ten times pilot volume; security review; database restore drill; runbooks for transfer storm, gateway down, VICIdial API down, dialer down, disk full and restore; **raise `VAD_POOL_SIZE` and `ASR_WORKERS` and re-benchmark to the pilot's concurrent-call target** — the current `VAD_POOL_SIZE=4` and `ASR_WORKERS=1` will not carry twenty concurrent calls; set concurrency limits to measured capacity.

## 18. Dependencies

```text
M0 ─► M1 ─► M2 ─┬─► M3 ─► M4 ─► M5 ─► M6 ─► M7 ─► M10
                │     │
                │     ├─► M8   (parallel)
                │     └─► M9   (parallel)
                └────────────────────────────────┘
```

**Critical path:** M0 → M1 → M2 → M3 → M4 → M5 → M6 → M7.

**The three riskiest milestones, in order:** M6 (rewriting a working engine), M3 (touching the realtime service under a latency constraint), M2 (the adapter's correctness depends on an external system nobody on the team controls).

**Longest-lead external dependencies, all to be opened in M0:** VICIdial API account provisioning; confirmation of the dialplan channel variables for §6.3; a staging extension for integration testing; the Asterisk 18 EOL migration path; and the TPMO-of-record question in §15.5.

---

# PART 6 — READINESS, DECISIONS, GOVERNANCE

## 19. Production Readiness Gate

```text
CORRECTNESS
□ An approved script version cannot be mutated — proven by direct SQL UPDATE
□ Two concurrent activations yield exactly one active version
□ A double-committed import creates no duplicate leads
□ A suppressed number is absent from the VICIdial hopper AND present on its DNC list
□ A lead with no valid consent artefact for its state is never pushed to the dialer
□ A compliance rule set to warn/off has a recorded rationale and a named actor
□ A disposition override preserves the original in history
□ A compliance event cannot be updated after call close
□ Every call carries script version, rule set version and compliance profile version
□ Gateway and control-plane qualification agree, or the disagreement alerts
□ Two verifiers cannot accept the same transfer offer

VICIDIAL INTEGRATION
□ Every adapter function has a recorded-response fixture test
□ Every documented ERROR and NOTICE string is parsed, not just SUCCESS
□ A partial add_lead (added but not hoppered, outside local time) is detected and surfaced
□ The dnc-reconciler reports zero divergence over a 24-hour window
□ The disposition-reconciler re-writes divergences and alerts on repeated failure
□ The recording-reconciler recovers an orphaned recording within 5 minutes
□ Circuit breaker opens on VICIdial failure instead of hammering the dialer
□ No VICIdial call originates from a request handler
□ Three separate API accounts, each with minimum flags

RELIABILITY
□ A gateway restart mid-call loses no events (buffer + replay verified)
□ A Kafka restart at call end loses no recording
□ A Redis flush degrades display only — no business data lost, no TTS cache eviction
□ The transfer watchdog recovers a stuck transfer within one sweep
□ The outbox replays cleanly after a dispatcher outage
□ Database restore from backup verified end to end on real data
□ Next month's partitions exist seven days ahead

SECURITY
□ No secret returned by any endpoint, including to Master Admin
□ The exposed Postgres credential is rotated and removed from history
□ Gateway /internal/* unreachable from outside the private network
□ Recording URLs expire; download tokens are single-use; VICIdial's HTTP
  recording location is never sent to the browser
□ PII masked for every role without pii.view_full, via one serializer
□ Every route carries an explicit permission dependency (CI-enforced)
□ pip-audit and gitleaks clean

PERFORMANCE
□ Read p95 < 200 ms · write p95 < 400 ms · analytics p95 < 300 ms
□ Kafka call-ingest lag < 2 s · WS fanout lag p95 < 250 ms
□ Rule evaluation p99 < 20 ms
□ No analytics endpoint touches raw calls
□ Control-plane ingest adds no measurable latency to the conversational turn
□ Gateway sustains the pilot's concurrent-call target at measured settings

PROCESS
□ openapi.json drift gate green; CONTRACT_VERSION current
□ Coverage ≥ 85% overall, 100% on policies
□ Dashboard lint/test/build job green
□ Runbooks written and rehearsed
□ Migrations tested against restored production data
```

## 20. Decisions Required

Each blocks a milestone. Each becomes an ADR in the existing `docs/adr/` series.

| # | Decision | Blocks | Owner | Recommendation |
|---|---|---|---|---|
| 1 | **Who is the TPMO of record for these calls — SmartBrains, the carrier, or a downstream FMO?** | M8 retention, §15.5 | SmartBrains + counsel | Answer before the first production call. It determines whether 180-day audio retention is defensible. |
| 2 | Is `calls.id` the gateway's existing call id, or is `channel_id` the join key? | M1 | Backend lead | `channel_id` (Asterisk UNIQUEID) as the join key; `calls.id` stays an independent UUID v7 |
| 3 | Exact VICIdial dialplan channel variables for campaign and lead identity | M3, §6.3 | Telephony admin | Confirm in week one; the whole script feature depends on it |
| 4 | Confirm deployed `non_agent_api.php` build date and JSON support | M2 | Telephony admin | Needs ≥ 260519 for JSON; ≥ 260822 for `agent_ingroup_availability` |
| 5 | Add indexes on `phone_number` in `vicidial_log` and `vicidial_closer_log`? | M3 | VICIdial DBA | Yes if `phone_number_log` is used; the API docs explicitly warn it is unindexed |
| 6 | Asterisk 18 EOL migration path | M10 | Telephony admin + VICIdial project | Do not upgrade Asterisk independently of VICIdial |
| 7 | Compliance profile: which rules `enforce` vs `warn` at launch | M5 | SmartBrains compliance | Default profile is all `enforce`; every relaxation is audited |
| 8 | Split Part A/B into two questions and capture age as a number? | M5 | SmartBrains ops | Recommended — restores DQ diagnostics for ~4 seconds of call time |
| 9 | Do lead vendors supply state or ZIP, and consent artefacts? | M4, §15.3 | SmartBrains + vendors | Without state, the consent rule cannot be evaluated |
| 10 | Which CRM, and its API shape | M9 | SmartBrains | Adapter interface now, implementation when named |
| 11 | `/api/v1` prefix — the frontend spec's catalogue is unprefixed | M1 | Backend + frontend leads | Adopt the prefix and amend the frontend specification |

## 21. Frozen Latency Fields

Agree these names **before** RunPod benchmarking closes, so benchmark numbers and production telemetry are comparable without a schema change.

```text
vad_ms                         stt_provider
stt_ms                         stt_model
decide_ms                      tts_provider
llm_ttft_ms                    tts_model
llm_total_ms                   llm_provider
tts_ttfa_ms                    llm_model
tts_total_ms                   gateway_node
speech_end_to_first_audio_ms   gpu_identifier
barge_in_stop_ms
total_turn_ms
```

Two facts from the repository's own benchmark record that bear on interpretation: the Phase 9 end-to-end figure of roughly 450–600 ms time-to-first-audio was measured **with DummyTTS**, and Chatterbox measured 6.4 s time-to-first-audio at one word rising to 20.4 s at twenty-six words, with RTF 2.8–4.7 and peak VRAM 3,906 MB. The benchmark document itself states these come from small-scale integration samples rather than load tests. Any latency commitment made to SmartBrains should be based on the winning model measured under load, not on these figures.

## 22. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| **Asterisk 18 is EOL** — unpatched SIP stack on Medicare calls | Security exposure with no vendor remedy | M0 opens the migration path with the VICIdial project; treat as a standing risk with a named owner and review date |
| **VICIdial API is a shared fragile resource** — PHP against MySQL on the dialer host | Control-plane traffic degrades live dialing | Client-side rate limit, circuit breaker, bulk functions, worker-only access, `source` marker in VICIdial's own log |
| **Script identity at session open (§6.3) is unconfirmed** | The script feature cannot function | First-week task for the telephony admin; `callid_info` fallback; hard refusal rather than guessing |
| **M6 rewrites a working engine** | Regression in the one component that currently works well | Parity bundle first, proven against M3's persisted calls, with the existing test harness as the regression suite |
| **Consent artefacts may not exist** for current lead supply | The eligibility gate blocks everything, or is switched off | §15.3 decision with vendors in M0, not M4 |
| **Retention below the CMS floor** if SmartBrains is the TPMO | Regulatory exposure; audio unavailable for audit | Decision 1; long transcript retention as partial mitigation |
| **Merged Part A/B and range-based age** | DQ rate movements have no diagnostic path | Decision 8; report `disqualification_reason` distribution from day one |
| **Dashboard is JavaScript with no CI** | Contract drift invisible; regressions ship silently | Generated types + MSW mocks; dashboard CI job in M0 |
| **Gateway concurrency ceiling** — `VAD_POOL_SIZE=4`, `ASR_WORKERS=1` | Pilot target exceeds measured capacity | M10 re-benchmark; concurrency limits set to measured, not aspirational, values |
| **Unbounded call and transcript growth** | Query and vacuum degradation within months | Monthly partitions from the first migration |

## 23. Working Practice

**Branching.** Trunk-based; short-lived `feat/<module>-<summary>` branches; feature flags for anything spanning more than a few days.

**Pull requests.** One module or one coherent change. Every PR carries tests at the layers §11.1 requires.

```text
PR CHECKLIST
□ No business logic in the router (R2)
□ No cross-module repository access (R3)
□ Permission dependency present and correct (R4)
□ Repository queries take scope (R5)
□ Audit written inside the business transaction
□ Errors use registered codes, not free-form strings
□ Idempotency or version guard on state-changing writes (R9)
□ Any VICIdial write is idempotent and reconciled (R11)
□ Any suppression write is dual-write (R12)
□ Policies are pure and fully branch-tested
□ Invariants tested against the database, not just the service
□ No secret reachable from a response model (R7)
□ OpenAPI regenerated if the contract changed (R10)
□ Migration is expand/contract; index creation CONCURRENTLY
```

**ADRs.** The repository has an existing series (003–026, with gaps). Continue it. Every decision in §20 becomes an ADR when settled.

**Per-module definition of done:** endpoints implemented and permission-gated; policies branch-tested; invariants tested at the database; contract regenerated; audit wired; error codes registered; seed data extended; runbook entry if the module can page someone.

## 24. What Good Looks Like

The measure of whether this was built well is not that the features exist. It is that these are true six months in:

- A new developer ships a working module in their first week, because every module has the same seven files and the same four test files.
- A backend change that would break the dashboard fails CI before anyone sees it at runtime.
- When a call goes wrong, one `traceId` reconstructs everything that happened to it — including every VICIdial call the control plane made on its behalf.
- When compliance asks what the bot said on a call in March, the answer is a script version id, a compliance profile version and a recording offset, retrieved in seconds.
- When a number is suppressed, it is gone from both systems within one worker pass, and a reconciler proves it stayed gone.
- A model swap after RunPod benchmarking is a configuration change, not a code change.

---

# APPENDIX A — VICIdial Functions Used

| Function | Profile | Purpose | Milestone |
|---|---|---|---|
| `version` | readonly | Confirm API build date and JSON support | M0 |
| `campaigns_list` | readonly | Campaign inventory, dial configuration | M2 |
| `hopper_list` | readonly | Hopper depth and composition | M4 |
| `in_group_status` | readonly | Closer in-group real-time state | M7 |
| `agent_ingroup_availability` | readonly | Verifier availability counts (requires build ≥ 260822) | M7 |
| `agent_status` | readonly | Per-verifier state and sub-status | M7 |
| `callid_info` | readonly | Call detail; the §6.3 identity fallback | M3 |
| `recording_lookup` | readonly | Locate the recording for a call | M8 |
| `phone_number_log` | readonly | Call history by number (needs indexes — decision 5) | M9 |
| `lead_all_info` / `lead_search` / `lead_field_info` | readonly | Lead reconciliation | M4 |
| `add_lead` | leadwrite | Push a lead with DNC, duplicate and hopper options | M4 |
| `update_lead` | leadwrite | Status, callback, hopper add/remove | M4 |
| `batch_update_lead` | leadwrite | Bulk status change (no per-lead admin log — audit in TalkFlow) | M4 |
| `hopper_bulk_insert` | leadwrite | Up to 1,000 lead IDs per call | M4 |
| `add_dnc_phone` / `delete_dnc_phone` | dncwrite | Suppression dual-write | M4 |
| `update_log_entry` | dncwrite | Disposition writeback to `vicidial_log` / `vicidial_closer_log` | M3 |

# APPENDIX B — New Environment Variables

```text
APP_API_PORT                 REALTIME_API_PORT
JWT_ACCESS_SECRET            JWT_ACCESS_TTL            REFRESH_TTL_DAYS
ENCRYPTION_KEY_ID            KMS_ENDPOINT
STORAGE_PROVIDER             STORAGE_ENDPOINT          STORAGE_BUCKET_*

VICIDIAL_BASE_URL            VICIDIAL_SOURCE_TAG
VICIDIAL_RO_USER             VICIDIAL_RO_PASS
VICIDIAL_LEAD_USER           VICIDIAL_LEAD_PASS
VICIDIAL_DNC_USER            VICIDIAL_DNC_PASS
VICIDIAL_RATE_LIMIT_RPS      VICIDIAL_TIMEOUT_S
VICIDIAL_CIRCUIT_THRESHOLD   VICIDIAL_OUTPUT_STAGE      (json|pipe)

GATEWAY_SERVICE_TOKEN        GATEWAY_IP_ALLOWLIST
CONTROL_PLANE_REDIS_DB       ← keep clear of TTS_REDIS_DB=0
CRM_BASE_URL                 CRM_API_KEY
OTEL_EXPORTER_OTLP_ENDPOINT
```

Existing variables (`DATABASE_URL`, `REDIS_URL`, `KAFKA_BOOTSTRAP_SERVERS`, the `RECORDING_*` group) are reused unchanged. Production values come from the secret manager at boot; `.env` files exist only for local development and contain no real credentials.

# APPENDIX C — First Two Weeks

```text
WEEK 1 — unblock the long-lead items
 1. Rotate the Postgres credential; remove it from the public repository.
 2. Request three VICIdial API accounts with minimum flags; confirm the
    deployed non_agent_api.php build date.
 3. With the telephony admin, confirm the dialplan channel variables that
    carry campaign and lead identity into AudioSocket (§6.3).
 4. Request a staging extension and a test list on the dialer.
 5. Ask SmartBrains: who is the TPMO of record? (§15.5, decision 1)
 6. Ask the lead vendors: do you supply state/ZIP and a consent artefact?
 7. Open the Asterisk 18 EOL question with the VICIdial project.
 8. Scaffold the packages and services; stand up CI including the dashboard job.

WEEK 2 — make the contract real
 9. packages/contracts: reconcile every enum with the gateway's.
10. Write the first migration off 41960d8b814f; retire the recording-worker
    migration directory into it.
11. Capture VICIdial API fixtures from the staging dialer — every function in
    Appendix A, every ERROR and NOTICE string you can provoke.
12. Generate openapi.json; wire the drift gate; generate the dashboard types
    and MSW handlers.
13. Agree the frozen latency field names with whoever runs the RunPod
    benchmarks (§21).
```

---

**End of blueprint.**

*Verified against `ASK-Baloch/TalkFlow` @ `main`, Asterisk 18.26.4-vici, VICIdial 2.14, VICIdial Non-Agent API rev 260907-1808, and the federal rules cited in Part 4. Supersedes all previous backend documents in this series. Changes to Parts 1–4 require agreement from the backend and frontend leads; changes to Part 4 additionally require SmartBrains compliance.*
