# Activity Tracking & Follow-up Buckets — from [auto-crm](https://github.com/Hainrixz/auto-crm)

> Domain: [[_domain]] · Source: https://github.com/Hainrixz/auto-crm (`src/app/api/followups/route.ts`, `src/app/api/activities/`, MCP `crm_get_followups`) · NotebookLM: <add link>

## What it does
Every interaction with a contact — a call, an email, a meeting, a note, a scheduled follow-up — gets
logged as an **activity** on a timeline. The standout view this enables is the **follow-up board**:
it takes every promised-but-not-yet-done follow-up and sorts them into four urgency buckets —
**overdue** (you missed it), **today** (do it now), **upcoming** (coming up), and **unscheduled**
(you meant to follow up but never picked a date). Open it in the morning and you have your call list,
already triaged by how late you are.

## Why it exists
The single biggest way salespeople lose deals is forgetting to follow up. The job-to-be-done is
**nothing falls through the cracks**: turn a vague pile of "I should call them back" into a concrete,
time-sorted action list. The overdue bucket is the emotional core — it's the guilt list that makes
sure a hot lead doesn't go cold because you forgot. Logging activities also feeds the lead-scoring
engine (recent activity raises a lead's score; silence decays it), so the activity log isn't just a
diary — it's the signal that keeps the whole prioritization system honest.

## How it actually works
Activities are simple records: a type (call/email/meeting/note/follow-up), a description, the contact
they belong to (and optionally a deal), an optional `scheduledAt` (when it's due), and an optional
`completedAt` (when it was done). An activity with a `scheduledAt` but no `completedAt` is a *pending
follow-up* — that's the population the follow-up board works with.

The bucketing endpoint pulls all incomplete activities (where `completedAt` is null), joins in the
contact's details so each item can show who it's about, and orders them chronologically by their due
time. Then it does date math in Unix seconds. It normalizes every `scheduledAt` to a Unix-seconds
number, and computes "today" as a day window: the start of today is `floor(now / 86400) * 86400`
(86400 = seconds in a day) and the end is that plus 86400. With those boundaries it sorts each item:

- **Overdue** — due time is before *now* (in the past).
- **Today** — due time falls within today's start-to-end window.
- **Upcoming** — due time is at or after tomorrow's start (`(floor(now/86400)+1)*86400`).
- **Unscheduled** — no `scheduledAt` at all.

It returns four arrays, one per bucket, each full of activity records with their contact info — ready
for the UI to render as four columns or sections. The same logic is exposed to Claude as
`crm_get_followups`, so you can also just ask "what are my overdue follow-ups?" and get the same
triage conversationally.

## The non-obvious parts
- **"Pending follow-up" = scheduled but not completed.** The entire board is defined by that one
  predicate (`scheduledAt` set, `completedAt` null). Marking an activity complete is what removes it
  from the board — there's no separate "dismiss" concept.
- **Day boundaries via integer division on Unix seconds.** `floor(now/86400)*86400` is a cheap,
  dependency-free way to get "midnight today" — but it's **midnight UTC**, not the user's local
  midnight. So near midnight, an item can land in the "wrong" day for users far from UTC. A real
  gotcha for a product whose audience is in the Americas.
- **Four buckets, not a flat list, because urgency is the product.** The value isn't the list of
  follow-ups; it's the *prioritization*. Overdue-first framing creates the right pressure.
- **Unscheduled is a real category, not an error.** Logging "follow up with them" without a date is a
  legitimate state — the board surfaces these separately so they don't silently vanish (an item with
  no date can't be overdue or upcoming, so without this bucket it'd be invisible).
- **Activities are the fuel for scoring.** This isn't an isolated feature: activity count and recency
  directly drive `calculateLeadScore`. Logging discipline literally changes who rises in the queue.
- **Timeline + buckets are two views of one table.** The contact detail page shows a chronological
  timeline; the follow-up board shows the urgency triage — same `activities` rows, different lens.

## Related
- [[rule-based-lead-scoring--from-auto-crm]] — consumes activity count + recency; this feature
  produces that signal.
- [[mcp-crm-server--from-auto-crm]] — `crm_log_activity` writes activities and `crm_get_followups`
  exposes this exact bucketing to Claude.
- [[self-customizing-crm--from-auto-crm]] — the `daily-briefing` command narrates these buckets as a
  morning standup.
- See also: any task/CRM "due today / overdue" inbox — same time-bucketing pattern.
