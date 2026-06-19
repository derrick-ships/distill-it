# Domain: plugin-architecture

Patterns for making a library extensible by third parties without modifying the core package — whether via Python entry-point discovery (markitdown) or an in-process, name-keyed hook registry (style-dictionary).

## What this domain is about

Plugin architecture is the practice of defining a stable contract (interface + registration protocol) that external packages can implement to inject new behavior into a host library at runtime. The host discovers and loads plugins lazily via Python's `importlib.metadata` entry points system.

## Key concerns

- **Discovery**: how the host finds installed plugins without a central registry
- **Interface versioning**: how to prevent ABI mismatches between host and plugin
- **Isolation**: plugins that fail to load should not crash the host
- **Registration callback**: the pattern for handing a plugin a reference to the host so it can register itself

## Features in this domain

- [[plugin-system--from-markitdown]] — entry-point-based plugin discovery and converter registration
- [[register-extensibility-api--from-style-dictionary]] — eight-bucket in-process hook registry (transforms/formats/filters/actions/parsers/preprocessors/...) with static-vs-instance scopes merged on read, and string-name indirection from config to plugin
- [[multimethod-driver-abstraction--from-metabase]] — one interface for N databases via Clojure multimethods + an isa? hierarchy, where SQL drivers inherit a shared MBQL→HoneySQL compiler and override only dialect quirks. Polymorphism through a data hierarchy; a new DB is a few dialect overrides, not a fork.
- [[multi-platform-agent-sync--from-ai-website-cloner-template]] — AGENTS.md as single source of truth, with sync scripts that regenerate 11+ platform-specific rule files (CLAUDE.md, GEMINI.md, .cursor/rules/, Copilot instructions, etc.) on demand. The agent-instruction counterpart to plugin discovery.
- [[sandboxed-extension-system--from-asyar]] — iframe-sandboxed extension runtime with a postMessage bridge, dual-layer permission enforcement (TypeScript frontend + Rust backend Tauri commands), a TypeScript SDK (`@asyar/extension-sdk`) with a Commander-based CLI for scaffolding, and hot-reload via Chokidar in dev mode
