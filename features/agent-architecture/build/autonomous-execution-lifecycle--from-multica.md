# Autonomous Execution Lifecycle + WebSocket Streaming (build spec) — distilled from multica

## Summary

Move an agent task from `queued` to `completed`/`failed` across a server (orchestration + persistence)
and a separate daemon (execution on the user's machine), streaming every step over one multiplexed
WebSocket. Key design points: the WS dispatch is only a **wakeup hint** (the daemon claims via HTTP,
transactionally), and every streamed message carries a monotonic `seq` so the transcript is ordered
and replayable. Go + gorilla/websocket + Postgres; the protocol/state-machine pattern is portable.

## Core logic (inlined)

**Task state machine (`agent_task_queue`):**
```sql
CREATE TABLE agent_task_queue (
  id UUID PK,
  agent_id UUID REFERENCES agent(id), issue_id UUID REFERENCES issue(id),
  status TEXT DEFAULT 'queued'
    CHECK (status IN ('queued','dispatched','running','completed','failed','cancelled')),
  priority INT DEFAULT 0,
  dispatched_at TIMESTAMPTZ, started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ,
  result JSONB, error TEXT, created_at TIMESTAMPTZ);
-- + autopilot_run_id UUID (link back to the autopilot run that spawned it)
```
Transitions: `queued → dispatched` (on claim) `→ running` (CLI spawned) `→ completed | failed`;
`cancelled` from any pre-terminal state.

**WebSocket protocol (`pkg/protocol`) — one envelope, many types:**
```go
type Message struct { Type string `json:"type"`; Payload json.RawMessage `json:"payload"` }

// server -> daemon
type TaskDispatchPayload  struct { TaskID, IssueID, Title, Description string }
type TaskAvailablePayload struct { RuntimeID string; TaskID string `json:",omitempty"` } // WAKEUP HINT only

// daemon -> server  (live transcript; one per agent step)
type TaskMessagePayload struct {
  TaskID  string; IssueID string `json:",omitempty"`
  Seq     int                                  // <-- monotonic; ordering + replay backbone
  Type    string                               // "text" | "tool_use" | "tool_result" | "error"
  Tool    string `json:",omitempty"`           // tool name (tool_use/tool_result)
  Content string `json:",omitempty"`           // text content
  Input   map[string]any `json:",omitempty"`   // tool input (tool_use)
  Output  string `json:",omitempty"`           // tool output (tool_result)
  CreatedAt string `json:",omitempty"`
}
type TaskProgressPayload  struct { TaskID, Summary string; Step, Total int `json:",omitempty"` }
type TaskCompletedPayload struct { TaskID, PRURL, Output string `json:",omitempty"` }
type DaemonRegisterPayload struct { DaemonID, AgentID string; Runtimes []RuntimeInfo }
// also multiplexed on the same socket: chat_message, chat_done, daemon_heartbeat, runtime_profiles_changed
```

**Flow:**
```
1. create agent_task_queue{status:'queued'}        (human assign OR autopilot)
2. server -> daemon: {type:'task_available', payload:{runtime_id, task_id}}   // HINT, not dispatch
   daemon -> server: HTTP POST /claim                                          // transactional claim
   -> status='dispatched', dispatched_at=now
3. daemon: mkdir isolated workdir; spawn CLI backend (see runtime distill); status='running', started_at=now
   for each agent step: daemon -> server {type:'task_message', payload:{seq:n++, type, tool, content,...}}
                        server persists in seq order + fans out to subscribed clients
   coarse: {type:'task_progress', payload:{summary, step, total}}
4. done: daemon -> server {type:'task_completed', payload:{pr_url, output}}
   -> status='completed', result=..., completed_at=now   (or 'failed', error=...)
```

## Data contracts
- Status enum: `queued | dispatched | running | completed | failed | cancelled`.
- Every transcript event: `(seq:int, type:'text'|'tool_use'|'tool_result'|'error', tool, content, input, output)`.
- WS envelope: `{ type:string, payload:json }`. Dispatch hint vs HTTP claim are distinct steps.

## Dependencies & assumptions
- A persistent server↔daemon WebSocket (gorilla/websocket) + an HTTP claim endpoint.
- A relational DB owning the task row (server is source of truth; daemon executes).
- The runtime/CLI-backend layer to actually run the agent (separate distill).
- Clients subscribe per-task (or via a hub) to receive the fanned-out `task_message` stream.

## To port this, you need:
- [ ] A task table with the `queued→dispatched→running→completed|failed|cancelled` enum + timestamps.
- [ ] A WS envelope `{type, payload}` multiplexing task/chat/heartbeat messages.
- [ ] A **wakeup-hint + transactional-claim** split: WS nudges, HTTP claim moves to `dispatched`.
- [ ] Typed transcript events with a **monotonic `seq`** per task (text/tool_use/tool_result/error).
- [ ] Server-side ordered persistence + fan-out to subscribed clients.
- [ ] Isolated per-task workdir; completion event carrying result (e.g. `pr_url`, `output`).

## Gotchas
- **Never treat the WS dispatch as authoritative.** If you dispatch over the socket and it drops, the
  task is lost. Use the socket only to wake the daemon; claim via a transactional HTTP call.
- **`seq` is not optional.** Without monotonic ordering you can't reconcile reconnects or persist a
  correct transcript — out-of-order tool_result/text corrupts the rendered run.
- **The status row lives on the server, the work on the daemon** — every transition is a cross-process
  handoff; design for the daemon dying mid-`running` (the row must be reclaimable/failable).
- **Don't stream raw stdout** — normalize to typed events (text/tool_use/tool_result/error) or the UI
  can't render structured activity and you lose tool-call visibility.
- **Isolate and GC workdirs** — concurrent tasks sharing a dir corrupt each other; mark dirs for GC.
- **Cancellation must reach the spawned process**, not just flip the DB row — wire cancel through to
  killing the CLI subprocess.

## Origin (reference only)
- Repo: https://github.com/multica-ai/multica
- `server/pkg/protocol/messages.go` (all WS payloads incl. `TaskMessagePayload.Seq`),
  `server/migrations/001_init.up.sql` (`agent_task_queue` status enum), `022_task_lifecycle_guards`,
  `server/internal/daemonws/{hub.go,notifier.go}` (server↔daemon WS hub),
  `server/internal/realtime/*` (client fan-out: broadcaster, hub, redis_relay, sharded_stream_relay),
  `server/internal/daemon/*` (claim, spawn, stream). Docs: `CLI_AND_DAEMON.md`.
- **Verify before relying on:** exact cancellation/reconnection-replay semantics and whether the
  client fan-out replays buffered `seq` ranges on reconnect (the `realtime` package has a redis_relay
  + sharded_stream_relay suggesting buffered replay, but the replay path was not read line-by-line) —
  confirm in `internal/realtime` before depending on replay guarantees.
