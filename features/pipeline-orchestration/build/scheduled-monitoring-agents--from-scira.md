# Scheduled Monitoring Agents (Lookouts) (build spec) — distilled from scira

## Summary

Turn a one-shot AI research call into a cron-scheduled monitoring agent. A user defines a query +
cadence + timezone; the system stores it, registers a schedule with QStash (Upstash), and on each
fire runs the existing research pipeline, persists the answer as a browsable chat, appends a run-
history entry, and emails the result. One route serves both CRUD and the cron callback (disambiguated
by the QStash signature header). Stack: Next.js route handlers + `@upstash/qstash` + Drizzle/Postgres.

## Core logic (inlined)

**Create (POST, user-initiated):**
```ts
// auth -> require Pro -> enforce limits (LOOKOUT_LIMITS: 30 total, 20 daily)
const row = await db.insert(lookout).values({
  id, userId, title, prompt, searchMode, frequency,
  cronSchedule,            // UTC cron, e.g. "0 9 * * *"
  timezone,                // IANA string, stored separately from cron
  nextRunAt, status: 'active',
});
if (frequency !== 'once') {
  const { scheduleId } = await qstash.schedules.create({
    destination: `${HOST}/api/lookout`,   // callback = this same route
    cron: cronSchedule,
    body: JSON.stringify({ lookoutId: id }),
  });
  await db.update(lookout).set({ qstashScheduleId: scheduleId }).where(eq(lookout.id, id));
} else {
  await qstash.publishJSON({ url: `${HOST}/api/lookout`, body: { lookoutId: id }, delay: secondsUntil(nextRunAt) });
  // one-time: qstashScheduleId stays null
}
```

**Callback (same POST route, QStash-initiated — detected via signature header):**
```ts
await verifySignature(req);                       // @upstash/qstash receiver; reject if invalid
const lk = await withBackoff(() => getLookout(lookoutId), { retries: 3 }); // absorb replication lag
if (!(await checkUserIsProById(lk.userId))) return; // races 2 subscription DBs, first 'yes' wins
await db.update(lookout).set({ status: 'running', lastRunAt: now }).where(eq(lookout.id, lk.id));

const chat = await createChat({ userId: lk.userId });
await createMessage({ chatId: chat.id, role: 'user', content: lk.prompt });
const tools = SEARCH_MODE_TOOLS[lk.searchMode];   // same registry the live app uses
const { text, usage, searches } = await runResearch({ prompt: lk.prompt, tools, mode: lk.searchMode });
await createMessage({ chatId: chat.id, role: 'assistant', content: text });

const entry = { runAt: now.toISOString(), chatId: chat.id, status: 'success',
                duration, tokensUsed: usage.totalTokens, searchesPerformed: searches };
await db.update(lookout).set({
  runHistory: [...lk.runHistory, entry],
  lastRunChatId: chat.id,
  status: lk.frequency === 'once' ? 'paused' : 'active',
  nextRunAt: lk.frequency === 'once' ? lk.nextRunAt : nextFromCron(lk.cronSchedule, lk.timezone),
}).where(eq(lookout.id, lk.id));

try { await sendEmail(lk.userId, truncateMarkdown(text)); } catch (e) { logger.warn(e); } // swallow
// on research error: status back to 'active', runHistory entry status:'error'
```

## Data contracts

`lookout` table (Drizzle/Postgres):
```ts
{
  id: text PK,
  userId: text notNull,                 // FK -> user.id, cascade delete
  title: text notNull,
  prompt: text notNull,
  frequency: text notNull,              // 'once'|'daily'|'weekly'|'monthly'(|'yearly')
  cronSchedule: text notNull,           // UTC cron, e.g. "0 9 * * *"
  timezone: text notNull default 'UTC', // IANA, e.g. "America/New_York"
  nextRunAt: timestamp notNull,
  qstashScheduleId: text,               // null for one-time runs
  status: text notNull default 'active',// 'active'|'paused'|'archived'|'running'
  searchMode: text notNull default 'extreme', // 'extreme'|'web'|'academic'|'youtube'|'reddit'|'github'|'stocks'|'x'|'code'|'chat'
  lastRunAt: timestamp,
  lastRunChatId: text,
  runHistory: json default [],          // RunHistoryEntry[]
  createdAt: timestamp notNull defaultNow,
  updatedAt: timestamp notNull defaultNow,
}
// indexes: (userId), (userId, status)

type RunHistoryEntry = {
  runAt: string; chatId: string;
  status: 'success'|'error'|'timeout';
  error?: string; duration?: number; tokensUsed?: number; searchesPerformed?: number;
};
```
Limits: `LOOKOUT_LIMITS = { total: 30, daily: 20 }`.

## Dependencies & assumptions

- **`@upstash/qstash`** — `schedules.create()` (recurring), `publishJSON({ delay })` (one-time), and
  `verifySignature`/receiver for callback auth.
- Drizzle ORM + Postgres for the `lookout` row and the run's `chat`/`message` records.
- The existing research pipeline + tool/mode registry (the run reuses them wholesale).
- An email service for result delivery; a `truncateMarkdown()` that cuts on safe boundaries.
- A public callback URL QStash can reach.

## To port this, you need:
- [ ] A scheduler that fires HTTP callbacks on a cron + supports delayed one-shot messages (QStash, or
      a cron worker + queue).
- [ ] Signature verification on the callback so only the scheduler can trigger runs.
- [ ] A `lookout` table with cron(UTC)+timezone stored *separately*, status enum, and a run-history store.
- [ ] Reuse of your one-shot research/agent pipeline, parameterized by a stored `searchMode`.
- [ ] Per-run persistence as a normal chat (so results are browsable) + a run-history append.
- [ ] Next-run recomputation from cron+timezone for recurring; pause-not-delete for one-time.
- [ ] Backoff retry on callback entry to absorb create→fire replication lag.
- [ ] Server-side limit enforcement (total + per-frequency).

## Gotchas

- **One route, two callers.** CRUD and the cron callback share the handler — branch on the signature
  header. Miss this and you either can't schedule or you expose the runner to the public.
- **Store cron in UTC, timezone separately.** Conflating them makes runs drift across DST/timezones.
- **Run history in a JSON column doesn't scale** — fine for bounded history; switch to a `lookout_run`
  table if you need deep, queryable history.
- **One-time runs pause, not delete.** Keep the row so the user can read the result; deleting loses it.
- **Errors must not disable the lookout.** Record the failure in run history but keep status schedulable
  (Scira rolls back to `active`), or one bad run silently kills the monitor.
- **Backoff on callback entry is load-bearing** — without it, a schedule that fires immediately after
  creation can't find its own row yet.
- **Swallow email errors** — a mail outage shouldn't fail the run or lose the saved result.

## Origin (reference only)

- Repo: https://github.com/zaidmukaddam/scira
- `app/api/lookout/route.ts` (CRUD + cron callback), `app/lookout/` (UI: `page.tsx`, `components/`,
  `hooks/use-lookout-form.ts`, `utils/time-utils.ts`, `constants.ts` with `LOOKOUT_LIMITS`),
  `lib/db/schema.ts` (`lookout` table).
- **Verify before relying on:** the exact QStash call signature (`schedules.create` vs `publishJSON`
  shape) and how `verifySignature` is wired (middleware vs inline), the `time-utils.ts` cron-generation
  logic, the email provider, and the precise monthly/yearly cron strings were not read field-by-field —
  confirm against the route + `time-utils.ts` before depending on them.
