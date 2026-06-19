# Code Explorer (build spec) — distilled from dyad

## Summary

Build a TypeScript-compiler-backed code indexer that runs in worker threads, discovers the right tsconfig in monorepos, extracts exported symbols with file paths and line numbers, ranks them against a query using stemming and architecture heuristics, and injects the top results into the AI's system prompt before each chat turn. Designed to give LLMs semantic awareness of an existing codebase.

## Core logic (inlined)

```typescript
// --- AVAILABILITY CHECK (run before every chat turn) ---
function getCodeExplorerAvailability(appPath: string): { available: boolean; reason?: string } {
  const tsPath = path.join(appPath, 'node_modules/typescript/lib/typescript.js')
  if (!fs.existsSync(tsPath)) return { available: false, reason: 'typescript_not_installed' }
  
  const configPath = discoverTsconfigPath(appPath)
  if (!configPath) return { available: false, reason: 'no_tsconfig' }
  
  return { available: true }
}
// Note: intentionally NOT cached — detects fresh TypeScript installs immediately

// --- TSCONFIG DISCOVERY ---
function discoverTsconfigPath(appPath: string): string | null {
  // Priority 1: root-level preferred names
  for (const name of ['tsconfig.app.json', 'tsconfig.json']) {
    const p = path.join(appPath, name)
    if (fs.existsSync(p)) return p
  }
  
  // Priority 2: monorepo subdirectories
  const candidates: { path: string; score: number }[] = []
  
  for (const subdir of ['apps', 'packages']) {
    const subdirPath = path.join(appPath, subdir)
    if (!fs.existsSync(subdirPath)) continue
    
    for (const entry of fs.readdirSync(subdirPath)) {
      const entryPath = path.join(subdirPath, entry)
      const configPath = path.join(entryPath, 'tsconfig.json')
      if (!fs.existsSync(configPath)) continue
      
      let score = 0
      // Bonus for frontend-like names
      if (/^(web|app|client|frontend|ui)$/.test(entry)) score += 10
      // Penalty for non-product directories  
      if (/^(docs|test|e2e|storybook|scripts)$/.test(entry)) score -= 5
      // Bonus if it has a package.json (real package)
      if (fs.existsSync(path.join(entryPath, 'package.json'))) score += 2
      
      candidates.push({ path: configPath, score })
    }
  }
  
  candidates.sort((a, b) => b.score - a.score)
  return candidates[0]?.path ?? null
}

// --- WORKER POOL ---
// Pool size: 8 workers max, keyed by (appPath + tsconfigPath)
// Each worker: sequential task queue, 5-min idle timeout, LRU eviction at capacity
const workerPool = new Map<string, WorkerEntry>()

interface WorkerEntry {
  worker: Worker
  queue: Promise<unknown>   // chain tasks sequentially
  lastUsed: number
  idleTimer: NodeJS.Timeout
}

function getOrCreateWorker(appPath: string, tsconfigPath: string): WorkerEntry {
  const key = `${appPath}::${tsconfigPath}`
  
  if (workerPool.has(key)) {
    const entry = workerPool.get(key)!
    refreshIdleTimer(entry)
    return entry
  }
  
  if (workerPool.size >= 8) evictLRU()
  
  const worker = new Worker('./code_explorer_worker.js', {
    workerData: { appPath, tsconfigPath }
  })
  const entry: WorkerEntry = {
    worker,
    queue: Promise.resolve(),
    lastUsed: Date.now(),
    idleTimer: setTimeout(() => terminateWorker(key), 5 * 60 * 1000)
  }
  workerPool.set(key, entry)
  return entry
}

// --- WORKER LOGIC (runs in worker thread) ---
// code_explorer_worker.js
import ts from 'typescript' // loaded from app's node_modules, not global
import { workerData } from 'worker_threads'

const { appPath, tsconfigPath } = workerData

// Build incremental program (cached via tsBuildInfo)
const host = ts.createIncrementalCompilerHost(config)
let program = ts.createIncrementalProgram({ ... })

function buildIndex(): SymbolEntry[] {
  const entries: SymbolEntry[] = []
  
  for (const sourceFile of program.getSourceFiles()) {
    // Skip: declaration files, test utilities, external packages
    if (sourceFile.fileName.endsWith('.d.ts')) continue
    if (sourceFile.fileName.includes('node_modules')) continue
    
    ts.forEachChild(sourceFile, (node) => {
      if (!isExported(node)) return
      
      if (ts.isFunctionDeclaration(node) || ts.isArrowFunction(node) ||
          ts.isClassDeclaration(node) || ts.isInterfaceDeclaration(node) ||
          ts.isTypeAliasDeclaration(node)) {
        const name = node.name?.getText()
        if (!name) return
        const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart())
        entries.push({
          name,
          file: path.relative(appPath, sourceFile.fileName),
          line: line + 1,
          kind: getSymbolKind(node),
          snippet: sourceFile.text.slice(node.getStart(), Math.min(node.getEnd(), node.getStart() + 200))
        })
      }
    })
  }
  return entries
}

// --- QUERY & RANKING ---
function exploreCode(query: string, index: SymbolEntry[]): SymbolEntry[] {
  const queryTerms = tokenize(query).flatMap(t => [t, stem(t)])
  
  return index
    .map(entry => ({
      entry,
      score: scoreEntry(entry, queryTerms)
    }))
    .filter(x => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 50)
    .map(x => x.entry)
}

function scoreEntry(entry: SymbolEntry, queryTerms: string[]): number {
  let score = 0
  const nameLower = entry.name.toLowerCase()
  
  for (const term of queryTerms) {
    if (nameLower.includes(term)) score += 10
  }
  
  // Prefer implementation files
  if (entry.file.includes('.test.') || entry.file.includes('.spec.')) score -= 3
  if (entry.file.includes('__mocks__')) score -= 5
  
  return score
}

// Simple stemmer: strip common suffixes
function stem(word: string): string {
  return word.replace(/(ing|ed|er|s)$/, '')
}

// --- INJECTION INTO SYSTEM PROMPT ---
function formatCodeExplorerContext(symbols: SymbolEntry[]): string {
  if (symbols.length === 0) return ''
  
  const lines = symbols.map(s =>
    `${s.kind} ${s.name} — ${s.file}:${s.line}\n  ${s.snippet.trim().slice(0, 100)}`
  )
  
  return `<codebase-symbols>\n${lines.join('\n\n')}\n</codebase-symbols>`
}
// Prepend this to the system prompt before each AI call
```

