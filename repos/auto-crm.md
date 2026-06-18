# auto-crm

**Source**: https://github.com/Hainrixz/auto-crm
**Product**: Open-source, local-first, self-customizing CRM with AI-powered lead classification and an automated pipeline — runs entirely on your machine, no subscription, no cloud. Bilingual (Spanish-primary).
**Stack**: Next.js 16, React 19, TypeScript, Tailwind v4 + shadcn/ui, SQLite + Drizzle ORM (better-sqlite3), @dnd-kit, Recharts, optional Claude API (`@anthropic-ai/sdk`), built-in MCP server, Docker
**License**: MIT · **Distilled**: 2026-06-18

## What it is

A CRM you own. It stores contacts, deals, pipeline stages, and activities in a local SQLite file and
gives you the modern CRM surface — a drag-and-drop Kanban pipeline, a KPI dashboard, follow-up
triage, CSV import/export, and a webhook to auto-capture leads. Two things make it distinctive: (1)
it's **AI-operable** via a built-in MCP server that exposes the CRM as 10 tools to Claude
Desktop/Web, so you can run your pipeline by talking; and (2) it's **AI-customizable** via
`.claude/commands` that let Claude rewrite the schema/UI to fit your business instead of a settings
screen. Lead grading ships as a transparent rule-based scorer with an optional Claude classifier
layered on top (and falling back to) it.

## Features distilled

### lead-scoring
| Feature | Study | Build |
|---------|-------|-------|
| Rule-Based Lead Scoring | [study](../features/lead-scoring/study/rule-based-lead-scoring--from-auto-crm.md) | [build](../features/lead-scoring/build/rule-based-lead-scoring--from-auto-crm.md) |

### ai-integration
| Feature | Study | Build |
|---------|-------|-------|
| AI Lead Classification (Claude) | [study](../features/ai-integration/study/ai-lead-classification--from-auto-crm.md) | [build](../features/ai-integration/build/ai-lead-classification--from-auto-crm.md) |

### lead-ingestion
| Feature | Study | Build |
|---------|-------|-------|
| Webhook Lead Ingestion | [study](../features/lead-ingestion/study/webhook-lead-ingestion--from-auto-crm.md) | [build](../features/lead-ingestion/build/webhook-lead-ingestion--from-auto-crm.md) |

### agent-architecture
| Feature | Study | Build |
|---------|-------|-------|
| MCP CRM Server (10 tools) | [study](../features/agent-architecture/study/mcp-crm-server--from-auto-crm.md) | [build](../features/agent-architecture/build/mcp-crm-server--from-auto-crm.md) |

### canvas-interaction
| Feature | Study | Build |
|---------|-------|-------|
| Kanban Pipeline (drag-and-drop) | [study](../features/canvas-interaction/study/kanban-pipeline-dnd--from-auto-crm.md) | [build](../features/canvas-interaction/build/kanban-pipeline-dnd--from-auto-crm.md) |

### analytics
| Feature | Study | Build |
|---------|-------|-------|
| CRM Dashboard KPIs & Analytics | [study](../features/analytics/study/crm-dashboard-kpis--from-auto-crm.md) | [build](../features/analytics/build/crm-dashboard-kpis--from-auto-crm.md) |

### data-portability
| Feature | Study | Build |
|---------|-------|-------|
| CSV Import / Export | [study](../features/data-portability/study/csv-import-export--from-auto-crm.md) | [build](../features/data-portability/build/csv-import-export--from-auto-crm.md) |

### activity-tracking
| Feature | Study | Build |
|---------|-------|-------|
| Activity Tracking & Follow-up Buckets | [study](../features/activity-tracking/study/followup-buckets--from-auto-crm.md) | [build](../features/activity-tracking/build/followup-buckets--from-auto-crm.md) |

### agent-distribution
| Feature | Study | Build |
|---------|-------|-------|
| Self-Customizing CRM via Claude Code Commands | [study](../features/agent-distribution/study/self-customizing-crm--from-auto-crm.md) | [build](../features/agent-distribution/build/self-customizing-crm--from-auto-crm.md) |

## Notes & cross-repo context

- **AI-native CRM thesis** has two halves worth studying together: the [[mcp-crm-server--from-auto-crm]]
  *operates* the CRM via Claude, and [[self-customizing-crm--from-auto-crm]] *reshapes* it via Claude.
  Compare the latter to [[agent-driven-install--from-agent-reach]] — same "agent executes a markdown
  runbook" pattern.
- **Lead grading** is two interchangeable engines behind one write contract:
  [[rule-based-lead-scoring--from-auto-crm]] (deterministic, offline) and
  [[ai-lead-classification--from-auto-crm]] (optional Claude, falls back to the former).
- **Data model** (`src/db/schema.ts`): `contacts`, `pipelineStages`, `deals`, `activities`,
  `crmSettings` (key/value). Stages carry `isWon`/`isLost` flags that drive analytics.
- **Cloneability verdict**: the CRM CRUD + Kanban + dashboard is commodity (an LLM-assisted stack
  rebuilds it in days). The genuine differentiation is the AI-operable (MCP) + AI-customizable
  (commands) pairing and the local-first/no-subscription positioning — moat is the *integration
  story*, not any single feature.
