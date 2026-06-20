# Autopilot — Scheduled/Triggered Agent Work (build spec) — distilled from multica

## Summary

Recurring agent work driven by a **generic DB-backed distributed-lock scheduler**. Three tables:
`autopilot` (definition), `autopilot_trigger` (schedule/webhook/api), `autopilot_run` (each
execution). The scheduler is the reusable core: a `sys_cron_executions` table whose unique key on
`(job_name, scope_kind, scope_id, plan_time)` is simultaneously the distributed lock and the audit
log — every server instance ticks the same jobs, one wins each planned run, losers no-op. Go +
Postgres (sqlc), but the scheduler pattern ports anywhere with a relational DB.

## Core logic (inlined)

**Schema (Postgres):**
```sql
CREATE TABLE autopilot (
  id UUID PK, workspace_id UUID, project_id UUID,
  title TEXT NOT NULL, description TEXT,
  assignee_id UUID NOT NULL REFERENCES agent(id),
  status TEXT DEFAULT 'active' CHECK (status IN ('active','paused','archived')),
  execution_mode TEXT DEFAULT 'create_issue' CHECK (execution_mode IN ('create_issue','run_only')),
  issue_title_template TEXT,
  created_by_type TEXT CHECK (created_by_type IN ('member','agent')), created_by_id UUID,
  last_run_at TIMESTAMPTZ, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ);

CREATE TABLE autopilot_trigger (
  id UUID PK, autopilot_id UUID REFERENCES autopilot(id) ON DELETE CASCADE,
  kind TEXT CHECK (kind IN ('schedule','webhook','api')),
  enabled BOOLEAN DEFAULT true,
  cron_expression TEXT, timezone TEXT DEFAULT 'UTC', next_run_at TIMESTAMPTZ,
  webhook_token TEXT, label TEXT, last_fired_at TIMESTAMPTZ);
-- partial index drives the scheduler scan:
CREATE INDEX idx_autopilot_trigger_next_run ON autopilot_trigger(next_run_at)
  WHERE enabled = true AND kind = 'schedule';

CREATE TABLE autopilot_run (
  id UUID PK, autopilot_id UUID, trigger_id UUID,
  source TEXT CHECK (source IN ('schedule','manual','webhook','api')),
  status TEXT DEFAULT 'pending'
    CHECK (status IN ('pending','issue_created','running','skipped','completed','failed')),
  issue_id UUID, task_id UUID,
  triggered_at TIMESTAMPTZ, completed_at TIMESTAMPTZ,
  failure_reason TEXT, trigger_payload JSONB, result JSONB);
-- agent_task_queue.autopilot_run_id and issue.origin_type='autopilot' link spawned work back.
```

**The generic scheduler (`sys_cron_executions`) — the reusable gem:**
```
Table sys_cron_executions: unique (job_name, scope_kind, scope_id, plan_time),
  + status, attempt, lease_token, stale_after, error_code, result JSONB.

JobSpec {
  Name              string         // stable audit/index key, snake_case
  Cadence           Duration       // plan bucket size; plan_time = floor(db_now - ScheduleDelay, Cadence)
  ScheduleDelay     Duration       // shift eligibility back from now (let late data land)
  CatchUpMode       enum           // LatestOnly | EveryPlan
  CatchUpWindow     Duration       // ignore plans older than now - window
  MaxPlansPerTick   int            // cap replay per tick (EveryPlan)
  RunTimeout        Duration       // < StaleTimeout
  StaleTimeout      Duration       // after last heartbeat, a RUNNING lease is stealable
  HeartbeatInterval Duration       // < StaleTimeout; handler must heartbeat
  AllowStaleReentry bool           // false => stale leases FAIL (error_code='stale_timeout'), need manual repair
  MaxAttempts       int
  RetryBackoff      []Duration     // backoff[i] before attempt i+2
  Scopes            ScopeProvider  // global => {global/global}; sharded => one per shard
  Handler           func(ctx, HandlerInput)(HandlerResult, error)
}

Tick(now):
  for job in registry:
    for scope in job.Scopes(now):
      plan_times = derivePlans(job, scope, now)         // LatestOnly or EveryPlan up to MaxPlansPerTick
      for pt in plan_times:
        INSERT sys_cron_executions(job,scope,pt,status='running',lease_token=me,stale_after=now+StaleTimeout)
          ON CONFLICT (job_name,scope_kind,scope_id,plan_time) DO NOTHING;   // <-- the lock
        if not inserted: continue          // another instance owns this plan -> silent no-op
        result, err = job.Handler(ctx, {PlanTime:pt, Attempt, Heartbeat})    // heartbeat extends stale_after
        if err: scheduleRetryOrFail(job, attempt, RetryBackoff, MaxAttempts)
        else:   UPDATE ... SET status='succeeded', result=... WHERE lease_token=me;
```

