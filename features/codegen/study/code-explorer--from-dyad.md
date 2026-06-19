# Code Explorer — from [dyad](https://github.com/dyad-sh/dyad)

> Domain: [[_domain]] · Source: https://github.com/dyad-sh/dyad · NotebookLM: 

## What it does

Before Dyad sends your message to the AI, it optionally injects a rich semantic index of your app's codebase — exported functions, types, component names, with line numbers and cross-file context — so the LLM knows what already exists and can make targeted edits rather than rewriting from scratch.

## Why it exists

AI code generation fails in two predictable ways: it hallucinates APIs that don't exist, or it re-implements things that are already in the codebase. The code explorer solves both by giving the AI a "table of contents" of the real codebase, indexed semantically. It's the difference between "add a button that calls handleSubmit" working vs. the AI inventing a new `submitHandler` that conflicts with the existing one.

## How it actually works

**Availability check:** `getCodeExplorerAvailability()` verifies two things in ~3 microseconds: TypeScript is installed in the app's node_modules, and a `tsconfig.json` or `tsconfig.app.json` exists. If either is missing, code explorer silently skips — it only works on TypeScript apps. This check runs uncached so fresh installs are detected immediately.

**Tsconfig discovery:** For monorepos, `discoverTsconfigPath()` walks the directory tree: first checks the root for `tsconfig.app.json` (preferred) then `tsconfig.json`. If not found, checks `apps/` and `packages/` subdirectories. Each candidate is scored — directories named `web`, `app`, or `client` get a bonus; `docs`, `test`, and `e2e` get penalized. The highest-scoring config wins.

**Worker pool:** Computing the TypeScript symbol index is expensive (it runs the full TS compiler in language-service mode). Dyad maintains a pool of up to **8 worker threads**, each keyed by `(appPath, tsconfigPath)`. Each worker:
- Owns a task queue (sequential execution, no concurrent TS operations per worker)
- Has a 5-minute idle timeout — the worker terminates if unused, freeing memory
- Is LRU-pruned when the pool hits capacity

**Index building:** Inside the worker, `buildCodeExplorerIndex()` runs with the TypeScript instance and config. It:
1. Loads all source files matching the tsconfig globs (excluding `.d.ts` declaration files)
2. Extracts exported symbols: functions, classes, interfaces, type aliases, React components
3. Records file path, line number, and a snippet of surrounding context for each symbol
4. Applies query stemming when called (e.g., "creating" → "create" to match `createUser`)

**Ranking:** When `exploreCode(query)` is called with the user's prompt keywords, results are ranked by:
- Term overlap with the query (after stemming)
- Architecture preference: implementation files > test utilities > docs
- Monorepo awareness: product app packages score higher than documentation packages

**Injection into chat:** The top-N symbols are formatted as a structured block (symbol name, file, line, snippet) and prepended to the system prompt before the LLM call.

## The non-obvious parts

- **Worker isolation is intentional:** TypeScript's language service maintains file system state and caches. Running it in the main process would block Electron's UI thread for seconds on large codebases. Worker threads allow true parallelism without blocking.
- **Cache invalidation via tsBuildInfo:** The explorer writes `.tsbuildinfo` files to a cache dir and invalidates when tsconfig globs change. This means the second exploration of the same project is much faster (incremental).
- **Monorepo scoring is heuristic, not config:** There's no "tell dyad where your main app is" setting. The scoring algorithm guesses by directory name. It works well for standard setups (apps/web, packages/ui) but can pick the wrong root in unusual layouts.
- **Opt-in feature flag:** Code Explorer is behind a feature flag in settings and can be disabled. It's off by default for simpler setups where the TypeScript overhead isn't worth it.

## Related
- [[ai-chat-stream--from-dyad]] (symbols are injected here before the LLM call)
- [[dependency-manager--from-dyad]] (TypeScript must be installed for code explorer to activate)
