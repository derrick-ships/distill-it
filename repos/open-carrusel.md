# open-carrusel

**Source**: https://github.com/Hainrixz/open-carrusel
**Product**: AI-powered, local-first tool for designing Instagram carousels by chatting with Claude. You describe what you want, the Claude Code CLI (running as a local subprocess) generates HTML/CSS slides, and you export them as pixel-perfect PNGs at exact Instagram dimensions — zipped, ready to post. No cloud, no API key, no vendor lock-in.
**Stack**: Next.js 16, React 19, TypeScript 5, Tailwind CSS v4, Radix UI, lucide-react, dnd-kit (drag/reorder), Claude Code CLI (agent), Puppeteer + Sharp (PNG export), async-mutex (storage). Data is plain JSON files in `data/`.
**Distilled**: 2026-06-18

## What it is

A thin, local-first web shell around the Claude Code CLI. The browser talks to a localhost Next.js server; each chat message spawns `claude -p ... --output-format stream-json` as a subprocess, streams its tokens back over SSE, and lets the agent author slides by `curl`-ing HTML into the app's own REST API (using the Bash + WebFetch tools — no custom tool protocol). Slides are body-level HTML rendered identically in a live preview iframe and in headless Chromium for export. The whole thing leans on "you already have Claude Code, so this is free to run."

The most transplant-worthy ideas here are architectural, not carousel-specific: how to drive an app with a local Claude CLI subprocess, how to guarantee preview/export pixel parity, how to gate agent mutations behind a review queue, and how to persist state safely without a database.

## Features distilled

### agent-architecture
| Feature | Study | Build |
|---------|-------|-------|
| Claude CLI Subprocess Agent | [study](../features/agent-architecture/study/cli-subprocess-agent--from-open-carrusel.md) | [build](../features/agent-architecture/build/cli-subprocess-agent--from-open-carrusel.md) |

### rendering
| Feature | Study | Build |
|---------|-------|-------|
| HTML→PNG Slide Export | [study](../features/rendering/study/html-to-png-export--from-open-carrusel.md) | [build](../features/rendering/build/html-to-png-export--from-open-carrusel.md) |

### agent-guardrails
| Feature | Study | Build |
|---------|-------|-------|
| Staged Actions Confirmation Queue | [study](../features/agent-guardrails/study/staged-actions-queue--from-open-carrusel.md) | [build](../features/agent-guardrails/build/staged-actions-queue--from-open-carrusel.md) |

### state-management
| Feature | Study | Build |
|---------|-------|-------|
| JSON File Store with Async-Mutex | [study](../features/state-management/study/json-mutex-store--from-open-carrusel.md) | [build](../features/state-management/build/json-mutex-store--from-open-carrusel.md) |

## Not yet distilled (candidates)

- **Brand configuration system** (design-systems) — colors/fonts/logo/style-keywords in `brand.json`, fed into the agent's system prompt.
- **Template save & reuse** (folds into state-management) — persist a slide/carousel as a reusable template.
- **Three-panel editor + dnd-kit filmstrip** (canvas-interaction) — drag-reorderable slide strip, live preview, safe-zone overlay.
- **Per-slide version history / undo** (state-management) — version stack per slide.