**Autopilot job handler (per due trigger):**
```
find autopilot_trigger where enabled and kind='schedule' and next_run_at <= now   // partial index
claim an autopilot_run via the scheduler lease (source='schedule')
if autopilot.execution_mode == 'create_issue':
    issue = createIssue({title: render(issue_title_template), origin_type:'autopilot', origin_id:autopilot.id,
                         assignee_type:'agent', assignee_id:autopilot.assignee_id, status:'todo'})
    task  = enqueue(agent_task_queue{agent_id:assignee, issue_id:issue.id, autopilot_run_id:run.id})
    run.status = 'issue_created'
else: // run_only
    run the agent directly without a tracked issue
next_run_at = nextFromCron(trigger.cron_expression, trigger.timezone)
```
Webhook door: `POST` endpoint authenticated by `autopilot_trigger.webhook_token` → insert
`autopilot_run(source='webhook', trigger_payload=<body>)` → same dispatch.

## Data contracts
- Trigger kinds: `schedule | webhook | api`. Run sources: `schedule | manual | webhook | api`.
- Run status: `pending → issue_created → running → completed | failed | skipped`.
- `plan_time` is canonical UTC, floored to `Cadence`. The `(job,scope,plan_time)` tuple is globally
  unique = the lock identity.

## Dependencies & assumptions
- A relational DB with a real UNIQUE constraint + `ON CONFLICT DO NOTHING` (Postgres here).
- A cron-expression evaluator with timezone support (to compute `next_run_at`).
- The agent task pipeline (issue + `agent_task_queue`) to dispatch into.
- Every app instance runs the tick loop; correctness comes from the DB, not from singleton deployment.

## To port this, you need:
- [ ] A `sys_cron_executions`-style table with unique `(job, scope, plan_time)` + lease/heartbeat columns.
- [ ] A `JobSpec` registry + tick loop that claims via `INSERT ... ON CONFLICT DO NOTHING`.
- [ ] Catch-up policy (latest-only vs every-plan) and a catch-up window per job.
- [ ] Stale-lease detection + (optional) theft for idempotent jobs; FAIL for non-idempotent ones.
- [ ] The three autopilot tables + a dispatch handler that creates issue+task (or runs directly).
- [ ] A webhook endpoint authenticated by a per-trigger token, converging on the same run/dispatch.
- [ ] `next_run_at` recomputation from cron+timezone after each fire.

## Gotchas
- **Don't gate on single-instance deployment.** The whole point is N instances ticking safely; the
  DB unique key is the lock. A naive goroutine ticker double-fires under horizontal scaling.
- **Heartbeat or lose the lease.** Long handlers must heartbeat to extend `stale_after`; otherwise a
  peer steals (idempotent) or the run FAILs (non-idempotent).
- **Catch-up must be chosen deliberately.** After downtime, EveryPlan can storm; LatestOnly can drop
  buckets that have independent meaning. Pick per job and bound with a window.
- **Overlap control is hard** — Multica *removed* its `concurrency_policy` (skip/queue/replace) after a
  skip-orphan bug. If you re-add it, design the orphan cleanup first.
- **Store cron + timezone separately;** compute `next_run_at` in UTC. Conflating them drifts schedules.
- **Tag generated issues** (`origin_type`) so they can be filtered from human views.

## Origin (reference only)
- Repo: https://github.com/multica-ai/multica
- `server/migrations/042_autopilot.up.sql` (3 tables), `043_fix_orphaned_autopilot_runs.up.sql`
  (concurrency_policy removal scar), `058_*`, `079_*` (status tweaks), `113_sys_cron_executions.up.sql`
  (scheduler table), `server/internal/scheduler/{spec.go,manager.go,db_ops.go}` (JobSpec + tick + SQL
  primitives). Doc: `docs/db-backed-execution-scheduler-rfc.md` (MUL-2957).
- **Verify before relying on:** the exact autopilot job handler wiring in `internal/scheduler` /
  `internal/service` (the dispatch from due trigger → issue+task) was inferred from schema + scheduler
  contract, not read line-by-line; confirm the handler before depending on field-level behavior.
