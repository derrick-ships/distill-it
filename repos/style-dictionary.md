# style-dictionary

**Source:** https://github.com/style-dictionary/style-dictionary
**Product:** "Style once, use everywhere." A build system that takes design tokens defined once (JSON/JS) and exports platform-ready style files — CSS custom properties, SCSS, JS, iOS Swift, Android XML, Flutter, React Native, and more.
**Stack:** JavaScript (ESM), Node + browser. Deps include `change-case`, `colorjs.io`/`tinycolor2`, `commander` (CLI), `@bundled-es-modules/memfs` (in-browser FS), `json5`, `prettier`.
**Distilled:** 2026-06-17

## Features extracted

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Token Pipeline Orchestration | design-systems | [study](../features/design-systems/study/token-pipeline-orchestration--from-style-dictionary.md) | [build](../features/design-systems/build/token-pipeline-orchestration--from-style-dictionary.md) |
| Reference Resolution Engine | design-systems | [study](../features/design-systems/study/reference-resolution-engine--from-style-dictionary.md) | [build](../features/design-systems/build/reference-resolution-engine--from-style-dictionary.md) |
| Transforms & Transform Groups | design-systems | [study](../features/design-systems/study/transforms-and-transform-groups--from-style-dictionary.md) | [build](../features/design-systems/build/transforms-and-transform-groups--from-style-dictionary.md) |
| Register / Extensibility API | plugin-architecture | [study](../features/plugin-architecture/study/register-extensibility-api--from-style-dictionary.md) | [build](../features/plugin-architecture/build/register-extensibility-api--from-style-dictionary.md) |

## Notes

The four features form the reusable spine of any token-to-code build system. The **orchestration** layer interleaves **transforms** and **reference resolution** in a convergence loop (transforms can't run until references resolve; some references can't resolve until transforms run). The **Register API** is the name-indirection layer that lets a plain config describe a fully custom pipeline. Not distilled (available for a later pass): formats & format helpers, token parsing/JSON merging, DTCG spec support, composite token expansion.
