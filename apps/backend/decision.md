# TalkFlow Backend Architectural Decisions & Logical Blueprint (`decision.md`)

This document records the architectural decisions, design patterns, integration rules, and core logical concepts governing the TalkFlow Control Plane backend (`apps/backend`).

---

## 1. Core System Philosophy

> **VICIdial owns the dialer. TalkFlow owns the business.**

To avoid split enforcement, dual DNC lists, and dialing race conditions:
* **VICIdial** is the single authoritative system for dialing, hopper depth, pacing, calling-hour enforcement, Trunk/Carrier routing, and AMD.
* **TalkFlow Control Plane** is the single authoritative system for lead master data, consent provenance, versioned script execution, qualification rule sets, verifier transfers, compliance enforcement, and analytics.

---

## 2. Key Architectural Decisions (ADRs)

### ADR-01: Architecture Choice — Domain-Driven Modular Monolith
* **Decision**: Build `apps/backend` as a Modular Monolith organized by business domains (`app/modules/<module_name>/`).
* **Rationale**: Avoids microservice network latency, complex distributed tracing, and multi-repo deployment overhead while maintaining strict domain isolation. All modules share single-head database migrations and core infrastructure packages.

### ADR-02: Strict 8-File Module Template
* **Decision**: Every module inside `app/modules/<module>/` strictly adheres to an identical file contract:
  1. `__init__.py`: Package marker.
  2. `router.py`: FastAPI HTTP routes, request validation, RBAC permission checks.
  3. `service.py`: Business transaction orchestration, event publishing, audit logging.
  4. `repository.py`: Scope-aware SQLAlchemy 2.0 async queries.
  5. `schemas.py`: Pydantic request/response DTOs (camelCase wire formatting).
  6. `errors.py`: Typed module error codes registered centrally.
  7. `events.py`: Kafka transactional outbox payload builders.
  8. `policies.py`: **Pure business logic functions with ZERO database/network I/O.**
* **Rationale**: Provides predictable navigation across all 16 modules and enables instant unit testing of domain rules.

### ADR-03: Pure Domain Policies (`policies.py`)
* **Decision**: All campaign start guards, script reachability checks, consent eligibility rules, and qualification logic live in `policies.py` as pure functions.
* **Rationale**: Guarantees 100% branch testability in milliseconds without needing database mocks or live server dependencies.

### ADR-04: Integration Model — Dual Enforcement Boundary
* **Decision**: Eliminate parallel ARI call originators. TalkFlow interacts with VICIdial via the VICIdial Non-Agent API (`/vicidial/non_agent_api.php`).
* **Rationale**: Building a parallel dialer alongside VICIdial creates dual DNC lists, split calling-hour checks, and un-reconcilable call logs. Making VICIdial the sole dialer enforcement point removes dialer duplication while letting TalkFlow govern business rules.

### ADR-05: Dedicated VICIdial Adapter Library (`packages/vicidial`)
* **Decision**: Encapsulate all VICIdial interaction in `app/packages/vicidial`.
* **Rationale**:
  * Uses 3 separate credential profiles (`readonly`, `leadwrite`, `dncwrite`) to minimize blast radius.
  * Implements a client-side token bucket rate limiter (5 req/sec max) and circuit breaker to protect the dialer's MySQL database.
  * Robustly parses VICIdial's text responses (`SUCCESS:`, `NOTICE:`, `ERROR:`) line by line.

### ADR-06: Dual-Write Suppression & Outbox Sync (Rule R12)
* **Decision**: Every opt-out or DNC suppression is written to TalkFlow DB and VICIdial DNC lists (`add_dnc_phone`) in the same worker pass, backed by a scheduled 60-minute reconciler.
* **Rationale**: Guarantees zero divergence between TalkFlow and VICIdial DNC registers.

### ADR-07: Sub-Second Realtime Loop Protection
* **Decision**: The control plane communicates with `services/ai-gateway` asynchronously via Kafka events (`talkflow.call.*`) and compiled Redis script bundles (`cp:script:bundle:{id}`).
* **Rationale**: The gateway's sub-second audio execution loop must never wait on synchronous REST HTTP requests to the backend mid-call.

### ADR-08: 4-Layer Disposition Taxonomy
* **Decision**: Replace flat single-status codes with a 4-layer disposition model:
  1. **Telephony Layer**: Authoritative from VICIdial/AMD (`initiated`, `no_answer`, `busy`, `amd_machine`).
  2. **Conversation Layer**: Authoritative from gateway (`dead_air`, `silence_no_response`, `opted_out`).
  3. **Qualification Layer**: Authoritative from rule set (`qualified`, `disqualified_no_part_ab`, `disqualified_age_range`).
  4. **Verifier Layer**: Authoritative from human agent (`verified_accepted`, `verified_rejected`, `sale`).
  * Plus multi-value **Compliance Flags** (`disclosure_missing`, `script_deviation`).
* **Rationale**: Allows independent computation of Contact Rate, Qualification Rate, Transfer Success, and Verifier Close Rate without corrupting metrics denominators.

### ADR-09: State-Aware Prior Consent Gate (§15.3)
* **Decision**: Leads without valid TCPA consent artifacts matching their target state's legal requirements are held in `blocked_no_consent` and never pushed to the VICIdial hopper.
* **Rationale**: Enforces federal and state-specific TCPA consent compliance (*Bradford v. Sovereign Pest Control*) before dialing occurs.

### ADR-10: Versioned Compliance Profiles (§15.6)
* **Decision**: Compliance rules (TPMO disclaimer pre-benefit, AI disclosure, opt-out) run under named profiles with 3 modes: `enforce`, `warn`, `off`. Setting any rule to `warn` or `off` requires Master Admin authentication, mandatory written rationale, and trigger-enforced audit logging.
* **Rationale**: Compliance is a transparent, versioned posture with an immutable audit trail rather than hardcoded assumptions.

---

## 3. Database & Security Standards

1. **ID Standard**: All primary keys are **UUIDv7** (time-sortable UUIDs).
2. **Table Partitioning**: `calls`, `call_events`, and `transcript_turns` are range-partitioned monthly by `started_at`.
3. **Database-Enforced Invariants**:
   * `audit_log`, `call_compliance_events`, and non-draft `script_versions` are guarded by `BEFORE UPDATE OR DELETE` database triggers throwing exceptions on mutation.
   * Partial unique index guarantees exactly **one active script version per campaign** (`WHERE deactivated_at IS NULL`).
4. **Scope Security (Rule R5)**: Every repository query accepts a mandatory `scope` parameter without defaults to enforce RBAC data access boundaries.
5. **PII Protection**: Single masking serializer converts PII fields (phones, DOB) based on the user's `pii.view_full` permission.

---

## 4. Operational Reconcilers

Three background worker reconcilers ensure platform integrity:

| Reconciler | Schedule | Function |
|---|---|---|
| **`recording-reconciler`** | Every 5 min | Fetches missing recordings from VICIdial SFTP/HTTP storage to eliminate orphaned recordings. |
| **`disposition-reconciler`** | Every 15 min | Reconciles TalkFlow call dispositions with VICIdial `vicidial_log` status and re-writes divergences. |
| **`dnc-reconciler`** | Every 60 min | Compares TalkFlow suppression lists with VICIdial DNC lists and alerts on any divergence. |
