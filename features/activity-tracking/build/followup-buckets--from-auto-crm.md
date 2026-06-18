# Activity Tracking & Follow-up Buckets (build spec) — distilled from auto-crm

## Summary
Activities are timeline records (type, description, contact, optional deal, optional `scheduledAt`,
optional `completedAt`). A "pending follow-up" = `scheduledAt` set AND `completedAt` null. The
follow-up endpoint loads all incomplete activities (joined to contact), normalizes `scheduledAt` to
Unix **seconds**, and buckets them into **overdue / today / upcoming / unscheduled** using integer
day-window math. Returns four arrays. Same logic backs MCP `crm_get_followups`. Activity count +
recency feed lead scoring.

## Core logic (inlined)

### Bucketing (`GET /api/followups`)
```ts
// 1. incomplete activities, with contact info, ordered by due time
const rows = db.prepare(`
  SELECT a.*, c.name AS contactName, c.temperature AS contactTemperature
  FROM activities a JOIN contacts c ON a.contactId = c.id
  WHERE a.completedAt IS NULL
  ORDER BY a.scheduledAt ASC`).all();

// 2. day-window boundaries in Unix SECONDS
const nowSec      = Math.floor(Date.now() / 1000);
const todayStart  = Math.floor(nowSec / 86400) * 86400;        // midnight UTC today
const todayEnd    = todayStart + 86400;                        // midnight UTC tomorrow
// (tomorrowStart === todayEnd)

const overdue: any[] = [], today: any[] = [], upcoming: any[] = [], unscheduled: any[] = [];

for (const a of rows) {
  if (a.scheduledAt == null) { unscheduled.push(a); continue; }

  // normalize: Date -> /1000, numeric ms? -> /1000, numeric sec -> as-is
  const sched = a.scheduledAt instanceof Date
    ? Math.floor(a.scheduledAt.getTime() / 1000)
    : Number(a.scheduledAt);   // assume already seconds (see Gotchas re: ms vs s)

  if (sched < nowSec)            overdue.push(a);
  else if (sched < todayEnd)     today.push(a);   // now..todayEnd  => "today" (and not past)
  else                           upcoming.push(a); // >= tomorrow start
}

return Response.json({ overdue, today, upcoming, unscheduled });
```

Exact boundary semantics from the source:
- **overdue:** `scheduledAt < now`
- **today:** `todayStart <= scheduledAt < todayEnd` *and* not already past (i.e. `now <= sched < todayEnd`)
- **upcoming:** `scheduledAt >= (floor(now/86400)+1) * 86400` (tomorrow's midnight onward)
- **unscheduled:** `scheduledAt` is null/missing

### Logging an activity (`POST /api/activities` / MCP `crm_log_activity`)
```ts
db.prepare(`INSERT INTO activities (id,type,description,contactId,dealId,scheduledAt,completedAt,createdAt)
            VALUES (?,?,?,?,?,?,?,?)`)
  .run(crypto.randomUUID(), type /* call|email|meeting|note|followup */, description,
       contactId, dealId ?? null, scheduledAt ?? null, completedAt ?? null, Date.now());
```
Marking complete: `UPDATE activities SET completedAt=? WHERE id=?` — this removes it from the board.

## Data contracts
- **activities:** `{ id, type, description, contactId→contacts, dealId?→deals, scheduledAt?:ts,
  completedAt?:ts, createdAt:ts }`. Types: `call | email | meeting | note | followup`.
- **followups response:** `{ overdue[], today[], upcoming[], unscheduled[] }`, each item = activity
  row + `contactName` + `contactTemperature`.
- **Pending follow-up predicate:** `scheduledAt != null && completedAt == null`.

## Dependencies & assumptions
- An `activities` table with nullable `scheduledAt`/`completedAt`, FK to contacts (+ optional deal).
- A consistent timestamp unit — the bucket math works in **seconds**; be deliberate about ms vs s.
- The same query/bucketing is callable from both the web route and an agent/MCP tool.

## To port this, you need:
- [ ] An `activities` entity with type/description/contact + optional deal/scheduledAt/completedAt.
- [ ] A followups query: incomplete activities joined to contact, ordered by `scheduledAt`.
- [ ] The four-bucket classifier with day-window boundaries (decide UTC vs local — see Gotchas).
- [ ] A "mark complete" write (sets `completedAt`) to drop items off the board.
- [ ] (Recommended) re-score the contact on new activity so scoring's recency signal updates.

## Gotchas
- **UTC vs local midnight.** `floor(now/86400)*86400` is **midnight UTC**. For users in the Americas
  (auto-crm's audience), an item due at 11pm local can be classified into the wrong day. If local-day
  correctness matters, offset by the user's timezone before bucketing.
- **Milliseconds vs seconds.** The bucket math assumes seconds. If your `scheduledAt` is stored in ms
  (JS `Date.now()`), divide by 1000 first — mixing units silently throws everything into "overdue"
  (a ms value is ~1000× larger than the seconds `now`).
- **"Complete" is the only exit.** There's no dismiss/snooze — to remove an item you set `completedAt`.
  Add a snooze by bumping `scheduledAt` if users need it.
- **Unscheduled must be its own bucket.** An item with no date can't be overdue/today/upcoming, so
  without this bucket it disappears from every view. Keep it.
- **Ordering is by `scheduledAt ASC`** — nulls' position is DB-dependent; the code routes nulls to
  `unscheduled` explicitly regardless of sort order, so don't rely on the ORDER BY for correctness.
- **Activities double as the scoring signal.** Don't treat this table as cosmetic — count + recency
  drive `calculateLeadScore`.

## Origin (reference only)
auto-crm — `src/app/api/followups/route.ts` (bucketing), `src/app/api/activities/*` (CRUD), MCP
`crm_get_followups` / `crm_log_activity` in `mcp/crm-server.ts`. Activity types in
`src/lib/constants.ts`.
