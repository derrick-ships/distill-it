# penpot

- **Source:** https://github.com/penpot/penpot
- **Product:** Open-source design & prototyping platform — a self-hostable, open-standards Figma
  alternative for teams building digital products. Real-time collaboration, native design tokens,
  components & variants, CSS Grid/Flex layout, inspect-mode code (SVG/CSS/HTML), a plugin system, and
  an MCP server. Designs are stored in open formats (SVG/JSON), "you own your data."
- **Stack:** Clojure / ClojureScript (frontend, backend, common, exporter) · Rust → WebAssembly
  (render-wasm, on Skia via rust-skia) · shadow-cljs · SCSS · pnpm workspace · deps.edn · Docker.
- **License:** MPL 2.0
- **Date distilled:** 2026-06-18

## Architecture in one breath
A Clojure-everywhere monorepo: `frontend` (CLJS app), `backend` (Clojure server), `common`
(`.cljc` shared between them — the file model, change system, tokens), `exporter` (headless render
service), `render-wasm` (Rust+Skia canvas engine), `plugins` (sandboxed plugin runtime), and `mcp`.
The conceptual spine is the **change-based file model in `common`**: a design file is never mutated
directly — every edit is a serializable `change` applied through a dispatch table, built together
with its inverse, so undo, persistence, and realtime collab all reduce to replaying change lists.
Design tokens and components are layered on that same model. Rendering is being moved off SVG/DOM
into the Rust→WASM Skia engine for scale.

## Features distilled

| Feature | Domain | Study | Build |
|---|---|---|---|
| Change-Based Document Mutation Model | state-management | [study](../features/state-management/study/change-based-mutation-model--from-penpot.md) | [build](../features/state-management/build/change-based-mutation-model--from-penpot.md) |
| Native Design Tokens | design-systems | [study](../features/design-systems/study/native-design-tokens--from-penpot.md) | [build](../features/design-systems/build/native-design-tokens--from-penpot.md) |
| WASM/Skia Render Engine | rendering | [study](../features/rendering/study/wasm-skia-render-engine--from-penpot.md) | [build](../features/rendering/build/wasm-skia-render-engine--from-penpot.md) |

## Source files (reference only — repo may be gone later)
- `common/src/app/common/files/changes.cljc` — `process-change` multimethod + ~40 change types + `:mod-obj` operations.
- `common/src/app/common/files/changes_builder.cljc` — `empty-changes` (redo vector / undo list), `with-objects`, `add-object`, `update-shapes` (redo+undo pairing).
- `common/src/app/common/files/{page_diff,migrations,validate,repair}.cljc` — diffing, versioned migrations, integrity.
- `common/src/app/common/files/tokens.cljc` — token schema, token types, `is-reference?` (`{…}`).
- `common/src/app/common/types/tokens_lib.cljc` — `Token`/`TokenSet`/`TokenTheme`/`TokensLib`, `get-tokens-in-active-sets` (merge active sets in order → override).
- `render-wasm/src/main.rs` — `#[no_mangle]` C-ABI exports, `with_state!`/`with_current_shape_mut!`, alloc/free + `mem::bytes()`.
- `render-wasm/src/{wapi,render,tiles}.rs` — JS-imported callbacks, render pipeline, tile system.
- `render-wasm/docs/serialization.md` — binary byte layouts (shape-type u8, 28-byte path segs, 160-byte fills).
- `render-wasm/README.md` — Emscripten/Skia build, `enable-feature-render-wasm` flag.

## Cloneability verdict
The product as a whole is a years-long, multi-language effort — not something you "clone." But three
mechanisms are genuinely portable and worth lifting wholesale. The **change-based mutation model** is
the crown jewel: a clean, language-agnostic recipe for editor state where undo/redo, autosave, and
collaboration all fall out of one decision (edits = invertible serializable instructions) — copy this
into any editor you build. The **design-tokens model** (typed tokens → ordered sets → themes, with
override-by-merge-order theming and `{ref}` resolution) is a compact, interoperable design-system
core; it also slots neatly next to the heavier style-dictionary engine already in the brain. The
**WASM/Skia render engine** is the least copyable as code (it's deep Rust + Skia), but its
*architecture* — a numbers-and-pointers FFI boundary, "current shape + setters," fixed-size packed
binary records in shared memory, and tile-based incremental rendering — is a reusable blueprint for
any Rust/WASM + CanvasKit performance play. No moat in any single piece; the moat is the integrated,
polished whole. An LLM-assisted rebuild of any one feature is days–weeks; the full product is not.
