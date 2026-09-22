# Metrics Manual — one SQL definition per metric

Every displayed number in the dashboard traces to a column in the six
pre-aggregated tables below (blueprint §14.4, TalkFlow roadmap STEP 39).  No
analytics endpoint touches the raw `calls` table; the rollup worker is the only
writer and it is idempotent (ON CONFLICT upsert), so re-runs and backfills are
snapshot-equal.

Conventions:

- A call is **answered** when `calls.answered_at IS NOT NULL`.
- A call is **contacted** when a conversation-layer disposition exists
  (`calls.disposition IS NOT NULL`).  Contacted ⊂ answered.
- `_unassigned` is the sentinel for a NULL dimension (no campaign / no script
  version / no source / no alias stated by the ingest stamp).
- `DATE` means `calls.started_at::date`; the rollup window is
  `started_at >= :watermark AND started_at < :now`.

---

## agg_campaign_daily
Serves **PRD report: Daily Medicare Campaign Summary (`/analytics/campaigns`)**
and the funnel KPIs on `/analytics/summary`.

```sql
INSERT INTO agg_campaign_daily (date, tenant_id, campaign_id, total_calls,
       answered, contacted, qualified, transferred, verifier_accepted,
       disqualified, avg_duration)
SELECT date(started_at), COALESCE(tenant_id, '_unassigned'),
       COALESCE(campaign_id, '00000000-0000-0000-0000-000000000000'),
       count(*),
       count(*) FILTER (WHERE answered_at IS NOT NULL),
       count(*) FILTER (WHERE disposition IS NOT NULL),
       count(*) FILTER (WHERE qualification_status = 'qualified'),
       count(*) FILTER (WHERE transfer_status = 'completed'),
       count(*) FILTER (WHERE verifier_id IS NOT NULL),
       count(*) FILTER (WHERE qualification_status = 'disqualified'),
       avg(duration_seconds)
FROM calls
WHERE started_at >= :watermark AND started_at < :now
GROUP BY 1,2,3
ON CONFLICT (date, tenant_id, campaign_id) DO UPDATE SET
  total_calls = EXCLUDED.total_calls, answered = EXCLUDED.answered,
  contacted = EXCLUDED.contacted, qualified = EXCLUDED.qualified,
  transferred = EXCLUDED.transferred,
  verifier_accepted = EXCLUDED.verifier_accepted,
  disqualified = EXCLUDED.disqualified, avg_duration = EXCLUDED.avg_duration;
```

Metrics: `total_calls`; `answered`; `contacted`; `qualified`; `transferred`;
`verifier_accepted`; `disqualified`; `avg_duration` (seconds).

---

## agg_script_version_daily
Serves **PRD report: Script Performance (`/analytics/scripts`)**.

```sql
INSERT INTO agg_script_version_daily (date, tenant_id, script_version_id,
       total_calls, answered, contacted, qualified, transferred, disqualified,
       avg_duration)
SELECT date(started_at), COALESCE(tenant_id, '_unassigned'),
       COALESCE(script_version_id, '00000000-0000-0000-0000-000000000000'),
       count(*),
       count(*) FILTER (WHERE answered_at IS NOT NULL),
       count(*) FILTER (WHERE disposition IS NOT NULL),
       count(*) FILTER (WHERE qualification_status = 'qualified'),
       count(*) FILTER (WHERE transfer_status = 'completed'),
       count(*) FILTER (WHERE qualification_status = 'disqualified'),
       avg(duration_seconds)
FROM calls
WHERE started_at >= :watermark AND started_at < :now
GROUP BY 1,2,3
ON CONFLICT (date, tenant_id, script_version_id) DO UPDATE SET ...;
```

Metrics: `total_calls`, `answered`, `contacted`, `qualified`, `transferred`,
`disqualified`, `avg_duration`.

---

## agg_source_daily
Serves **PRD report: Lead Source Quality (`/analytics/sources`)**.  Source lives
on `leads`, so the rollup joins the lead master via the read-only projection
(`leads.phone_normalized` is PII; only `leads.source` is folded in).

```sql
INSERT INTO agg_source_daily (date, tenant_id, source, total_calls, answered,
       contacted, qualified, transferred, verifier_accepted, disqualified)
SELECT date(c.started_at), COALESCE(c.tenant_id, '_unassigned'),
       COALESCE(l.source, '_unassigned'),
       count(*),
       count(*) FILTER (WHERE c.answered_at IS NOT NULL),
       count(*) FILTER (WHERE c.disposition IS NOT NULL),
       count(*) FILTER (WHERE c.qualification_status = 'qualified'),
       count(*) FILTER (WHERE c.transfer_status = 'completed'),
       count(*) FILTER (WHERE c.verifier_id IS NOT NULL),
       count(*) FILTER (WHERE c.qualification_status = 'disqualified')
FROM calls c LEFT JOIN leads l ON l.id = c.lead_id
WHERE c.started_at >= :watermark AND c.started_at < :now
GROUP BY 1,2,3
ON CONFLICT (date, tenant_id, source) DO UPDATE SET ...;
```

Metrics: `total_calls`, `answered`, `contacted`, `qualified`, `transferred`,
`verifier_accepted`, `disqualified`.

---

## agg_bot_daily
Serves **PRD report: AI Bot Performance (`/analytics/bot`)**.  `agent_alias` is
the ingest stamp `calls.agent_alias_used` (recorded at call open, §roadmap
"script + rule-set + channel + agent stamped at open").

