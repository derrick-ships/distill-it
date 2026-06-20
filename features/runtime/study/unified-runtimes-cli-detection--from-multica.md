# Unified Runtimes + CLI Auto-Detection — from [multica](https://github.com/multica-ai/multica)

> Domain: [[_domain]] · Source: https://github.com/multica-ai/multica · NotebookLM: <link once added>

## What it does

Multica runs a small local **daemon** on your machine that figures out which AI coding CLIs you
already have installed — Claude Code, Codex, Copilot CLI, Gemini, Cursor Agent, OpenCode, OpenClaw,
Hermes, Pi, Kimi, Kiro — and registers each one as an available "runtime." The web dashboard then
shows all of them (plus cloud compute) in one place, so assigning a task to "the Codex agent on my
laptop" is a dropdown choice. You don't configure providers by hand; the daemon detects them.

## Why it exists

The agent-CLI landscape is fragmented: a dozen tools, each with its own binary name, its own
streaming format, its own model flags. Most products pick one. Multica's pitch is to be the *manager*
over all of them, which means it has to (a) discover whatever the user has, with zero config, and (b)
normalize each one behind a common interface so the rest of the system treats "run a task" uniformly
regardless of which CLI actually does the work. Auto-detection is what makes the "unified" promise
real instead of a setup chore.

## How it actually works

On `multica daemon start`, the daemon probes for each supported CLI by its binary name on your PATH
(`claude`, `codex`, `copilot`, `opencode`, `openclaw`, `hermes`, `gemini`, `pi`, `cursor-agent`,
`kimi`, `kiro-cli`). Each one also honors an env override, `MULTICA_<NAME>_PATH`, which points at an
absolute binary so non-standard installs still work. Whatever it finds, it registers with the server
as `RuntimeInfo { type, version, status }` in the `DaemonRegisterPayload`, advertising the available
runtimes per workspace. On clean shutdown it deregisters them, so the server knows immediately a
machine went away (rather than waiting for a heartbeat to expire).

Behind each CLI is a **backend** implementing a common interface — the daemon maps the agent type to
a concrete backend (`claudeBackend`, `codexBackend`, `copilotBackend`, …) that knows that CLI's
invocation: its binary, its args, and crucially its *output protocol*. These differ a lot: Claude and
Gemini speak `stream-json`, Codex runs an `app-server`, Hermes/Kimi/Kiro speak `acp`, Copilot/
OpenClaw/OpenCode/Pi emit plain JSON. The backend's job is to translate that CLI-native stream into
Multica's uniform task-message events. Per-CLI knobs ride on env vars: `MULTICA_<NAME>_MODEL` to pin
a model, `MULTICA_<NAME>_ARGS` (Claude/Codex) for extra flags parsed with POSIX shell-word quoting,
and argument layering goes hardcoded-defaults → daemon env defaults → per-task `custom_args`.

The daemon also keeps liveness going: it polls the server (~3s) for claimed tasks and heartbeats
(~15s). When a task arrives it creates an isolated workspace dir under `~/multica_workspaces`
(tracked with a `.gc_meta.json` marker for later garbage collection), spawns the right CLI backend
there, and streams output back. "Cloud" runtimes are the same abstraction from the server's side; the
dashboard simply aggregates local daemons and cloud compute into one runtime list.

## The non-obvious parts

- **Binary names are full of traps.** Cursor is `cursor-agent` (the headless mode), *not* `cursor`.
  Kiro is `kiro-cli`, not `kiro`. Probe the wrong name and you silently "don't have" the tool.
- **Detection is PATH-based but overridable per CLI.** `MULTICA_<NAME>_PATH` is an absolute path that
  *replaces* the lookup — it's not a directory prepended to PATH.
- **The hard part isn't detection, it's the output protocols.** Eleven CLIs, ~five different streaming
  formats (stream-json, app-server, acp, plain json). Each backend exists mostly to normalize that.
- **Model defaults are deliberately *not* guessed.** When no model is set, the daemon passes `""` and
  lets each CLI resolve its own default — the local account/environment knows better than a static map.
- **Copilot's model override is best-effort** — GitHub routes models by account entitlement, so
  `MULTICA_COPILOT_MODEL` "may not be honoured."
- **Deregister-on-shutdown, not just heartbeat-expiry.** Clean stops tell the server right away;
  liveness timeouts are only the backstop.
- **Profiles isolate daemons.** Multiple daemons on one box (`--profile`) get separate config, state,
  health port, and workspace root — they don't share detected runtimes.

## Related
- [[autonomous-execution-lifecycle--from-multica]] (what the detected runtime actually executes)
- [[agents-as-teammates--from-multica]] (an `agent` row is `runtime_mode` local|cloud + `runtime_config`)
- [[mcp-sidecar-auto-detection--from-asyar]] (a sibling "auto-detect installed tooling" pattern)
- [[provider-agnostic-model-layer--from-scrapegraph-ai]] (normalizing many providers behind one shape)
