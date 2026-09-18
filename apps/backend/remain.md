# Fake-Gateway Soft Dependencies

The **STEP 16 fake gateway simulator** (`scripts/fake_gateway.py`) stems the
AI Voice Bot's wire contract (the five `talkflow.call.*.v1` topics) so
`apps/backend` can run and test the full call pipeline without Asterisk or the
AI-Gateway.  The events it emits reference identifiers that belong to modules
that are **not built yet**; until each owner module lands, the calls module and
ingest worker hold those references as *soft* values (nullable UUIDs with no
SQL foreign key).

When an owner module is completed, the wiring below must be tightened so the
real gateway / ingest path validates real records instead of arbitrary UUIDs.

## 1. `leads` Module

- `lead_id` is a soft reference on every simulated `talkflow.call.opened.v1`
  event (and on the ingested `calls.lead_id` row).  The CLI defaults to a
  generated UUID when `--lead-id` is not given.
- `GET /calls` renders `lead_name` via a read-only projection and already
  tolerates a missing lead row (`None`).
- **Follow-up when `leads` lands:** `--lead-id` should resolve against the
  real `leads` table (or the import wizard), and `calls.lead_id` gains a
  foreign key.

## 2. `scripts` Module

- `scriptVersionId` is a soft reference carried on every simulated
  `talkflow.call.opened.v1` event (and stored as `calls.script_version_id`).
  The simulator generates one per call when the CLI does not supply it.
- **Follow-up when `scripts` lands:** the gateway binds the campaign's
  activated script version and the ingest path validates it exists and is
  `approved` (see `apps/remain.md` §1).

## 3. `rule_sets` Module

- `ruleSetVersionId` is a soft reference carried on every simulated
  `talkflow.call.opened.v1` event (and stored as `calls.rule_set_version_id`).
  It names the rule-set version the voice bot executed during the call.
- **Follow-up when `rule_sets` lands:** bind the same version the campaign
  activated onto `calls.rule_set_version_id` at call open, and let the
  qualification consequence of each simulated outcome flow from a real rule
  set instead of the pure eligibility policy
  (`app/modules/calls/policies.py::evaluate_qualification`).