```sql
INSERT INTO agg_bot_daily (date, tenant_id, agent_alias, total_calls, answered,
       contacted, qualified, transferred, avg_talk_time_seconds, avg_duration)
SELECT date(started_at), COALESCE(tenant_id, '_unassigned'),
       COALESCE(agent_alias_used, '_unassigned'),
       count(*),
       count(*) FILTER (WHERE answered_at IS NOT NULL),
       count(*) FILTER (WHERE disposition IS NOT NULL),
       count(*) FILTER (WHERE qualification_status = 'qualified'),
       count(*) FILTER (WHERE transfer_status = 'completed'),
       avg(talk_time_seconds), avg(duration_seconds)
FROM calls
WHERE started_at >= :watermark AND started_at < :now
GROUP BY 1,2,3
ON CONFLICT (date, tenant_id, agent_alias) DO UPDATE SET ...;
```

Metrics: `total_calls`, `answered`, `contacted`, `qualified`, `transferred`,
`avg_talk_time_seconds`, `avg_duration`.

---

## agg_compliance_daily
Serves **PRD report: Compliance Review (`/analytics/compliance`)**.  Built from
call-level compliance signals until the compliance-events module lands:
disqualifications (with reason), opt-outs, and QA auto-fails.

```sql
INSERT INTO agg_compliance_daily (date, tenant_id, campaign_id, reason,
       total_calls, answered, contacted, qualified, disqualified, opted_out,
       qa_autofail)
SELECT date(started_at), COALESCE(tenant_id, '_unassigned'),
       COALESCE(campaign_id, '00000000-0000-0000-0000-000000000000'),
       COALESCE(NULLIF(disqualification_reason, ''), '_unassigned'),
       count(*),
       count(*) FILTER (WHERE answered_at IS NOT NULL),
       count(*) FILTER (WHERE disposition IS NOT NULL),
       count(*) FILTER (WHERE qualification_status = 'qualified'),
       count(*) FILTER (WHERE qualification_status = 'disqualified'),
       count(*) FILTER (WHERE disqualification_reason = 'opted_out'),
       count(*) FILTER (WHERE qa_status = 'auto_fail')
FROM calls
WHERE started_at >= :watermark AND started_at < :now
GROUP BY 1,2,3,4
ON CONFLICT (date, tenant_id, campaign_id, reason) DO UPDATE SET ...;
```

Metrics: `total_calls`, `answered`, `contacted`, `qualified`, `disqualified`,
`opted_out`, `qa_autofail`.  The DQ-breakdown metric (§14.4) is served by
weighting `disqualified` by `reason`.

---

## agg_dashboard_counters
Serves **PRD report: Business Overview headline strip (`/analytics/summary`)**.
One row per tenant, refreshed each rollup pass.

```sql
INSERT INTO agg_dashboard_counters (tenant_id, captured_at, total_calls,
       calls_today, answered_today, qualified_today, active_campaigns,
       enabled_scripts, suppression_count, live_calls)
SELECT :tenant_id, :now,
       (SELECT count(*) FROM calls),
       (SELECT count(*) FROM calls WHERE started_at >= date_trunc('day', :now)),
       (SELECT count(*) FROM calls
         WHERE started_at >= date_trunc('day', :now) AND answered_at IS NOT NULL),
       (SELECT count(*) FROM calls
         WHERE started_at >= date_trunc('day', :now)
           AND qualification_status = 'qualified'),
       (SELECT count(*) FROM campaigns WHERE uq_script_activations_active IS NULL),
       ...
ON CONFLICT (tenant_id) DO UPDATE SET ...;
```

Metrics: `total_calls`, `calls_today`, `answered_today`, `qualified_today`,
`active_campaigns`, `enabled_scripts`, `suppression_count`, `live_calls`.

Note: `agg_dashboard_counters` is the only rollup that also reads non-`calls`
tables (campaigns / scripts / suppression / live index).  It is still a
pre-aggregate — no endpoint computes these on read.

---

## Rates derived on read (pure scalars, no extra SQL)

```text
contact rate        = contacted / answered          (PRD: Business Overview)
qualification rate  = qualified / contacted         (PRD: Overview + scripts)
transfer success    = transferred / qualified       (PRD: Overview + campaigns)
verifier close rate = verifier_accepted / transferred (PRD: Overview + sources)
```

These are computed in `analytics/policies.py` with a guarantee that a zero
denominator yields `0.0` rather than a division error, and are unit-tested.

---

## Performance telemetry (`/analytics/performance`)

Engineering telemetry is NOT covered by the six rollups (it has no PRD report;
the page is operational).  It reads the per-call `call_performance` table
(never `calls`), aggregating latency percentiles server-side:

```sql
SELECT date(c.started_at) AS date,
       COALESCE(p.llm_provider, 'unknown') AS provider,
       count(*) AS samples,
       percentile_cont(0.50) WITHIN GROUP (ORDER BY p.total_turn_ms) AS p50,
       percentile_cont(0.95) WITHIN GROUP (ORDER BY p.total_turn_ms) AS p95,
       percentile_cont(0.99) WITHIN GROUP (ORDER BY p.total_turn_ms) AS p99
FROM call_performance p JOIN calls c ON c.id = p.call_id
WHERE c.started_at >= :from AND c.started_at < :to
GROUP BY 1,2 ORDER BY 1;
```