## Data contracts

```typescript
interface SymbolEntry {
  name: string          // "handleSubmit"
  file: string          // relative path: "src/components/Form.tsx"
  line: number          // 1-indexed
  kind: 'function' | 'class' | 'interface' | 'type' | 'component'
  snippet: string       // first ~200 chars of the node's text
}

// IPC: code-explorer:query(appPath, query) → SymbolEntry[]
// IPC: code-explorer:availability(appPath) → { available: boolean; reason?: string }
```

## Dependencies & assumptions

- **TypeScript** must be installed in the **target app's** `node_modules` (not globally). Load it with `require(path.join(appPath, 'node_modules/typescript'))`.
- **`worker_threads`** (Node 12+) for isolating the TS compiler
- Target apps must have a `tsconfig.json` or `tsconfig.app.json`
- Works only for TypeScript (and JS projects with JSDoc types) — not Python, Go, etc.

## To port this, you need:

- [ ] Worker thread infrastructure (pool, queue, idle timeout, LRU eviction)
- [ ] `discoverTsconfigPath()` with monorepo scoring
- [ ] TypeScript program builder that loads `typescript` from the *app's* node_modules
- [ ] Symbol extractor: walk AST, collect exported functions/classes/types
- [ ] Query stemmer and term-overlap scorer
- [ ] Architecture-aware ranking (penalize tests/docs/e2e)
- [ ] System prompt injection block (`<codebase-symbols>...</codebase-symbols>`)
- [ ] Availability check guard (skip cleanly if TS not installed or no tsconfig)
- [ ] `.tsbuildinfo` incremental cache invalidation

## Gotchas

- **Load TypeScript from the app, not globally:** `require('typescript')` would use the system version. The app may have a different TS version. Always resolve from `appPath/node_modules/typescript`.
- **Worker thread, not child process:** Child processes have higher startup cost and no shared memory. Worker threads spin up faster and can share the worker pool efficiently.
- **Declaration files poison the index:** `.d.ts` files contain re-exports that look like symbols but aren't user-authored code. Always filter them out — they generate noise and no useful context.
- **Monorepo tsconfig scoring is heuristic:** It will fail on unusual layouts. Provide a manual override setting ("which tsconfig to use") as an escape hatch.
- **5-minute idle timeout:** Don't make it too short (heavy startup cost) or too long (memory leak). 5 minutes balances cold-start cost vs. footprint for inactive projects.
- **Token budget:** Code explorer output can be large. Cap injected symbols at ~2000 tokens (50 symbols × 40 tokens each). Beyond that, the context window benefit diminishes and cost increases sharply.

## Origin (reference only)
- Repo: https://github.com/dyad-sh/dyad
- Key files: `src/ipc/processors/code_explorer.ts`, `src/ipc/processors/code_explorer_core.test.ts`
