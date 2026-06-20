# Unified Runtimes + CLI Auto-Detection (build spec) — distilled from multica

## Summary

A local daemon auto-detects installed agent CLIs by probing binary names on PATH (with per-CLI env
overrides), registers each as a "runtime" with the server, and wraps each behind a common **backend
interface** that normalizes the CLI's native streaming output into uniform task-message events. The
server aggregates local daemons + cloud compute into one runtime list. Go, but the
detect→register→normalize pattern is language-agnostic.

## Core logic (inlined)

**Supported CLIs — probe name → backend → output protocol:**
```
agent type   binary probed     backend            native output protocol
-----------  ----------------  -----------------  ----------------------
claude       claude            claudeBackend      stream-json
codex        codex             codexBackend       app-server
copilot      copilot           copilotBackend     json
opencode     opencode          opencodeBackend    opencode run (json)
openclaw     openclaw          openclawBackend    json
hermes       hermes            hermesBackend      acp
gemini       gemini            geminiBackend      stream-json
pi           pi                piBackend          json mode
cursor       cursor-agent      cursorBackend      stream-json   (binary is cursor-agent, NOT cursor)
kimi         kimi              kimiBackend        acp
kiro         kiro-cli          kiroBackend        acp           (binary is kiro-cli, NOT kiro)
```

**Detection (daemon start):**
```go
for each agentType:
    path := os.Getenv("MULTICA_"+UPPER(name)+"_PATH")   // absolute override; replaces lookup
    if path == "": path, err = exec.LookPath(binaryName) // PATH probe
    if err == nil: detected = append(detected, RuntimeInfo{Type: agentType, Version: probeVersion(path), Status:"available"})
// register with server:
send DaemonRegisterPayload{ DaemonID, AgentID, Runtimes: detected }   // over WebSocket on connect
// on clean shutdown: deregister all (don't wait for heartbeat expiry)
```

**Backend interface (the normalization layer):**
```go
// agent type -> concrete backend (switch in pkg/agent/agent.go newBackend):
//   "claude" -> &claudeBackend{cfg}, "codex" -> &codexBackend{cfg}, ... etc.
type Backend interface {
    // builds argv for this CLI, runs it in workdir, parses its native stream,
    // and emits uniform events (text | tool_use | tool_result | error).
    Execute(ctx, task, workdir) (<-chan TaskMessage, error)
}
// argument layering order (lowest -> highest precedence):
//   hardcoded Multica defaults  <  MULTICA_<NAME>_ARGS (env, POSIX shellword-parsed; Claude/Codex only)
//                               <  per-task custom_args
// model: MULTICA_<NAME>_MODEL pins a model; empty => pass "" so the CLI resolves its own default.
```

**Daemon liveness + task pickup:**
```
poll server every ~3s (MULTICA_DAEMON_POLL_INTERVAL) for claimed tasks
heartbeat every ~15s (MULTICA_DAEMON_HEARTBEAT_INTERVAL)
max concurrent tasks ~20 (MULTICA_DAEMON_MAX_CONCURRENT_TASKS)
on task: mkdir isolated workdir under MULTICA_WORKSPACES_ROOT (~/multica_workspaces) + .gc_meta.json marker
         pick backend by agent type -> Execute() -> stream events back to server
orphan GC: dirs lacking .gc_meta.json are eligible after MULTICA_GC_ORPHAN_TTL (~72h)
profiles: --profile gives separate config dir / state / health port / workspace root (no shared runtimes)
```

## Data contracts
```go
type RuntimeInfo struct { Type string; Version string; Status string }      // one detected runtime
type DaemonRegisterPayload struct { DaemonID, AgentID string; Runtimes []RuntimeInfo }
// agent DB row carries the binding:
//   agent.runtime_mode  TEXT CHECK (runtime_mode IN ('local','cloud'))
//   agent.runtime_config JSONB  -- which CLI/model/args this agent uses
```

## Dependencies & assumptions
- A PATH lookup primitive (`exec.LookPath`) + process spawn (`exec.Command`).
- A persistent daemon↔server channel (WebSocket here) to register/deregister + receive wakeups.
- Per-CLI knowledge: binary name, argv shape, and how to parse that CLI's streaming output.
- A POSIX shell-word parser for the `_ARGS` env vars.

## To port this, you need:
- [ ] A registry mapping agent type → {binary name, env-override key, backend, output protocol}.
- [ ] A detection pass: env override first, else PATH lookup; collect `{type, version, status}`.
- [ ] A register/deregister handshake with your server (advertise runtimes; deregister on clean exit).
- [ ] A `Backend` interface per CLI that builds argv, runs it, and **normalizes its native stream** into
      your uniform event type (text/tool_use/tool_result/error).
- [ ] Argument layering: hardcoded < env defaults < per-task overrides; empty model => let CLI default.
- [ ] Isolated per-task workdirs + a GC marker file; poll + heartbeat for liveness.

## Gotchas
- **Wrong binary names silently disable tools.** `cursor-agent` not `cursor`; `kiro-cli` not `kiro`.
- **Env override is an absolute file path, not a PATH dir** — it replaces `LookPath`, doesn't augment it.
- **The real work is protocol normalization,** not detection. Budget most effort for parsing ~5
  different streaming formats into one event shape. A detector that finds CLIs but can't normalize
  their output is useless.
- **Don't hardcode model defaults** — pass empty and let each CLI pick; static guesses go stale and
  may not match the user's account/entitlement (esp. Copilot, which ignores model overrides).
- **Deregister on shutdown** so the server reacts immediately; heartbeat-expiry is only a backstop.
- **Isolate workdirs and mark them** (`.gc_meta.json`) or orphan dirs accumulate; GC keys on the
  marker's absence, not process liveness.

## Origin (reference only)
- Repo: https://github.com/multica-ai/multica
- `server/pkg/agent/agent.go` (CLI list, agent-type→backend switch, per-CLI output-protocol map),
  `server/pkg/agent/models.go` (Model/Thinking shapes), `server/internal/daemon/*` (daemon, config,
  execenv, gc, identity), `server/pkg/protocol/messages.go` (`RuntimeInfo`, `DaemonRegisterPayload`).
  Docs: `CLI_AND_DAEMON.md`, `CLI_INSTALL.md`.
- **Verify before relying on:** the exact detection function (confirmed PATH-based via `exec.LookPath`
  pattern + env overrides from docs, but the precise probe loop in `internal/daemon` was not read
  line-by-line) and whether a version command runs post-detection (not confirmed). Also: a 12th/13th
  type (codebuddy, antigravity) appears in the error string — confirm the full live list in `agent.go`.
