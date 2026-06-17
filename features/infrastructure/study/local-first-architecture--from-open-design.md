# Local-First Architecture — from [open-design](https://github.com/nexu-io/open-design)

> Domain: [[_domain]] · Source: https://github.com/nexu-io/open-design · NotebookLM: 

## What it does

Everything runs on your machine. Open Design is a desktop app (macOS/Windows) where a local Node.js daemon handles all the work — AI API calls, file management, database, MCP coordination — and the Electron shell renders the web UI on top. No cloud account required to use the app; your designs live in a local SQLite database and folder structure on your disk.

## Why it exists

Local-first is a deliberate product bet: design work is sensitive (clients, unreleased products, brand assets), and many designers and teams don't want it going through cloud servers. Running everything locally also means the app works offline for everything except AI API calls, and there's no server bill for the company when you're generating 100 designs a day.

## How it actually works

**The three-process model:**

1. **Electron main process** (`apps/desktop/`) — the native shell. It spawns the daemon as a sidecar process and opens the browser window. It handles native OS stuff: file system permissions, app lifecycle, auto-update.

2. **Daemon** (`apps/daemon/`) — a Hono HTTP server running in Node.js. This is where everything happens: AI calls, SQLite reads/writes, file writes, MCP server management, agent CLI spawning. It exposes ~15 API route groups at `localhost:<port>`.

3. **Web UI** (`apps/web/`) — a Next.js + React app that talks to the daemon via HTTP REST + SSE. It renders in the Electron browser window. It's a normal web app that happens to run in Electron — no Electron-specific code in the UI layer.

The Electron main process and daemon communicate via a sidecar IPC protocol with 6 message types: `STATUS` (health check), `EVAL` (run JS in renderer), `SCREENSHOT` (capture UI), `CONSOLE` (capture logs), `CLICK` (simulate interaction), `SHUTDOWN` (graceful stop).

**Data storage:**

SQLite via `better-sqlite3` stores everything: projects, conversations, artifacts metadata, design system selections, automation templates, MCP OAuth tokens, scheduler history, user preferences. The actual design files (HTML, images, videos) live on disk in a structured folder under `~/.od/projects/<projectId>/`.

The folder structure for a project:
```
~/.od/projects/<projectId>/
├── history.jsonl           — conversation history
├── .live-artifacts/        — HTML prototype versions + snapshots
├── artifacts/              — generated images and videos
├── files/                  — user-uploaded assets
└── design-system/          — resolved tokens for this project
```

**API surface (all localhost):**
The daemon exposes endpoints for everything the UI needs: chat streaming, media generation, project CRUD, artifact management, memory/knowledge base, automations, MCP server lifecycle, terminal (PTY) access, file management, app config, and connector (external service) management.

**Docker mode:** For power users, there's a Docker deployment option with locked-down security settings (read-only filesystem, no-new-privileges, 384MB memory limit) and an `OD_API_TOKEN` for authentication. The same daemon code runs locally or in a container.

## The non-obvious parts

**The daemon storage paths are in an internal spec.** The README explicitly says "Before changing daemon storage paths, you MUST read `AGENTS.md` → Daemon data directory contract." This is a sign the storage layout is considered a contract, not an implementation detail.

**Memory is a file system, not just a database.** The knowledge base is markdown files with frontmatter on disk — same format as the memory system in Claude Code. The daemon reads/writes `.md` files and exposes them through `/api/memory`. An LLM can extract facts from conversations and write them to memory automatically.

**PTY-based terminal access is built in.** You can open a real terminal inside the app (`/api/projects/:id/terminals/:tid/stream`), with full stdin/stdout/stderr. This is for power users who want a shell in context while designing.

**S3 is an optional storage backend.** The project storage abstraction has both `LocalProjectStorage` and `S3ProjectStorage`. By default everything is local; teams can configure S3 if they want shared project storage.

## Related

- [[byok-proxy--from-open-design]] (the proxy runs inside this daemon)
- [[agent-cli-integration--from-open-design]] (agent CLIs are spawned from this daemon)
- [[design-artifact-generation--from-open-design]] (artifacts stored in the project folder structure here)
