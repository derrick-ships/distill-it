# Scheduled Monitoring Agents (Lookouts) — from [scira](https://github.com/zaidmukaddam/scira)

> Domain: [[_domain]] · Source: https://github.com/zaidmukaddam/scira · NotebookLM: <link once added>

## What it does

A "Lookout" is a research question you set on a schedule — "every weekday at 9am, summarize new
papers on battery recycling" — and Scira runs it for you automatically, on a cron, in your timezone,
and emails you the result. Each run is a normal Scira research chat you can open and read, and the
Lookout keeps a history of every run with its status.

## Why it exists

Most research isn't one-and-done — you want to *keep watching* a topic. Doing that by hand means
remembering to re-ask the same question every day. Lookouts turn Scira's one-shot research engine into
a standing agent: define the query and cadence once, and it monitors for you. It's the productized
"set it and forget it" loop on top of the same search pipeline the live UI uses — a Pro feature that
turns a search tool into a monitoring service.

## How it actually works

A single API route (`app/api/lookout/route.ts`) does double duty: it's both the CRUD endpoint the UI
calls *and* the callback QStash hits when a schedule fires. It tells the two apart by the presence of
QStash's signature header.

**Creating one.** The form (title, prompt, search mode, frequency, time, timezone, and — depending on
frequency — a day-of-week or a date) computes a cron expression and a `nextRunAt`. POST to the route:
it authenticates, checks the user is Pro, enforces limits (max 30 total, max 20 daily), writes a
`lookout` row (status `active`), and registers the schedule with QStash. For recurring frequencies it
calls QStash `schedules.create()` with the cron + a callback URL pointing back at the same route, and
stores the returned `qstashScheduleId`. For a one-time "once" lookout it instead publishes a single
delayed QStash message (no repeating schedule, so `qstashScheduleId` stays null).

**When it fires.** QStash POSTs the callback. The route verifies the Upstash signature, then:
1. Loads the lookout row, retrying up to 3× with backoff (guards against DB replication lag right
   after the schedule was created).
2. Re-checks Pro status — racing two subscription databases in parallel and taking the first "yes".
3. Flips status to `running`, sets `lastRunAt`.
4. Creates a fresh `chat` + user `message` containing the lookout's prompt — so the run *is* a normal
   browsable chat.
5. Maps the lookout's `searchMode` to a tool set and runs the same AI research pipeline the live app
   uses (mode-specific prompts and citation rules apply).
6. Saves the assistant answer as a message, records metrics (duration, tokens, searches).
7. Appends a `runHistory` entry (`{ runAt, chatId, status, error?, duration?, tokensUsed?,
   searchesPerformed? }`) to a JSON array on the lookout row.
8. Emails the user a truncated-markdown version of the answer (email failures are swallowed, logged
   only).
9. Computes the next run: recurring → recalc `nextRunAt` from cron+timezone, status back to `active`;
   once → status `paused` (row kept so the result stays visible).

On a generation error, status rolls back to `active` (not `error`) and the run-history entry is marked
`error` — a bad run never halts future runs.

## The non-obvious parts

- **One route is both CRUD and cron callback.** It disambiguates by the QStash signature header. Tidy,
  but a re-implementer reading only the "create" path misses half the logic.
- **Run history is a JSON column, not a table.** All runs live in a `runHistory` array on the lookout
  row — bounded, and not independently SQL-queryable. Simple, but doesn't scale to deep history.
- **Cron is stored in UTC; timezone is stored separately.** The cron fires in UTC; the timezone is
  used only to compute display times and `nextRunAt`. Get this split wrong and schedules drift.
- **"Once" doesn't use a repeating schedule** — it's a single delayed message, and the row is *paused*
  (kept), not deleted, after firing, so the user can still read the result.
- **Pro check races two databases.** Subscriptions live in two systems; it queries both and takes the
  first positive — latency optimization that's easy to overlook.
- **Backoff-retry on callback entry** absorbs the race between "schedule created" and "row visible."
- **Errors don't disable the Lookout** — failures are recorded but the schedule keeps running.

## Related
- [[agentic-research-planning--from-scira]] (the research pipeline each scheduled run invokes)
- [[tool-and-search-mode-registry--from-scira]] (how `searchMode` maps to the run's tools)
- [[queue-backed-crawl--from-firecrawl]] (another queue/job-driven orchestration — good contrast)
- [[incremental-sync-state--from-airbyte]] (scheduled, stateful recurring jobs in a different domain)
