# Local-First Architecture (build spec) — distilled from open-design

## Summary

3-process model: Electron main (native shell) + Node.js daemon (Hono HTTP + SQLite + business logic) + Next.js web UI. Sidecar IPC: 6 message types (STATUS/EVAL/SCREENSHOT/CONSOLE/CLICK/SHUTDOWN). All data local: SQLite for metadata, `~/.od/projects/<id>/` for files. ~15 API route groups on localhost. Optional S3 backend and Docker deployment.

## Core logic (inlined)

**Process architecture:**
```
Electron main process
  └── spawns daemon via sidecar-runtime package
  └── opens BrowserWindow (web UI)
  └── IPC: STATUS | EVAL | SCREENSHOT | CONSOLE | CLICK | SHUTDOWN

Daemon (Hono HTTP server, Node.js)
  ├── SQLite (better-sqlite3, synchronous)
  ├── Project storage: LocalProjectStorage | S3ProjectStorage
  ├── Agent CLI spawner
  ├── MCP server manager
  └── API routes:
      /api/chat + /api/projects/:id/chat/events (SSE)
      /api/proxy/:provider/stream
      /api/projects/*
      /api/workspaces/*
      /api/artifacts/*
      /api/memory/* + /api/memory/events (SSE)
      /api/automations/* + /api/routines/*
      /api/mcp/*
      /api/terminals/:id/stream (SSE, PTY)
      /api/app-config
      /api/connectors/*
      /api/media/tasks
      /api/live-artifacts/*
      /api/health

Web UI (Next.js + React, in Electron BrowserWindow)
  → HTTP REST to daemon
  → SSE for streaming (chat, memory, terminals)
```

**Project file storage layout:**
```
<dataDir>/.od/projects/<projectId>/
├── history.jsonl                    — JSONL conversation turns
├── .live-artifacts/
│   └── <artifactId>/
│       ├── artifact.json            — LiveArtifact metadata
│       ├── template.html            — raw agent output
│       ├── index.html               — rendered (bindings resolved)
│       ├── data.json                — template data (≤256KB)
│       ├── provenance.json          — creation audit trail
│       ├── refreshes.jsonl          — all refresh ops
│       └── snapshots/<refreshId>/   — historical snapshots
├── artifacts/                       — images, videos
├── files/                           — user uploads
└── design-system/                   — resolved tokens.css + component manifests
```

**AppConfigPrefs schema (persisted in SQLite):**
```typescript
{
  agentId: string,
  installationId: string,
  modelPreferences: Record<string, string>,
  cliEnv: Record<string, string>,
  skillId: string,
  designSystemId: string,
  customInstruction: string,
  projectLocationRoots: string[],
  recentLinkedDirs: string[],     // pruned to still-existing dirs only
  privacyConsentTimestamp: number,
  telemetryEnabled: boolean
}
```

**Memory (knowledge base) API:**
```typescript
// Files: <dataDir>/.od/memory/<slug>.md
// Frontmatter: name, description, type ('user'|'feedback'|'project'|'reference')
// Index: MEMORY.md

GET  /api/memory          → list all entries with metadata
POST /api/memory          → create (auto-slug from name+type)
PUT  /api/memory/:id      → update
GET  /api/memory/:id      → retrieve with body
POST /api/memory/extract  → LLM extraction from chat transcript
GET  /api/memory/system-prompt → composed markdown for agent injection
```

**Docker deployment config:**
```dockerfile
Security:
  no-new-privileges: true
  read-only filesystem (with tmpfs mounts for writable dirs)
  localhost-only binding

Resources:
  memory: 384m
  pids: 256
  NODE_OPTIONS: --max-old-space-size=192

Auth: OD_API_TOKEN (generate: openssl rand -hex 32)
Health: GET /api/health every 30s
Volume: open_design_data → <dataDir>
```

**Automation pipeline stages:**
```
ingest → canonicalize → redact → compress → classify → propose → agent-run → apply → notify

Sources: upload, url, repo, connector, artifact, chat
Destinations: memory, skill, design-system, automation-template, artifact
Compression: off | balanced | aggressive
```

**Project status state machine:**
```
not_started → queued → running → awaiting_input → succeeded
                                                 ↘ failed
                                                 ↘ canceled
```

