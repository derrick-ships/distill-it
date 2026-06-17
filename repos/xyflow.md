# xyflow

- **Source:** https://github.com/xyflow/xyflow
- **Product:** Open-source libraries for building node-based UIs — flowcharts, diagram editors, no-code pipelines. Ships **React Flow** (`@xyflow/react`) and **Svelte Flow** (`@xyflow/svelte`), both built on a shared framework-agnostic engine (`@xyflow/system`).
- **Stack:** TypeScript · d3-zoom / d3-drag / d3-selection / d3-interpolate · Zustand (React) · Svelte stores · Turbo + pnpm monorepo
- **License:** MIT
- **Date distilled:** 2026-06-17

## Architecture in one breath
A pnpm/Turbo monorepo with four packages: `@xyflow/react` (v12), `reactflow` (legacy v11), `@xyflow/svelte`, and `@xyflow/system` (the shared core). The clever part is the **core/adapter split**: all the hard math and every interaction engine live in the framework-free `@xyflow/system` package as `XY*` factories (`XYPanZoom`, `XYDrag`, `XYHandle`, `XYResizer`, `XYMinimap`) plus pure helpers (edge-path functions, `adoptUserNodes`, `updateAbsolutePositions`). React Flow and Svelte Flow are thin reactive shells over that one core — a bug fix in system fixes both. Everything keys off a single viewport transform `[x, y, zoom]` that projects world coordinates to screen.

## Features distilled

| Feature | Domain | Study | Build |
|---|---|---|---|
| Pan & Zoom Canvas (`XYPanZoom`) | canvas-interaction | [study](../features/canvas-interaction/study/pan-zoom-canvas--from-xyflow.md) | [build](../features/canvas-interaction/build/pan-zoom-canvas--from-xyflow.md) |
| Node Dragging (`XYDrag`) | canvas-interaction | [study](../features/canvas-interaction/study/node-dragging--from-xyflow.md) | [build](../features/canvas-interaction/build/node-dragging--from-xyflow.md) |
| Minimap Navigation (`XYMinimap`) | canvas-interaction | [study](../features/canvas-interaction/study/minimap-navigation--from-xyflow.md) | [build](../features/canvas-interaction/build/minimap-navigation--from-xyflow.md) |
| Connection Handles (`XYHandle`) | graph-editing | [study](../features/graph-editing/study/connection-handles--from-xyflow.md) | [build](../features/graph-editing/build/connection-handles--from-xyflow.md) |
| Node Resizer (`XYResizer`) | graph-editing | [study](../features/graph-editing/study/node-resizer--from-xyflow.md) | [build](../features/graph-editing/build/node-resizer--from-xyflow.md) |
| Edge Path Algorithms (bezier/step/straight) | graph-rendering | [study](../features/graph-rendering/study/edge-path-algorithms--from-xyflow.md) | [build](../features/graph-rendering/build/edge-path-algorithms--from-xyflow.md) |
| Reactive Store Architecture | state-management | [study](../features/state-management/study/reactive-store--from-xyflow.md) | [build](../features/state-management/build/reactive-store--from-xyflow.md) |

## Source files (reference only — repo may be gone later)
- `packages/system/src/xypanzoom/` — `XYPanZoom.ts`, `utils.ts`, `filter.ts`, `eventhandler.ts` (d3-zoom wrapper).
- `packages/system/src/xydrag/XYDrag.ts` + `utils.ts` — node dragging (d3-drag), snap, auto-pan, multi-drag.
- `packages/system/src/xyhandle/XYHandle.ts` + `utils.ts` — drag-to-connect, closest-handle, validity.
- `packages/system/src/xyresizer/XYResizer.ts` + `utils.ts` — resize handles, aspect/min/max, parent/child extents.
- `packages/system/src/xyminimap/index.ts` — minimap gesture forwarding.
- `packages/system/src/utils/edges/{bezier,smoothstep,straight}-edge.ts` — pure SVG path functions.
- `packages/react/src/store/index.ts` — Zustand store + actions; `packages/system/src/utils/` — `adoptUserNodes`, `updateAbsolutePositions`.

## Cloneability verdict
The interaction engines (pan/zoom, drag, connect, resize) are essentially thin, careful wrappers over d3 — the *value is in the carefulness* (threshold in screen space, DOM-priority hit-testing, group-snap-as-unit, corner-anchoring), not novel algorithms. The **edge-path functions are commodity and the single best copy-paste target** (pure, ~150 lines, zero deps). The genuine moat is the **core/adapter split** that lets one team ship two production libraries from one logic core — that's an architecture discipline more than code. An LLM-assisted rebuild of any single feature here is a day or two; replicating the whole dual-runtime ecosystem with the polish is months.
