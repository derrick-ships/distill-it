# excalidraw

**Source:** https://github.com/excalidraw/excalidraw  
**Product:** Open-source virtual hand-drawn-style whiteboard. Infinite canvas, sketchy aesthetic, real-time collaboration that is end-to-end encrypted, local-first/offline (PWA). Hosted at excalidraw.com; also shipped as the `@excalidraw/excalidraw` React npm package embedded by Notion, Replit, CodeSandbox, Google Cloud, Meta, and others.  
**Stack:** TypeScript (pnpm monorepo), React, Vite, Rough.js (hand-drawn rendering), perfect-freehand (pencil strokes), socket.io (collab relay), Firebase Firestore + Storage (encrypted persistence), Web Crypto (AES-GCM), jotai. Packages: `common`, `element`, `excalidraw`, `math`, `utils`, `fractional-indexing`; app in `excalidraw-app/`.  
**Date distilled:** 2026-06-17

## Features extracted

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Hand-Drawn Rendering | rendering | [study](../features/rendering/study/hand-drawn-rendering--from-excalidraw.md) | [build](../features/rendering/build/hand-drawn-rendering--from-excalidraw.md) |
| E2E-Encrypted Collaboration | realtime-collab | [study](../features/realtime-collab/study/e2e-encrypted-collaboration--from-excalidraw.md) | [build](../features/realtime-collab/build/e2e-encrypted-collaboration--from-excalidraw.md) |
| Scene Reconciliation | realtime-collab | [study](../features/realtime-collab/study/scene-reconciliation--from-excalidraw.md) | [build](../features/realtime-collab/build/scene-reconciliation--from-excalidraw.md) |
| Fractional Indexing (z-order) | data-structures | [study](../features/data-structures/study/fractional-indexing--from-excalidraw.md) | [build](../features/data-structures/build/fractional-indexing--from-excalidraw.md) |

## Not yet distilled (candidates)

- Local-first persistence & autosave (LocalStorage scene + IndexedDB files, PWA) — domain `persistence`
- Freehand drawing via perfect-freehand (pressure → variable-width filled polygons) — domain `rendering`
- Arrow binding (arrows that stick to shapes, focus/gap geometry) — domain `canvas-interaction`
- Export pipeline (PNG/SVG/clipboard; scene JSON embedded back into the PNG) — domain `export`
- Immutable element data model (`version`/`versionNonce`/`seed`/`updated` discipline) — domain `data-model`
