# whatsapp-agentkit

**Source:** https://github.com/Hainrixz/whatsapp-agentkit
**Product:** A Claude-Code-native kit that lets a non-technical business owner build a complete, deployable WhatsApp AI customer-service bot in ~20 minutes by answering a guided interview — no coding.
**Distilled:** 2026-06-18

## What this repo actually is
The repo ships almost no runtime code. Its entire IP lives in two prompt files — `CLAUDE.md` (the "brain": persona, pinned stack, target architecture, and the full inline code templates for every generated file) and `.claude/commands/build-agent.md` (a thin slash command that runs a strict 5-phase flow). A `start.sh` checks prerequisites; `.env.example` enumerates the variables. The `agent/` application described in the README is **generated at runtime** by Claude Code from those templates — it does not exist in the repo. Stack of the generated app: FastAPI + Uvicorn, Anthropic Claude (`claude-sonnet-4-6`), SQLAlchemy (SQLite local / PostgreSQL prod), Meta Cloud API or Twilio for WhatsApp, Docker + Railway. The whole experience is conducted in Spanish.

## Features distilled

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Interview-driven app scaffolding | code-generation | [study](../features/code-generation/study/interview-driven-scaffolding--from-whatsapp-agentkit.md) | [build](../features/code-generation/build/interview-driven-scaffolding--from-whatsapp-agentkit.md) |
| WhatsApp provider adapter layer | messaging | [study](../features/messaging/study/whatsapp-provider-adapter--from-whatsapp-agentkit.md) | [build](../features/messaging/build/whatsapp-provider-adapter--from-whatsapp-agentkit.md) |
| Per-contact conversation memory | agent-architecture | [study](../features/agent-architecture/study/conversation-memory--from-whatsapp-agentkit.md) | [build](../features/agent-architecture/build/conversation-memory--from-whatsapp-agentkit.md) |

## Not yet distilled (candidates)
- **The Claude "brain" call** (`brain.py`) — load system prompt from YAML, build messages from history, call Claude with configurable fallback/error messages. (Covered briefly inside the scaffolding build doc.)
- **Use-case-conditional tools** (`tools.py`) — base `buscar_en_knowledge`/`obtener_horario` plus functions emitted per chosen use case (scheduling, orders, leads, support).
- **Knowledge-file inlining** — reading `/knowledge/*` and pasting contents verbatim into the system prompt (no RAG).
- **Railway deploy flow + dev/prod `.gitignore` swap** — the phase-5 hosting recipe.
