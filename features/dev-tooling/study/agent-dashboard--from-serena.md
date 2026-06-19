# Agent Dashboard — from [Serena](https://github.com/oraios/serena)

> Domain: [[_domain]] · Source: https://github.com/oraios/serena · NotebookLM: <add link after upload>

## What it does

While an AI coding agent is working, you often want to know: what tools did it call, what went wrong, what's the active project, how many tokens has it used? Serena ships a live web dashboard that answers all of these questions without interrupting the agent's work.

The dashboard is a Flask-based REST API serving a single-page app that updates continuously. Depending on where you're running Serena, it shows up in three different ways: as a native desktop window (Windows), as a tab in your browser (macOS/Linux), or aggregated in a system-tray app that manages multiple simultaneous Serena instances. You can read logs, browse the active configuration, manage project memories, add/remove language servers, check for news about Serena updates — and shut the agent down — all from a single UI.

## Why it exists

The MCP stdio transport (how Claude Code talks to Serena) is a black box: the agent is sending and receiving JSON over stdin/stdout, but nothing about that is observable. Debugging is impossible without tooling. The dashboard makes the agent's activity visible — what tools it called, what they returned, what errors appeared — so developers can observe, trust, and tune the system.

There's also a practical multi-instance problem. You can run Serena for multiple projects simultaneously, each on its own port. The tray manager solves the "where is it?" problem by aggregating all running instances behind one menu, auto-cleaning dead ones.

## How it actually works

**The Flask backend.** `SerenaDashboardAPI` is a Flask application that the agent launches in a background daemon thread on a dynamically allocated port (starting from a base port, incrementing until a free port is found). It holds references to the live agent object, the in-memory log handler, tool statistics, and memory manager — so it can read current state at query time without any IPC overhead.

**In-memory log capture.** All agent log messages flow through Python's standard `logging` module. A `MemoryLogHandler` (a standard `logging.Handler` subclass) appends formatted log records to an in-memory ring buffer. The dashboard's `/logs` endpoint reads from that buffer. This means you see real-time log output without writing to a file or tailing anything.

**The routes.** The dashboard API exposes a small set of REST endpoints:
- `GET /logs` — paginated log messages (returns from a cursor index so repeated polls only get new messages)
- `DELETE /logs` — clear the log buffer
- `GET /tools` — available tool names
- `GET /tools/stats` — call counts and token usage per tool
- `DELETE /tools/stats` — reset stats
- `GET /config` — full configuration snapshot (active project, modes, contexts, registered projects, tool list, system info)
- `GET /memories`, `POST /memories`, `DELETE /memories/:name`, `POST /memories/:name/rename` — CRUD on the project's Markdown memory files
- `GET /tasks` — queued agent task execution status
- `DELETE /tasks/:id` — cancel a queued task
- `POST /languages` — add a language server to the active project
- `DELETE /languages/:lang` — remove one
- `GET /news` — news articles fetched from a remote URL with ETag caching
- `POST /news/:id/read` — mark an article as read
- `POST /shutdown` — gracefully terminate the agent

**News with ETag caching.** Serena fetches a remote JSON feed of news/release notes. The HTTP response's ETag header is stored locally; subsequent requests include `If-None-Match` to get 304 Not Modified when nothing changed. Read state ("has the user seen this article?") is tracked in a local JSON file, with a legacy migration path from an older storage format. Articles are filtered by publication date vs. the Serena installation timestamp — you only see news published after you installed.

**Three display modes.**

*BROWSER mode* (macOS/Linux default): The dashboard URL (`http://127.0.0.1:<port>/dashboard/index.html`) is opened in the system's default browser via `webbrowser.open()`. Simplest approach, zero extra dependencies.

*WEBVIEW mode* (Windows default): A `pywebview` native window is spawned as a subprocess. This gives users a proper desktop app feel without the browser tab. Platform-specific icon files (`.ico` on Windows, `.icns` on macOS) are loaded from the package resources.

*TRAY_MANAGER mode*: A singleton `SerenaDashboardTrayManager` runs its own Flask app on a fixed internal port (`127.0.0.1:9042`). Each Serena instance registers itself with a POST that includes its port, project name, PID, and startup time. The tray manager builds a system tray menu with one entry per live instance. It monitors instance health via PID existence checks or HTTP heartbeat pings (fallback if PID isn't available, e.g., across process namespaces). When an instance disappears, it's automatically removed from the menu. Clicking an instance's menu item opens its dashboard in a browser or webview.

**The GUI log viewer (alternative).** For users who don't want the web dashboard, there's also `GuiLogViewer` — a Tkinter window that runs in a separate thread, showing color-coded log messages (DEBUG in grey, WARNING in yellow, ERROR in red) with bold highlighting for tool names. This is mainly used as a lightweight log window when not running the full web dashboard.

## The non-obvious parts

**The Flask app runs before the agent is fully initialized.** Dashboard startup happens early so logs from agent startup (LSP server launch, etc.) are captured. The agent reference is injected after construction.

**Port conflicts are handled by retry.** Port discovery starts at a configured base port and increments by 1 until a free port is found. This is a simple loop that tries `socket.bind()` and catches `OSError`. On multi-user systems or when multiple Serena instances share a base port, they naturally spread out.

**Tray manager persistence across agent restarts.** The tray manager is designed to outlive individual Serena agent instances. When you restart an agent, it re-registers with the tray manager; the tray manager cleans up the old entry when it detects the PID is gone. This creates a stable system-level presence across multiple coding sessions.

**Memory CRUD goes through the agent's MemoryManager.** The dashboard's memory endpoints aren't raw file operations — they call into `MemoryManager`, which enforces read-only patterns, ignored-directory rules, and cross-reference updates on rename. This keeps the dashboard's memory edits consistent with what the agent sees.

**News is fetched in a background thread.** The first `/news` call spawns a daemon thread that does the actual HTTP fetch (with ETag). Subsequent calls immediately return the cached response while the thread quietly updates it in the background. Network failures are silently tolerated — the last cached content is served.

## Related
- [[semantic-symbol-tools--from-serena]] (the tools whose call counts and results appear in the dashboard)
- [[agent-memory--from-serena]] (the memory system the dashboard exposes for CRUD)
- See also: Langfuse, LangSmith for general-purpose LLM observability at a higher abstraction level
