# Multica — origin index

- **Source:** https://github.com/multica-ai/multica
- **What it is:** An open-source platform for managing AI coding agents as autonomous teammates. You
  assign issues to agents like colleagues; they pick them up, execute autonomously with live progress,
  report blockers, run on a schedule (Autopilots), and accrue reusable skills. Agents and humans share
  the same issue/comment/board primitives.
- **Author:** Multica (multica-ai) · **License:** see repo · self-hostable
- **Stack:** Next.js 16 (App Router) frontend + Electron desktop + React Native mobile · **Go**
  backend (Chi router, sqlc, gorilla/websocket) · **PostgreSQL 17** + pgvector · a local **daemon**
  that auto-detects and runs agent CLIs (Claude Code, Codex, Copilot, Gemini, Cursor Agent, OpenCode,
  OpenClaw, Hermes, Pi, Kimi, Kiro) · Redis relay for realtime fan-out.
- **Date distilled:** 2026-06-20
- **Architecture in one line:** a server owns issues/agents/tasks in Postgres and orchestrates a
  generic DB-backed cron scheduler (`sys_cron_executions`) for Autopilots; a local daemon claims tasks
  over HTTP (woken by a WebSocket hint), spawns the right CLI backend in an isolated workspace, and
  streams typed, `seq`-numbered transcript events back over one multiplexed socket — with agents acting
  as first-class teammates via actor-polymorphic (`member|agent`) records.

## Features extracted
| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Autopilot — Scheduled/Triggered Agent Work | pipeline-orchestration | [study](../features/pipeline-orchestration/study/autopilot-scheduled-work--from-multica.md) | [build](../features/pipeline-orchestration/build/autopilot-scheduled-work--from-multica.md) |
| Unified Runtimes + CLI Auto-Detection | runtime | [study](../features/runtime/study/unified-runtimes-cli-detection--from-multica.md) | [build](../features/runtime/build/unified-runtimes-cli-detection--from-multica.md) |
| Agents as Teammates | agent-architecture | [study](../features/agent-architecture/study/agents-as-teammates--from-multica.md) | [build](../features/agent-architecture/build/agents-as-teammates--from-multica.md) |
| Autonomous Execution Lifecycle + WS Streaming | agent-architecture | [study](../features/agent-architecture/study/autonomous-execution-lifecycle--from-multica.md) | [build](../features/agent-architecture/build/autonomous-execution-lifecycle--from-multica.md) |

## Verification gaps flagged in build docs (check before transplant)
- **Autopilot:** the due-trigger→issue+task dispatch handler was inferred from schema + the scheduler
  contract, not read line-by-line.
- **Runtimes/CLI:** exact detection probe loop in `internal/daemon` not read line-by-line; post-detect
  version-gating unconfirmed; full live CLI list (codebuddy/antigravity appear in an error string).
- **Agents-as-teammates:** the server handler that raises the `action_required` inbox item on a blocker
  was inferred from schema + the agent skill doc, not read as one function.
- **Execution lifecycle:** cancellation + reconnect-replay semantics (the `realtime` redis_relay /
  sharded_stream_relay) not read line-by-line.

## Note on method
Distilled via a disposable shallow local clone (read-only) after web-fetch exploration proved
cost-prohibitive on this large Go monorepo — the skill's sanctioned accelerator path.
