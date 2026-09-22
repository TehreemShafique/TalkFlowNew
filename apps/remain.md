# Remaining Backend & Telephony Integration Modules

Status:
- **`app/modules/campaigns/` is implemented** (migrations `8e9f0a1b2c3d`, `e7f8a9b0c1d2`, ORM `Campaign` + `CampaignVicidialList`).
- **`app/modules/calls/` is implemented** (migration `9f0a1b2c3d4e`, ORM models, permissions, router).
- **`app/modules/scripts/`, `app/modules/rule_sets/`, `app/modules/compliance/` are implemented (Phase 4 — Steps 20-25)**:
  - Migration `c4d5e6f7a8b9` added `rule_sets`, `rule_set_versions`, `compliance_profiles`, `compliance_rules`, version immutability trigger `trg_prevent_approved_script_version_mutation`, single active script version index `uq_script_activations_campaign_active`, and campaign FKs.
  - Pure state machine governance and graph structural validation `validate_graph(nodes, entry_id, profile)` with `GraphError` codes (`DANGLING_TRANSITION`, `UNREACHABLE`, `DEAD_END`, `MISSING_ENTRY`, `BENEFITS_BEFORE_DISCLAIMER`).
  - Event-driven graph simulation (`POST /api/v1/scripts/{id}/versions/{v}/simulate` accepting `{ "events": [...] }`).
  - Constrained expression language `evaluate(rule_set, fields)` with operators (`==`, `!=`, `<`, `<=`, `>`, `>=`, `in`).
  - Compliance mode governance (`enforce | warn | off`) requiring `MASTER_ADMIN`, confirmation string `CONFIRM_OVERRIDE`, rationale, and audit logging.
  - Bundle compilation & publishing to Redis on activation (`cp:script:bundle:{scriptVersionId}` and `cp:campaign:{id}:active_script`).
- **`app/modules/leads/`, `app/modules/suppression/`, `app/packages/telephony/` are implemented (Phase 5 — Steps 27-31)**:
  - Migration `e7f8a9b0c1d2` added `external_key` (VARCHAR(20) UNIQUE), `lead_import_rows` staging table, suppression channels/SLA fields/`vicidial_synced_at`, and campaign `vicidial_campaign_id`/`campaign_vicidial_lists`/`caller_ids`/`verifier_group_id`.
  - **Step 27 Leads**: E.164 phone normalization, base32 `external_key` (<=20 chars) generation, HTTP 422 system-field rejection for `attempts`/`last_attempt_at`/`next_attempt_at`, and `POST /api/v1/leads/bulk-assign`.
  - **Step 28 Import Pipeline**: 5-stage resumable wizard (upload, parse/infer, preview classification, 1,000-row batch commit with idempotency key, and skipped-row CSV error report download).
  - **Step 29 Suppression Register**: Soft removal (`removed_at`, `removed_by`), `MASTER_ADMIN` role gate, Redis pre-dial cache (`cp:suppression:{phone}`) with DB fallback.
  - **Step 30 Campaign Start Guard**: Evaluates active script, rule set, compliance profile, verifier group, list mapping, and caller IDs, returning all missing problem codes at once.
  - **Step 31 Telephony Adapter Seam**: `TelephonyAdapter` protocol, `ManualDialAdapter` implementation logging operations and returning `ExternalLeadRef(system="manual", external_id=lead.external_key)`, and `build_adapter` factory.
- **`app/core/outbox.py`, `app/modules/realtime/`, `app/modules/transfers/`, `app/modules/verifier/` are implemented (Phase 6 — Steps 32-36)**:
  - Migration `g2h3i4j5k6l7` added PostgreSQL channel sequences (`outbox_seq_*`), partial index `outbox_pending`, and `transfers` table.
  - **Step 32 Outbox & Monotonic Dispatcher**: Transactional outbox with DB sequence ordering and parallel `asyncio.gather` Kafka and Redis (`cp:channel:*`) fanout.
  - **Step 33 Realtime WebSocket API**: 5s auth gate, subscriber RBAC permission checks, 30s ping/pong heartbeat, dynamic PII masking, and 100-frame queue cap.
  - **Step 34 Live Transfers Engine**: Atomic Redis `SET NX` offer reservation (`cp:verifier:{vid}:offer`), stuck transfer watchdog, retry, and callback creation.
  - **Step 35 Verifier Workspace**: Single-payload accept response (`VerifierAcceptContextDTO`) returning prospect details, qualification status & fields, consent evidence, recording ref, and lead history in ONE response under 300ms.
  - **Step 36 Presence Expiry**: Automatic presence deletion upon socket disconnect (`cp:verifier:{id}:availability`).
- **`app/modules/recordings/`, `workers/`, `app/modules/analytics/` are implemented (Phase 7 — Steps 37-40)**:
  - **Step 37 Recording Serving & Reconciler**: 5-min presigned playback URLs (`recording.played`), single-use download tokens (`recording.downloaded`), status enum alignment (`pending → waiting_for_source → fetching → validating → storing → ready | failed | purged`), and 5-min `recording-reconciler` worker.
  - **Step 38 Retention Policies & Audio Purger**: `retention_policies` schema (180d audio, 2555d transcript, indefinite metadata) and daily retention purger worker (`workers/retention_purger.py`) deleting audio objects while preserving metadata rows with `recording.purged` audit logs.
  - **Step 39 60s Watermark Rollups Engine**: Migration `h3i4j5k6l7m8` added 6 `agg_*` tables. 60-second watermark incremental `rollup_worker` (`workers/rollup_worker.py`). Strict CI query isolation (`test_no_analytics_query_hits_raw_calls()`) ensuring `app/modules/analytics` queries fold exclusively over `agg_*` tables.
  - **Step 40 Dashboard Analytics Wiring**: `AnalyticsView.jsx` wired via `apiFetch` to server exports and analytics rollups.

---

## AI Gateway Deferred Integration (Step 26)

The services folder (`services/ai-gateway`) is preserved untouched per instructions. When `services/ai-gateway` is updated:

1. **Gateway Bundle Walk Execution**: Replace hardcoded `ConversationState` walk in `services/ai-gateway/app/realtime/qualification/engine.py` with dynamic graph walk driven by compiled JSON bundles from Redis (`cp:campaign:{id}:active_script` -> `cp:script:bundle:{versionId}`).
2. **Preserve Unchanged**: Extractors, validators, clarification counting, LLM fallback, speech normalization, TTS, and barge-in.
3. **Verification**: Run existing test suite (`cd services/ai-gateway && uv run pytest tests/ -q`) and text harness (`curl -s -X POST localhost:8000/internal/qualification/test -d '{"utterances":["yes","yeah I am 71"]}'`).

---

## Dialer Sync Deferred Integration (Phase 8)

The services/dialer integration is preserved untouched. When Phase 8 VICIdial dialer integration lands:

1. **Campaign List Sync**: Sync campaign lists and caller IDs with VICIdial non-agent API using stored `vicidial_campaign_id` and list IDs.
2. **DNC Register Sync**: Read `vicidial_synced_at` from `suppression_entries` table and stream additions/removals to VICIdial DNC lists via the outbox event queue (`talkflow.vicidial.sync.v1`).
