# tldraw — origin index

- **Source:** https://github.com/tldraw/tldraw
- **What it is:** An open-source React SDK for building infinite-canvas applications — collaborative
  whiteboards, diagramming, and drawing tools. A feature-complete canvas engine (DOM-based
  rendering, custom shapes/tools/bindings, real-time multiplayer, AI primitives) used in production
  by Google, Shopify, Autodesk, ClickUp, Replit, and others. Free for development; production use
  needs a license key.
- **Stack:** TypeScript + React monorepo. Home-grown signals reactivity (`@tldraw/state`) →
  reactive record store (`@tldraw/store`) → typed schema + migrations (`@tldraw/tlschema`,
  `@tldraw/validate`) → editor (`@tldraw/editor`, `tldraw`) → multiplayer sync (`@tldraw/sync-core`,
  `@tldraw/sync`, reference server on Cloudflare Durable Objects).
- **Date distilled:** 2026-06-17
- **Architecture in one line:** signals (epoch-clocked, diff-carrying) → normalized reactive record
  store (diffs tagged user/remote) → versioned bidirectional migrations → server-authoritative
  optimistic-rebase multiplayer over WebSockets.

## Features extracted
| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Signals Reactivity Engine | reactivity | [study](../features/reactivity/study/signals-reactivity-engine--from-tldraw.md) | [build](../features/reactivity/build/signals-reactivity-engine--from-tldraw.md) |
| Reactive Record Store | state-management | [study](../features/state-management/study/reactive-record-store--from-tldraw.md) | [build](../features/state-management/build/reactive-record-store--from-tldraw.md) |
| Schema & Migrations | schema-migrations | [study](../features/schema-migrations/study/schema-migrations--from-tldraw.md) | [build](../features/schema-migrations/build/schema-migrations--from-tldraw.md) |
| Multiplayer Sync | realtime | [study](../features/realtime/study/multiplayer-sync--from-tldraw.md) | [build](../features/realtime/build/multiplayer-sync--from-tldraw.md) |

## Not yet distilled (candidates)
- **Custom shapes / ShapeUtil system** (`@tldraw/editor`) — the plugin model for shapes: geometry,
  rendering, hit-testing, lifecycle → domain: `extensibility`
- **Bindings system** (`@tldraw/editor`) — declarative relationships between shapes (arrow↔node) that
  survive moves/deletes → domain: `extensibility`
- **Tool state-chart** (`@tldraw/editor`) — hierarchical state machine driving every interaction
  (idle→pointing→dragging) → domain: `state-machine`
- **Infinite canvas rendering** (`@tldraw/editor`) — camera/viewport math, coordinate spaces, culling,
  DOM shape rendering → domain: `canvas-rendering`
- **Local-first persistence** (`@tldraw/store` + sync) — IndexedDB snapshot/incremental persistence
  with cross-tab coordination → domain: `persistence`
- **AI primitives + agent template** (`ai` + `templates/agent`, `templates/workflow`) — driving the
  canvas with an LLM → domain: `ai-integration`
- **Asset/embed system** — external content (images, YouTube, Figma) as canvas shapes → domain: `embeds`

## Verification gaps flagged in build docs (check before transplant)
- Exact throttle/`SYNC_FPS` constants and health-check intervals — multiplayer-sync build (stated as
  ~5s ping / ~10s health-check from the source summary; confirm against current `TLSyncClient.ts`).
- Exact `MAX_TOMBSTONES` value and pruning trigger — multiplayer-sync build (build doc uses 3000 as a
  representative cap; confirm in `TLSyncRoom.ts`).
- The precise `sortMigrations` tie-break (distance-minimizing Kahn) — schema-migrations build
  (behavior captured; exact scoring heuristic should be re-read from `migrate.ts` if order-sensitive).
- `ArraySet` array→Set promotion threshold — signals build (stated ~8; confirm in `ArraySet.ts`).
