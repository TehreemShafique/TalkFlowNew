# Remaining Backend Modules

Status: **`app/modules/campaigns/` is implemented** (migration `8e9f0a1b2c3d`,
ORM `Campaign` + `CampaignVicidialList`, router wired in `app/main.py`) and
**`app/modules/calls/` is implemented** (migration `9f0a1b2c3d4e`, six ORM
models, `call.view` / `call.disposition` permissions, router wired in
`app/main.py`, tests in `tests/test_calls.py`).

This file lists the modules that are **not built yet** and whose future
completion the **campaigns / calls modules depend on**. Until each owner module
lands, campaigns stores the reference as a *soft* value (nullable UUID / string
with no SQL foreign key) and the start guard in
`app/modules/campaigns/policies.py` only checks that the binding *exists*. When
the owner module is completed, the follow-up work below must be done so
campaigns validates real records instead of mere presence.

> Direction of dependency: **campaigns -> these modules**. (Other modules such
> as `leads`, `consent_provenance` and `suppression` are the reverse: they will
> depend on campaigns, not the other way around.)

---

## 1. `scripts` (owner of scripts / script_versions / script_activations)

**Current campaigns coupling**

- `campaigns.script_id` (nullable UUID, no FK) - `Campaign.script_id`.
- `campaigns.active_script_version_id` (nullable UUID, no FK) - `Campaign.active_script_version_id`.
- Start guard `CAMPAIGN_NO_ACTIVE_SCRIPT` only asserts the UUID is non-null.

**Follow-up when `scripts` is complete**

1. Add real FK constraints from `campaigns.script_id` / `active_script_version_id`
   to the `scripts` / `script_versions` tables (new alembic revision).
2. In `campaigns/policies.py` `can_start_campaign`, replace the presence check
   with a lookup that the referenced version exists and has `status = approved`
   (or is the campaign's activated version per `script_activations`).
3. Emit/consume `script.activated` events so `active_script_version_id` stays in
   sync (there is exactly one active script version per campaign).
4. Add `POST /api/v1/campaigns/{id}/script` (or reuse PUT) to bind an approved
   version, gated by `campaign.start`.

## 2. `rule_sets` (owner of rule_sets / rule_set_versions)

**Current campaigns coupling**

- `campaigns.rule_set_version_id` (nullable UUID, no FK).
- Start guard `CAMPAIGN_NO_RULE_SET` only asserts presence.

**Follow-up when `rule_sets` is complete**

1. Add FK from `campaigns.rule_set_version_id` to `rule_set_versions`.
2. Validate the bound version exists and is published/active in
   `can_start_campaign`.
3. Bind the same version id onto `calls.rule_set_version_id` at call open
   (owned by the calls/gateway flow, not campaigns).

## 3. `compliance` (owner of compliance_profiles / compliance_rules)

**Current campaigns coupling**

- `campaigns.compliance_profile_id` (nullable UUID, no FK).
- Start guard `CAMPAIGN_NO_COMPLIANCE_PROFILE` only asserts presence.

**Follow-up when `compliance` is complete**

1. Add FK from `campaigns.compliance_profile_id` to `compliance_profiles`.
2. Validate the profile exists and is active for the campaign's jurisdiction in
   `can_start_campaign`.
3. Re-check the profile whenever its rules change (versioned profiles, ADR-10).

## 4. `verifier_groups` (verifier pool / in-group)

**Current campaigns coupling**

- `campaigns.closer_in_group` is a free-text `VARCHAR(120)` (e.g. a VICIdial
  in-group name). No table exists.
- Start guard `CAMPAIGN_NO_VERIFIER_GROUP` only asserts the string is non-empty.

**Follow-up when the verifier/transfer module is complete**

1. Add a `verifier_groups` table (id, name/alias, VICIdial in-group, active) and
   change `campaigns.closer_in_group` to a FK (`verifier_group_id`).
2. Have `can_start_campaign` verify the group exists and has at least one
   available verifier.
3. Replace the `transfer` JSON blob's `verifierPool` free text with the group id.

## 5. `calls` (calls / call_events / transcripts) — DONE

Implemented in migration `9f0a1b2c3d4e` (`down_revision=e5f6a7b8c9d0`):

- `calls` RANGE-partitioned by `started_at` (PK `(id, started_at)`, monthly
  partitions 2026-09..11 + DEFAULT), plus `transcript_turns`, `call_events`,
  `call_qualification_fields`, `call_performance`, `call_node_path`.
- `app/modules/calls/` exposes `GET /calls`, `GET /calls/live`,
  `GET /calls/{id}`, `PATCH /calls/{id}/disposition`,
  `GET /calls/{id}/transcript|timeline|performance|script-path`, gated by
  `call.view` / `call.disposition` (Rule R4).
- Disposition -> qualification roll-up is pure policy
  (`app/modules/calls/policies.py`, ADR-03); every mutation writes one
  `audit_log` row + one outbox event in the same transaction (Rule R8).
- ORM equivalence: `calls_table` projection still inserts into the ORM `calls`
  table (server defaults fill `reference`/`direction`/`status`/`attempt_number`).

Outstanding (deferred by decision, not blocked):

1. `GET /api/v1/campaigns/{id}/stats` already reads `calls` (implemented with
   campaigns); keep future aggregates in a `calls`-owned `agg_*` snapshot.
2. The compliance-events module owns the authoritative consent artifact; the
   calls `consent` block remains the best-effort heuristic until then.

## 6. `packages/vicidial` adapter (dialer integration)

**Current campaigns coupling**

- `campaigns.vicidial_campaign_id` and `campaign_vicidial_lists.vicidial_list_id`
  store the dialer mapping, but nothing pushes to / reads from VICIdial yet. The
  client (`app/packages/vicidial/client.py`) is a placeholder.
- The start guard requires `vicidial_campaign_id` **and** at least one mapped
  list id (`CAMPAIGN_NO_LIST_MAPPING`).

**Follow-up when the VICIdial adapter is complete**

1. On `campaign.started`, push the campaign + mapped lists to VICIdial
   (non-agent API) using the rate-limited client and the `leadwrite` credential
   profile; record sync status.
2. On `campaign.paused`, pause the VICIdial campaign.
3. Add a reconciler that verifies `campaign_vicidial_lists` matches the dialer.

---

## Reverse dependencies (build order note)

These modules will be built **on top of** campaigns and must not be forgotten:

| Module | Depends on campaigns via |
|---|---|
| `leads` | `leads.campaign_id -> campaigns.id` (FK), dialable-set selection by campaign |
| `consent_provenance` | lead eligibility gating before campaign push (indirect) |
| `suppression` | DNC scope can be campaign-specific; suppression blocks campaign dialing |
| `calls` | **built** — `calls.campaign_id`, `call_recordings.campaign_id` |

## Definition of done for each follow-up

- New alembic revision adds the FK / table (never edit an applied revision).
- `can_start_campaign` grows the real validation and its unit tests cover the
  new failure codes (still returned all-at-once in `details.problems`).
- Campaigns keeps the same HTTP contract; only the internals tighten.
