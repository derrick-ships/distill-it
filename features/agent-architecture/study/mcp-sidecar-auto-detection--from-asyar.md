# MCP Sidecar Auto-Detection — from [asyar](https://github.com/Xoshbin/asyar)

> Domain: [[_domain]] · Source: https://github.com/Xoshbin/asyar · NotebookLM:

## What it does

Asyar automatically discovers MCP (Model Context Protocol) server configurations from other AI tools installed on the same machine — Claude Desktop, Cursor, Cline, Continue, and Zed — and offers to import them. Once imported, those MCP servers' tools become available to Asyar's AI agent. For MCP servers that need `npx` or `uvx` to launch, Asyar ships bundled `bun` and `uv` binary sidecars so users don't need Node.js or Python installed.

## Why it exists

MCP servers represent a growing ecosystem of tool integrations (databases, APIs, file systems, developer tools). Users who've already configured these in Claude Desktop or Cursor shouldn't have to reconfigure them elsewhere. Auto-detection means a zero-configuration path: install Asyar, and your existing MCP setup is immediately available. The bundled runtime sidecars solve the "you need Node.js installed" problem that blocks non-developer users.

## How it actually works

**Config file scanning**: At startup, and when the user opens the MCP settings panel, Asyar scans the known config file locations for each AI tool:
- **Claude Desktop**: `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS), `%APPDATA%/Claude/claude_desktop_config.json` (Windows)
- **Cursor**: `~/.cursor/mcp.json`
- **Cline**: VS Code extension storage (`globalStoragePath` + `/samatech.cline/mcp_settings.json`)
- **Continue**: `~/.continue/config.json`
- **Zed**: `~/.config/zed/settings.json` (MCP section)

Each file has a different schema, but all describe MCP servers with a `command`, `args[]`, and optional `env{}`. Asyar parses each format and normalizes them to its internal `McpServerConfig` shape.

**Import UI**: Detected servers are presented as a list in the MCP settings panel. Users can import individual servers or all detected servers at once. Imported configs are stored in Asyar's own settings database.

**Sidecar resolution for `npx`/`uvx`**: Many MCP servers are distributed as npm or Python packages and launched with `npx package-name` or `uvx package-name`. These require Node.js or Python on the system. Asyar ships platform-specific binary sidecars of `bun` (JavaScript runtime, npm-compatible) and `uv` (Python package manager) inside the Tauri app bundle. When an MCP server's command is `npx`, Asyar rewrites it to use the bundled `bun x` instead. When it's `uvx`, it rewrites to the bundled `uv tool run`.

**MCP subprocess management**: Imported servers are launched as child processes when Asyar starts. The `bun`/`uv` sidecars are extracted to a temp directory at first launch and reused on subsequent runs. Subprocess stdout/stderr is monitored; a crashed server is restarted with exponential backoff.

**Tool discovery**: Once an MCP server process is running, Asyar connects to it via stdio (or HTTP, depending on the server's transport). It sends a `tools/list` JSON-RPC request and receives the list of tool definitions. These are added to the AI agent's tool registry under a namespace prefix (e.g., `mcp__github__create_issue`).

**Runtime fallback**: If the bundled sidecar fails to execute (architecture mismatch, permissions), Asyar falls back to the system `node` or `python3` binary with a warning to the user.

## The non-obvious parts

**Config file formats differ significantly.** Claude Desktop uses `mcpServers: { serverName: { command, args, env } }`. Cursor uses `{ mcpServers: [...] }` (array, not object). Continue embeds MCP config inside a larger config structure. Each parser is a separate code path.

**`bun x` vs `npx` differences.** Bun has excellent npm compatibility, but some packages rely on Node-specific globals (`__dirname`, `require.resolve`) in ways that break under Bun. Asyar defaults to the sidecar but lets users override the command if something breaks.

**MCP server lifecycle is tied to Asyar's lifecycle.** Servers start when Asyar starts, stop when Asyar quits. If a server is slow to start (downloads something on first run), the agent may see "tool not available" errors for the first few seconds.

**Tool namespacing prevents collisions.** If GitHub MCP and GitLab MCP both expose a `create_issue` tool, they'd collide in the registry. The `mcp__<server-slug>__` prefix prevents this. The slug is derived from the server name in the config.

**The sidecar binaries are large.** Bundled `bun` is ~50MB and `uv` is ~10MB. This significantly increases the Asyar download size but eliminates a major user friction point. It's a deliberate tradeoff.

## Related

- [[ai-agent-tool-calling--from-asyar]] — the tool registry that MCP tools join
- [[agent-architecture/mcp-crm-server--from-auto-crm]] — an example of building an MCP server (the server-side of this pattern)
- [[ordered-backend-routing--from-agent-reach]] — a related "prefer X, fall back to Y" pattern for tool backends
- [[plugin-ecosystem--from-open-design]] — similar 3-tier discovery for plugin backends
