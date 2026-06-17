# Agent CLI Integration (build spec) — distilled from open-design

## Summary

Dual-mode daemon CLI (`od`): default mode starts daemon + opens web UI; subcommand mode is a thin HTTP client POSTing to the running daemon. 22+ agent adapters (one object per CLI: bin, versionArgs, buildArgs, streamFormat). Agents run as child processes; stdout relayed via SSE. Recoverable exit codes 64-75. MCP server optional for tool-capable agents.

## Core logic (inlined)

**Daemon startup:**
```
od (no subcommand) →
  1. Start HTTP daemon (Hono, port inferred)
  2. Scan PATH for known agent binaries → build capability registry
  3. Open web UI in browser
  4. Serve API endpoints
```

**Thin client (subcommand mode):**
```
od <subcommand> [flags] →
  POST http://localhost:<daemonPort>/api/<subcommand>
  Body: { ...parsed flags }
  Stream SSE response or wait for JSON result
```

**Flag hoisting (important pattern):**
```typescript
// Flag definitions are hoisted to module scope to avoid TDZ errors
// during synchronous CLI dispatch (before async context is available)
const flags = {
  project: { type: 'string', alias: 'p' },
  output: { type: 'string', alias: 'o' },
  // ...
}
// Then used in the command handler
```

**Agent invocation:**
```typescript
function invokeAgent(adapter: AgentAdapter, prompt: string, projectDir: string) {
  const args = adapter.buildArgs(prompt)
  const child = spawn(adapter.bin, args, {
    cwd: projectDir,
    env: { ...process.env, ...mcpEnvVars }
  })
  return streamChildProcess(child, adapter.streamFormat)
}
```

**SSE streaming from daemon to web UI:**
```
GET /api/projects/:id/chat/events  (SSE endpoint)
Events:
  { type: 'start', runId, agentId, protocolVersion }
  { type: 'agent', status, text?, thinking?, liveArtifacts?, toolInvocations?, tokenUsage? }
  { type: 'stdout', data: string }
  { type: 'stderr', data: string }
  { type: 'error', message, stack? }
  { type: 'end', exitCode, signal, resumable: boolean }
```

**Recoverable exit codes:**
```
64 — daemon-not-running
65 — capabilities-required
66-75 — other retryable/recoverable failures
// Agents and automation scripts inspect these to decide retry behavior
```

**Agent detection command:**
```bash
open-design detect
# Rescans PATH for known agent binaries
# Returns updated capability registry
```

**Fallback env var:**
```
HERMES_CLI_PATH=/path/to/custom-agent
# Overrides PATH-based detection for this specific agent
```

## Data contracts

**Agent adapter object:**
```typescript
{
  id: string,           // 'claude-code', 'cursor', 'copilot', etc.
  name: string,         // display name
  bin: string,          // binary name in PATH
  versionArgs: string[], // e.g. ['--version']
  buildArgs: (prompt: string) => string[],
  streamFormat: 'plain' | 'acp-json' | 'json'
}
```

**Chat request (POST /api/chat):**
```typescript
{
  agentId: string,
  projectId: string,
  conversationId: string,
  message: string,
  systemPrompt: string,
  skillIds: string[],
  designSystemId: string,
  attachments: Attachment[],
  commentAttachments: CommentAttachment[],
  model: string,
  sessionMode: 'design' | 'chat',
  locale: string
}
```

**MCP server config (per-project or global):**
```typescript
{
  id: string,
  transport: 'stdio' | 'sse' | 'http',
  command?: string,
  args?: string[],
  env?: Record<string, string>,
  // OAuth:
  oauthConnectorId?: string
}

// OAuth endpoints:
POST /api/mcp/oauth/start   → { redirectUrl }
GET  /api/mcp/oauth/status  → { connected, expiresAt }
POST /api/mcp/oauth/disconnect
```

**Terminal session (PTY-based):**
```typescript
TerminalSession = {
  id: string,
  projectId: string,
  cwd: string,
  shell: string,
  cols: number,
  rows: number
}
// Streaming: SSE /api/projects/:id/terminals/:tid/stream
// Reconnect: Last-Event-ID header for buffered replay
```

## Dependencies & assumptions

- Agent CLIs must be installed and in PATH (or HERMES_CLI_PATH set)
- `child_process.spawn` with stdio pipes — Node.js built-in
- SSE relay: daemon holds open SSE connection to web UI, proxies agent stdout events
- MCP: agents must support MCP to use tool access (not all 22 adapters do)
- ACP (Agent Client Protocol): JSON-RPC over stdio — only supported by select agents

## To port this, you need:

- [ ] Agent adapter registry (start with claude + cursor; extend from there)
- [ ] PATH scanner that checks each adapter's bin with `which` or equivalent
- [ ] Child process spawner: `spawn(bin, buildArgs(prompt), { cwd: projectDir })`
- [ ] SSE endpoint on daemon that relays child process stdout in real time
- [ ] Exit code 64-75 mapping for recoverable failures
- [ ] `od` thin-client CLI: each subcommand = POST to daemon API
- [ ] Sandboxed iframe preview with hot-reload on file writes (debounced srcdoc replacement)
- [ ] MCP server (optional): serves project file access + design APIs as MCP tools

## Gotchas

- **Flag hoisting prevents TDZ crashes.** If you define CLI flags inside async functions, you'll get TDZ (temporal dead zone) errors during synchronous dispatch. Hoist flag definitions to module scope.
- **streamFormat matters.** Claude Code emits Anthropic-formatted JSON; other agents emit plain text or ACP JSON-RPC. Your stream parser must branch on format.
- **Sandbox the preview iframe properly.** `allow-scripts` only — no `allow-same-origin`, no `allow-forms`. The agent controls the HTML content; don't give it same-origin access.
- **MCP OAuth is daemon-hosted.** Don't implement a transient localhost redirect server — the daemon owns the full OAuth flow end-to-end. Much cleaner for a desktop app.
- **`od detect` is a user-facing command.** When agent detection fails (new agent installed after app launch), users need a way to force rescan without restarting. Expose this as a command.

## Origin (reference only)

Repo: https://github.com/nexu-io/open-design  
Key files: `apps/daemon/src/agents.ts`, `apps/daemon/src/chat-routes.ts`, `apps/desktop/src/`, `apps/cli/src/`