## Data contracts

**ProjectFile metadata:**
```typescript
{
  name: string,
  path: string,
  size: number,
  mtime: number,
  kind: 'html'|'image'|'video'|'audio'|'sketch'|'text'|'code'|'pdf'|'document'|'presentation'|'spreadsheet'|'binary',
  artifactKind?: ArtifactKind,
  artifactManifest?: ArtifactManifest,
  stubGuardWarning?: string    // set if file is undersized (regression detection)
}
```

**ConnectorAuthDetail:**
```typescript
{
  provider: 'local' | 'none' | 'oauth' | 'composio',
  configured: boolean
}

ConnectorConnectResponse = {
  authKind: 'redirect_required' | 'pending' | 'connected',
  redirectUrl?: string,         // for OAuth flows
  providerConnectionId?: string, // on success
  expiresAt?: number            // time-bound credentials
}
```

**Routine scheduling:**
```typescript
{
  scheduleType: 'hourly' | 'daily' | 'weekdays' | 'weekly',
  timezone?: string,   // UTC by default
  projectMode: 'fresh' | 'reuse',
  projectId?: string   // for reuse mode
}
```

## Dependencies & assumptions

- **Electron** 41.3.0 — macOS + Windows builds; optional Linux AppImage via GitHub Releases
- **better-sqlite3** 12.10.0 — synchronous SQLite bindings; requires native compilation (pre-built for supported platforms)
- **Hono** — HTTP framework for daemon
- **sharp** — image processing; also requires native compilation
- **node-pty** — PTY terminal sessions (native module)
- **Internal packages**: `@open-design/sidecar-runtime`, `@open-design/sidecar-protocol`, `@open-design/platform`, `@open-design/diagnostics`, `@open-design/download`
- **Storage paths**: governed by unpublished `AGENTS.md` → Daemon data directory contract — verify before implementation

## To port this, you need:

- [ ] Hono HTTP server in Node.js process (or Express equivalent)
- [ ] SQLite via better-sqlite3 with synchronous API (or better-sqlite3 is strongly preferred over async drivers for this use case)
- [ ] Project file storage abstraction with Local + S3 backends
- [ ] SSE endpoint pattern for all streaming routes (chat, terminals, memory events)
- [ ] Conversation history as JSONL (append-only, efficient)
- [ ] Live artifact versioning: artifact.json + refreshes.jsonl + snapshots/ subdirs
- [ ] Memory system: markdown files with frontmatter, MEMORY.md index, LLM extraction endpoint
- [ ] PTY terminal via node-pty for in-app shell sessions
- [ ] If Electron: sidecar-protocol IPC (STATUS/EVAL/SCREENSHOT/CONSOLE/CLICK/SHUTDOWN)
- [ ] `OD_API_TOKEN` bearer auth for Docker/headless deployments

## Gotchas

- **better-sqlite3 is synchronous.** This is intentional — it avoids Promise chains in hot paths. But it means blocking the Node.js event loop on heavy writes. Use WAL mode (`PRAGMA journal_mode=WAL`) for concurrent read performance.
- **Daemon storage paths are a contract, not details.** The codebase has an explicit `AGENTS.md` data directory contract. Changing paths silently breaks existing installations. Treat storage paths as a versioned API.
- **Native modules need platform-specific builds.** better-sqlite3, sharp, and node-pty must be compiled for each target platform/arch. Use `electron-builder` with pre-built binaries where available.
- **S3 storage is optional but plan the abstraction early.** If you build with `LocalProjectStorage` only and later add S3, it's a significant refactor. Model the storage interface from day one.
- **The web UI is a normal Next.js app.** No Electron APIs in the renderer. This is the right call — it makes the UI portable (also runs in browser via Docker). Don't add Electron-specific code to the web layer.
- **stubGuardWarning is a production monitoring tool.** If a generated artifact is suspiciously small (agent wrote a stub), this field gets set. Wire it to your monitoring/alerting.

## Origin (reference only)

Repo: https://github.com/nexu-io/open-design  
Key files: `apps/desktop/src/main.ts`, `apps/daemon/src/`, `apps/daemon/src/project-storage.ts`, `packages/sidecar-runtime/`, `packages/sidecar-protocol/`
