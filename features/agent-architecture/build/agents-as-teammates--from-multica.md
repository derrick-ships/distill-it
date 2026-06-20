# Agents as Teammates (build spec) — distilled from multica

## Summary

Model AI agents as first-class team members via **actor polymorphism**: every authored/assigned/
addressed record stores a `*_type` of `'member' | 'agent'` (+ `'system'` where relevant) plus an id.
One pattern lets an agent create issues, comment, get assigned, and appear in the inbox exactly like a
human — no parallel tables. "Reporting a blocker" is an emergent coordinated state change, not a
table. Postgres schema; the modeling pattern is stack-agnostic.

## Core logic (inlined)

**Schema (the typed-actor pattern in bold):**
```sql
CREATE TABLE agent (
  id UUID PK, workspace_id UUID,
  name TEXT, avatar_url TEXT,
  runtime_mode TEXT CHECK (runtime_mode IN ('local','cloud')),
  runtime_config JSONB DEFAULT '{}',
  visibility TEXT DEFAULT 'workspace' CHECK (visibility IN ('workspace','private')),
  status TEXT DEFAULT 'offline' CHECK (status IN ('idle','working','blocked','error','offline')),
  max_concurrent_tasks INT DEFAULT 1,
  owner_id UUID REFERENCES "user"(id));

CREATE TABLE issue (
  id UUID PK, workspace_id UUID, title TEXT, description TEXT,
  status TEXT DEFAULT 'backlog'
    CHECK (status IN ('backlog','todo','in_progress','in_review','done','blocked','cancelled')),
  priority TEXT DEFAULT 'none' CHECK (priority IN ('urgent','high','medium','low','none')),
  assignee_type TEXT CHECK (assignee_type IN ('member','agent')), assignee_id UUID,   -- agent CAN be assignee
  creator_type  TEXT CHECK (creator_type  IN ('member','agent')), creator_id  UUID,   -- agent CAN be creator
  parent_issue_id UUID REFERENCES issue(id),
  acceptance_criteria JSONB DEFAULT '[]', context_refs JSONB DEFAULT '[]',
  position FLOAT DEFAULT 0, due_date TIMESTAMPTZ);

CREATE TABLE comment (
  id UUID PK, issue_id UUID,
  author_type TEXT CHECK (author_type IN ('member','agent')), author_id UUID,         -- agent CAN author
  content TEXT,
  type TEXT DEFAULT 'comment' CHECK (type IN ('comment','status_change','progress_update','system')));

CREATE TABLE inbox_item (
  id UUID PK, workspace_id UUID,
  recipient_type TEXT CHECK (recipient_type IN ('member','agent')), recipient_id UUID, -- agent CAN receive
  type TEXT,
  severity TEXT DEFAULT 'info' CHECK (severity IN ('action_required','attention','info')),
  issue_id UUID, title TEXT, body TEXT, read BOOLEAN, archived BOOLEAN);

CREATE TABLE issue_dependency (             -- issue<->issue blocking (separate from agent "blocked" status)
  id UUID PK, issue_id UUID, depends_on_issue_id UUID,
  type TEXT CHECK (type IN ('blocks','blocked_by','related')));

CREATE TABLE activity_log (                 -- actor split incl. 'system'
  id UUID PK, workspace_id UUID, issue_id UUID,
  actor_type TEXT CHECK (actor_type IN ('member','agent','system')), actor_id UUID,
  action TEXT, details JSONB);
```

**"Report a blocker" = coordinated state change (no blocker table):**
```
agent hits a wall (auth fail / failing tests / missing context):
  UPDATE agent SET status='blocked' WHERE id=:agent
  UPDATE issue SET status='blocked' WHERE id=:issue            -- optional, when the issue itself is blocked
  INSERT comment(issue_id, author_type='agent', author_id=:agent, type='progress_update',
                 content='Blocked: <blocked_reason>')
  INSERT inbox_item(recipient_type='member', recipient_id=:human, severity='action_required',
                    issue_id=:issue, title='Agent blocked on <issue>', body=<reason>)
```

**Agents act through the same CLI/API as humans** (no privileged path):
```
during a run the agent invokes: multica issue comment <id> ...
                                 multica issue pull-requests <id> --output json
                                 multica issue create / status / link ...
server contracts apply identically, e.g. a PR with "Closes MUL-123" in title/body (NOT branch)
  records close-intent -> auto-advances the linked issue to 'done' on merge.
sub-issue created as status='todo' => assigned agent starts immediately; 'backlog' => waits.
```

## Data contracts
- Actor split: `('member'|'agent')` for author/creator/assignee/recipient; `+'system'` in activity_log.
- Agent status: `idle | working | blocked | error | offline`.
- Issue status: `backlog | todo | in_progress | in_review | done | blocked | cancelled`.
- Comment type: `comment | status_change | progress_update | system`.
- Inbox severity: `action_required | attention | info`.

## Dependencies & assumptions
- A relational DB; everything keys off workspace scoping + the typed-actor columns.
- A CLI/API surface agents call (so agent and human actions share server contracts).
- (For PR-linked workflows) a VCS webhook that scans PR title/body/branch for issue keys.

## To port this, you need:
- [ ] The `(*_type, *_id)` actor pattern on every authored/assigned/addressed table (`member|agent`).
- [ ] An `agent` profile table with status incl. `blocked`, `runtime_mode`, `max_concurrent_tasks`.
- [ ] Comment `type` to distinguish human chatter from agent progress/status/system messages.
- [ ] An inbox with an `action_required` severity to surface blockers to humans.
- [ ] A blocker convention: agent status + (optional) issue status + comment + action_required inbox item.
- [ ] Agents acting via the same API/CLI as humans (one set of server contracts, no backdoor).
- [ ] `issue_dependency(blocks|blocked_by|related)` for issue↔issue blocking, kept distinct from status.

## Gotchas
- **Don't build a separate "blocker" entity.** It's emergent: status + comment + inbox item. A
  dedicated table fragments the truth and desyncs from the agent's actual status.
- **Two different "blocked" concepts** coexist: an *agent* being blocked (status) and an *issue* being
  blocked (status and/or an `issue_dependency`). Keep them separate or reporting gets muddy.
- **Agent identity must be a real row, not a string** — assignment, comments, inbox, and capacity
  (`max_concurrent_tasks`) all FK to it.
- **Route agent actions through the same contracts as humans.** Multica's agents run the `multica`
  CLI; this is why PR close-intent and sub-issue enqueue behave identically for agents and people.
- **Sub-issue create-status controls cascades** — `todo` auto-starts the assignee; `backlog` parks it.
  Pick deliberately or autonomous agents may stampede.

## Origin (reference only)
- Repo: https://github.com/multica-ai/multica
- `server/migrations/001_init.up.sql` (agent, issue, comment, inbox_item, issue_dependency,
  activity_log, agent_task_queue), later migrations: `012_inbox_actor`, `017/018_comment_parent`,
  `021_agent_instructions`. Agent behavioral contract:
  `server/internal/service/builtin_skills/multica-working-on-issues/SKILL.md` (PR linking/close-intent,
  blocked-reason reporting, sub-issue enqueue semantics).
- **Verify before relying on:** the exact server handler that raises the `action_required` inbox item
  on a blocker was inferred from the schema + agent skill doc (which says to "report that blocker"),
  not read as a single function; confirm the blocker handler in `internal/service`/`internal/handler`.
