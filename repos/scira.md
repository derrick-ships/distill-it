# Scira — origin index

- **Source:** https://github.com/zaidmukaddam/scira
- **What it is:** An open-source AI research engine ("plans, retrieves, and cites — so you can think
  faster"). One chat box that decomposes a question into a plan, runs an autonomous agent over web/
  academic/X/Reddit/GitHub/finance sources across 17 search modes and ~28 tools, and returns a grounded
  answer with inline citations. Also schedules recurring "Lookout" research agents.
- **Author:** Zaid Mukaddam · **License:** AGPL-3.0 · self-hostable
- **Stack:** Next.js + React + Tailwind + Shadcn/UI · Vercel AI SDK (`ai`, `@ai-sdk/gateway`) over
  ~130 models / 22 providers · Exa / Firecrawl / Parallel / Tavily search · Daytona code sandbox ·
  Better Auth + DodoPayments/Polar · Drizzle ORM + Postgres · Redis/Upstash (rate limit, resumable
  streams) · QStash (scheduling) · Cloudflare R2 · ElevenLabs (voice).
- **Date distilled:** 2026-06-20
- **Architecture in one line:** one POST `/api/search` route resolves a model alias + a search-mode
  tool bundle, runs `streamText` (tiny outer loop) whose `extreme_search` tool runs a plan-then-execute
  research agent (big inner loop), buffers the answer through Redis for resumable/stoppable streaming,
  and cites sources inline by prompt — all reusable by QStash-scheduled Lookouts.

## Features extracted
| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Agentic Research Planning | research-automation | [study](../features/research-automation/study/agentic-research-planning--from-scira.md) | [build](../features/research-automation/build/agentic-research-planning--from-scira.md) |
| Grounded Retrieval + Inline Citations | structured-extraction | [study](../features/structured-extraction/study/grounded-retrieval-citations--from-scira.md) | [build](../features/structured-extraction/build/grounded-retrieval-citations--from-scira.md) |
| Multi-Provider Model Gateway | ai-integration | [study](../features/ai-integration/study/multi-provider-model-gateway--from-scira.md) | [build](../features/ai-integration/build/multi-provider-model-gateway--from-scira.md) |
| Tool & Search-Mode Registry | agent-architecture | [study](../features/agent-architecture/study/tool-and-search-mode-registry--from-scira.md) | [build](../features/agent-architecture/build/tool-and-search-mode-registry--from-scira.md) |
| Resumable Streaming Search | streaming | [study](../features/streaming/study/resumable-streaming-search--from-scira.md) | [build](../features/streaming/build/resumable-streaming-search--from-scira.md) |
| Scheduled Monitoring Agents (Lookouts) | pipeline-orchestration | [study](../features/pipeline-orchestration/study/scheduled-monitoring-agents--from-scira.md) | [build](../features/pipeline-orchestration/build/scheduled-monitoring-agents--from-scira.md) |

## Verification gaps flagged in build docs (check before transplant)
- **Agentic Research Planning:** inner agent tool schemas (`webSearch/browsePage/xSearch/codeRunner/
  done`) confirmed to emit events but not read field-by-field.
- **Tool & Search-Mode Registry:** full inline name→factory `streamTools` map in `route.ts` only
  partially read.
- **Resumable Streaming:** Redis key/value layout (internal to `ai-resumable-stream`) and client-side
  resume wiring not read.
- **Lookouts:** exact QStash call signature, `verifySignature` wiring, `time-utils.ts` cron generation,
  email provider, and monthly/yearly cron strings not confirmed.
- **Grounded Citations:** whether sources are surfaced as a separate sidebar vs only inline not confirmed.
