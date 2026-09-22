# Fake-Gateway Soft & Gateway Integration Dependencies

The **STEP 16 fake gateway simulator** (`scripts/fake_gateway.py`) stems the AI Voice Bot's wire contract so `apps/backend` can run and test the full call pipeline without Asterisk or the AI-Gateway.

## 1. Phase 4 Completed Modules (Scripts / Rule Sets / Compliance)
- `scripts`, `rule_sets`, and `compliance` control-plane backend services are fully built and tested (Phase 4, Steps 20-25).
- On activation, compiled script bundles are published to Redis:
  - `cp:script:bundle:{scriptVersionId}`
  - `cp:campaign:{id}:active_script`

## 2. Phase 5 Completed Modules (Leads / Suppression / Campaigns / Telephony)
- **Step 27 Leads**: E.164 phone normalization, base32 `external_key` (<=20 chars) generation, HTTP 422 system-field rejection for `attempts`/`last_attempt_at`/`next_attempt_at`, and `POST /api/v1/leads/bulk-assign`.
- **Step 28 Import Pipeline**: 5-stage resumable wizard (upload, parse/infer, preview classification, 1,000-row batch commit with idempotency key, and skipped-row CSV error report download).
- **Step 29 Suppression Register**: Soft removal (`removed_at`, `removed_by`), `MASTER_ADMIN` role gate, Redis pre-dial cache (`cp:suppression:{phone}`) with DB fallback.
- **Step 30 Campaign Start Guard**: Evaluates active script, rule set, compliance profile, verifier group, list mapping, and caller IDs, returning all missing problem codes at once.
- **Step 31 Telephony Adapter Seam**: `TelephonyAdapter` protocol, `ManualDialAdapter` implementation logging operations and returning `ExternalLeadRef(system="manual", external_id=lead.external_key)`, and `build_adapter` factory.

## 4. Phase 7 Completed Modules (Recordings Serving / Retention / 60s Watermark Rollups / Analytics)
- **Step 37 Recording Serving & Reconciler**: Presigned 5-min playback URLs (`recording.played`), single-use download tokens (`recording.downloaded`), status enum alignment (`pending → waiting_for_source → fetching → validating → storing → ready | failed | purged`), and 5-min `recording-reconciler` worker closing the orphan gap.
- **Step 38 Retention Policies & Audio Purger**: `retention_policies` schema (180d audio, 2555d transcript, indefinite metadata) and daily retention purger worker (`workers/retention_purger.py`) deleting physical audio objects while preserving metadata rows with `recording.purged` audit logs.
- **Step 39 60s Watermark Rollups Engine**: Migration `h3i4j5k6l7m8` added 6 `agg_*` tables. 60-second watermark incremental `rollup_worker` (`workers/rollup_worker.py`). Strict CI query isolation (`test_no_analytics_query_hits_raw_calls()`) ensuring `app/modules/analytics` queries fold exclusively over `agg_*` tables.
- **Step 40 Dashboard Analytics Wiring**: `AnalyticsView.jsx` wired via `apiFetch` to server exports and analytics rollups.

## 5. AI Gateway Integration (Step 26 - Deferred)
- `services/ai-gateway` is intentionally left untouched.
- When `services/ai-gateway` is connected, it will read `cp:campaign:{id}:active_script` and `cp:script:bundle:{versionId}` from Redis and execute graph walk.

## 5. Dialer Sync Deferred Integration (Phase 8 - Deferred)
- VICIdial sync outbox events (`talkflow.vicidial.sync.v1`) are enqueued on suppression additions/removals.
- Phase 8 dialer integration will process outbox events and call VICIdial non-agent API.