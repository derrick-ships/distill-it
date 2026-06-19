# Domain: activity-tracking

Logging every interaction with a record (calls, emails, meetings, notes, scheduled follow-ups) as a
timeline, and triaging the pending ones by urgency so nothing falls through the cracks.

## What this domain is about

Activity tracking is **memory + accountability**: a durable log of what happened with each contact,
and — more valuably — a forward-looking list of what's *due*. The killer view is the follow-up
triage: turning "I should call them back" into a time-sorted action list (overdue first). The same
activity log is also the raw signal that powers prioritization elsewhere (recent activity = hotter
lead, silence = decay), so it's never just a diary.

## Pattern shared across features in this domain

Activities are records with a type, a description, a parent record, and two optional timestamps:
`scheduledAt` (due) and `completedAt` (done). A **pending follow-up** is the predicate `scheduledAt
set AND completedAt null`. Triage buckets pending items by comparing `scheduledAt` to day-window
boundaries (overdue / today / upcoming / unscheduled). The same table feeds two views — a
chronological timeline and an urgency board — and feeds scoring's recency/engagement signals.

## Features in this domain

- [[followup-buckets--from-auto-crm]] — buckets incomplete scheduled activities into overdue/today/
  upcoming/unscheduled via Unix-seconds day-window math; backs both the web follow-up board and MCP
  `crm_get_followups`, and supplies the activity signal to lead scoring.
