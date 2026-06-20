# Agents as Teammates — from [multica](https://github.com/multica-ai/multica)

> Domain: [[_domain]] · Source: https://github.com/multica-ai/multica · NotebookLM: <link once added>

## What it does

Multica models an AI agent as a first-class member of the team, not a tool you invoke. An agent has a
profile, shows up on the issue board, gets assigned issues, posts comments, creates issues and
sub-issues, and raises its hand when it's stuck ("blocked") so a human can unblock it. The whole app
is built around the idea that a human teammate and an agent teammate are *the same kind of thing* with
the same affordances.

## Why it exists

If agents are going to do real work alongside people, the product can't bolt them on as a side panel —
they need to live in the same primitives humans do: issues, comments, assignment, status. Multica's
core design decision is **actor polymorphism**: nearly every record that has an author, creator,
assignee, or recipient stores a `*_type` of `'member'` or `'agent'` plus an id. That one pattern is
what lets an agent comment on an issue, get assigned work, and appear in the inbox exactly like a
person, without duplicating tables or branching logic everywhere.

## How it actually works

The schema is built on typed-actor columns. An `agent` row lives in a `workspace` with a `name`,
`avatar_url`, a `runtime_mode` (local|cloud), `runtime_config`, a `visibility` (workspace|private),
`max_concurrent_tasks`, and a `status` of idle | working | **blocked** | error | offline. An `issue`
has `assignee_type`/`assignee_id` and `creator_type`/`creator_id`, each `'member'` or `'agent'` — so
an agent can be the creator *or* the assignee. A `comment` has `author_type`/`author_id` (member or
agent) and a `type` of comment | status_change | progress_update | system, which lets agents post
machine-generated progress updates that render differently from human chatter. The `inbox_item`,
`activity_log`, and `autopilot` tables use the same `member|agent` (and `+system`) actor split.

"Reporting a blocker" isn't a separate table — it's a *coordinated state change* across those
primitives. When an agent can't proceed (auth failure, failing tests, missing context), it: sets its
own `agent.status = 'blocked'`, can move the `issue.status` to `'blocked'`, posts a comment (often
with a `blocked_reason`), and an `inbox_item` with `severity = 'action_required'` is raised to the
relevant human so it surfaces as "needs you." Issue-to-issue blocking is modeled separately via
`issue_dependency` rows of type `blocks` / `blocked_by` / `related`.

Agents perform these teammate actions during a run through a `multica` CLI (the agent literally runs
`multica issue comment ...`, `multica issue pull-requests ...`, etc.) — the same API surface a human
UI uses, so agent actions flow through identical server-side contracts (e.g. a PR title containing
`Closes MUL-123` records close-intent and can auto-advance the issue to `done` on merge).

## The non-obvious parts

- **Actor polymorphism is the whole trick.** `(*_type, *_id)` with `member|agent` everywhere means an
  agent is a peer, not a special case. Comments, issues, inbox, activity all share it.
- **A "blocker" is emergent, not a table.** It's the combination of agent status + issue status +
  an `action_required` inbox item + a comment — coordinated, not stored as one thing.
- **Comment `type` encodes who's "talking" how.** `progress_update`/`status_change`/`system` let
  agent output be first-class but visually distinct from human comments.
- **Agents act via the same CLI/API as humans.** There's no privileged backdoor — an agent uses the
  `multica` CLI, so server contracts (PR close-intent, sub-issue enqueue) apply identically.
- **Sub-issue create-status is a lever.** Creating a sub-issue as `todo` vs `backlog` decides whether
  an assigned agent starts immediately — a subtle control over autonomous cascades.
- **`max_concurrent_tasks` is per agent.** Agent throughput is a first-class profile field, like a
  person's capacity.

## Related
- [[autonomous-execution-lifecycle--from-multica]] (how an assigned agent actually runs the issue)
- [[autopilot-scheduled-work--from-multica]] (creates issues assigned to these agents)
- [[unified-runtimes-cli-detection--from-multica]] (the runtime that backs an agent's `runtime_mode`)
- [[conversation-memory--from-whatsapp-agentkit]] (another agent-as-participant model)
- [[agent-output-contract--from-last30days-skill]] (constraining how an agent's output is structured)
