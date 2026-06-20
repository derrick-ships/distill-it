# Autonomous Execution Lifecycle + WebSocket Streaming — from [multica](https://github.com/multica-ai/multica)

> Domain: [[_domain]] · Source: https://github.com/multica-ai/multica · NotebookLM: <link once added>

## What it does

When an issue is assigned to an agent, Multica runs it end to end without a human babysitting: the
task is queued, a local daemon claims it, spawns the agent CLI in an isolated workspace, and streams
every step — each text chunk, tool call, and tool result — live to the dashboard over WebSocket. You
watch the agent work in real time, and when it's done the result (often a PR link) is persisted.

## Why it exists

Autonomy without visibility is unusable — you won't trust an agent you can't watch. The lifecycle's
job is twofold: reliably move a task from "assigned" to "done/failed" across a server and a separate
machine (the daemon), and make the in-between *legible* by streaming the agent's reasoning and actions
as they happen. The split between a server (orchestration, persistence) and a daemon (actual
execution on your hardware) is what lets the agent use your local tools and credentials while the
server stays the source of truth.

## How it actually works

The unit of execution is an `agent_task_queue` row with a status machine: `queued → dispatched →
running → completed | failed | cancelled`. The server and daemon talk over a WebSocket whose envelope
is `Message { type, payload }`. The flow:

1. A task is created (by a human assigning an issue, or by an autopilot) as `queued`.
2. The server notifies the daemon with a lightweight `task_available` *wakeup hint* — but the daemon
   still **claims** work through the existing HTTP claim endpoint (the WS message is just a nudge, not
   the dispatch itself). On claim, the task moves to `dispatched`.
3. The daemon creates an isolated workspace dir, spawns the right agent CLI backend, and the task goes
   `running`. As the CLI emits output, the daemon translates it into `task_message` events — each with
   a monotonically increasing `seq`, a `type` of `text | tool_use | tool_result | error`, and the tool
   name/input/output — and streams them to the server, which fans them out to subscribed clients.
4. Coarse progress rides on `task_progress` (`summary`, `step`/`total`); completion is a
   `task_completed` event carrying `pr_url` and final `output`. The task row goes `completed` (or
   `failed`), with `result`/`error` persisted.

The `seq` number on every message is the backbone of correctness: because messages are ordered and
numbered, a client that connects late or reconnects can be brought up to date deterministically, and
the server can persist the transcript in order. The same WebSocket carries chat (`chat_message`,
`chat_done`) and daemon liveness (`daemon_heartbeat`) — it's one multiplexed channel per the
`protocol` package, not a socket per concern.

## The non-obvious parts

- **The WS dispatch is a hint; HTTP is the source of truth.** `task_available` only wakes the daemon;
  the daemon claims via HTTP. This avoids losing work if the socket blips — the claim is transactional.
- **`seq` makes the stream replayable.** Every `task_message` is numbered, so ordering and catch-up
  are deterministic rather than best-effort.
- **Two machines, one state machine.** The status enum (`queued→dispatched→running→…`) is shared
  across the server (owns the row) and the daemon (does the work); each transition is a handoff.
- **Events are typed, not raw logs.** `text | tool_use | tool_result | error` (plus tool name/input/
  output) means the UI renders structured agent activity, not a flat stdout dump.
- **Isolated workspace per task.** Each run gets its own dir (GC-tracked), so concurrent tasks and
  cleanup don't collide.
- **One multiplexed socket.** Tasks, chat, runtime-profile changes, and heartbeats all ride the same
  `Message{type,payload}` envelope.

## Related
- [[unified-runtimes-cli-detection--from-multica]] (provides the CLI backend this lifecycle runs)
- [[autopilot-scheduled-work--from-multica]] (one source of the tasks that enter this lifecycle)
- [[agents-as-teammates--from-multica]] (the issue/agent model the task executes against)
- [[resumable-streaming-search--from-scira]] (a different resumable-stream design — good contrast)
- [[stream-output-transcoding--from-vlc]] (streaming in a non-AI domain)
