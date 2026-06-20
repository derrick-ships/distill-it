# Autopilot — Scheduled/Triggered Agent Work — from [multica](https://github.com/multica-ai/multica)

> Domain: [[_domain]] · Source: https://github.com/multica-ai/multica · NotebookLM: <link once added>

## What it does

An "Autopilot" is a standing instruction to an AI agent that fires on a schedule (cron), on an
incoming webhook, or via API/manual trigger — "every weekday 8am, triage new bugs," "whenever this
webhook hits, draft a release note." Each fire either creates a fresh issue for the agent to work or
runs the agent directly, and every fire is recorded as an `autopilot_run` you can inspect.

## Why it exists

Agents are most valuable as *recurring teammates*, not one-off tools. Autopilots productize "keep
doing this for me": you define the work, the cadence, and the assignee once, and the platform keeps
dispatching it. The deeper engineering bet underneath is that all internal periodic work — autopilots
included — should ride on **one** reliable, multi-instance-safe scheduler rather than ad-hoc
goroutine tickers that double-fire when you run more than one server.

## How it actually works

Three tables model the feature: `autopilot` (the definition: title, assignee agent, status
active/paused/archived, and `execution_mode` = `create_issue` or `run_only`), `autopilot_trigger`
(how it fires: `kind` = schedule | webhook | api, with `cron_expression` + `timezone` + `next_run_at`
for schedules, or a `webhook_token` for webhooks), and `autopilot_run` (one execution, with a
`source`, a `status` lifecycle of pending → issue_created → running → completed | failed | skipped,
and links to the `issue_id` and `task_id` it spawned).

The scheduling itself is the clever part. Multica does **not** use a naive in-process cron. It has a
generic **DB-backed execution-record scheduler** built on a `sys_cron_executions` table. Every app
instance runs the same registered jobs on a tick, but the table has a unique key on `(job_name,
scope_kind, scope_id, plan_time)` — so when two instances try to claim the same planned run, exactly
one wins the row (the lease) and the losers silently no-op. That table is simultaneously the
distributed lock *and* the audit log. Each job is described by a `JobSpec` declaring its cadence,
catch-up policy (replay every missed bucket, or just the latest), retry backoff, and stale-lease
timeout. A running job must heartbeat; if it dies, its lease goes stale and (for idempotent jobs)
another instance can steal it.

For a scheduled autopilot, the loop finds triggers whose `next_run_at` is due, claims the run through
that lease mechanism, then dispatches: in `create_issue` mode it creates an `issue` (tagged
`origin_type = 'autopilot'` so it can be filtered) and enqueues an `agent_task_queue` row for the
assignee; in `run_only` mode it runs the agent without a tracked issue. Webhook triggers are the same
downstream — an HTTP endpoint authenticated by the trigger's `webhook_token` records a run with
`source = 'webhook'` and dispatches identically. After dispatch, `next_run_at` is recomputed from the
cron + timezone.

## The non-obvious parts

- **One scheduler for everything.** Autopilots aren't special-cased; they're one job on a generic
  DB-backed scheduler that also runs usage rollups etc. The `sys_cron_executions` table *is* the lock.
- **The DB unique key is the concurrency control.** No Redis lock, no leader election — the database's
  unique constraint on `(job, scope, plan_time)` decides who runs. Losers no-op without error.
- **Catch-up is a policy, not an accident.** A job declares whether a missed window replays every
  bucket or just the latest — so a server that was down doesn't silently drop (or storm) runs.
- **`concurrency_policy` was removed.** The autopilot table once had skip/queue/replace; a migration
  ripped it out after a "skip had an orphan bug" — a real scar worth knowing if you re-add overlap
  control.
- **Issues remember their origin.** `issue.origin_type = 'autopilot'` + `origin_id` let the UI filter
  auto-generated issues out of human lists.
- **Webhook = same pipeline, different door.** Schedule/webhook/api/manual all converge on the same
  `autopilot_run` + dispatch; only the `source` and auth differ.

## Related
- [[autonomous-execution-lifecycle--from-multica]] (what runs after an autopilot dispatches a task)
- [[agents-as-teammates--from-multica]] (the agent/issue model an autopilot creates work in)
- [[scheduled-monitoring-agents--from-scira]] (a contrasting take: QStash-backed scheduled agents)
- [[queue-backed-crawl--from-firecrawl]] (another job/queue orchestration pattern)
- [[incremental-sync-state--from-airbyte]] (catch-up/watermark semantics in a different domain)
