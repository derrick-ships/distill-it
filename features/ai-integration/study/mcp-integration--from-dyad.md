# MCP Integration — from [dyad](https://github.com/dyad-sh/dyad)

> Domain: [[_domain]] · Source: https://github.com/dyad-sh/dyad · NotebookLM: 

## What it does

Dyad lets you connect external MCP (Model Context Protocol) servers to the AI builder. When the AI is in "build" mode, it can invoke tools from those servers — web search, database queries, API calls, custom scripts — right inside the chat session. Dyad manages server discovery, OAuth auth flows, tool listing with timeouts, and user consent per-tool.

## Why it exists

MCP is the emerging standard for giving LLMs access to external capabilities without baking every integration into the AI itself. For Dyad — a local builder — MCP means users can wire up their own tools: a company's internal API, a local Postgres server, a web scraper. It makes the AI's capabilities unbounded without Dyad needing to ship every connector.

## How it actually works

**Server storage:** MCP servers are stored in the local SQLite database with a type field (stdio, SSE, streamable-http) and optional OAuth credentials (stored encrypted in the settings file).

**Port allocation:** For local servers that need a fixed port, `isPortFreeOnBothLoopbacks()` checks both `127.0.0.1` and `::1` simultaneously — because on some Linux/macOS configurations, binding on one loopback doesn't bind on the other, causing mysterious "port in use" errors.

**Tool listing:** When the UI asks for a server's tools, `mcp_handlers.ts` starts the server subprocess (or connects to the URL), calls `client.tools()`, and enforces an **8-second timeout**. If the server hangs past that, the client is forcibly disposed to avoid file descriptor leaks, and an error is returned. Tool results include the tool names, schemas, and descriptions — surfaced in the settings UI as a toggle list.

**Consent tracking:** Each tool has a per-user consent state stored in SQLite (`consented` boolean per tool ID). The renderer shows "Allow this tool?" prompts; once allowed, the IPC handler persists the decision. During a chat stream, only consented tools are passed to the LLM.

**OAuth flow:**
1. User clicks "Connect OAuth" in settings
2. Handler calls `probeOAuthConnection()` — tries to discover the server's OAuth metadata via `/.well-known/oauth-authorization-server`
3. On success, stores the OAuth state (encrypted) and opens the browser for the auth redirect
4. After redirect, the callback handler stores the access token
5. `toMcpServer()` converts the encrypted OAuth state to a simple `oauthConnected: boolean` for the UI — credentials never leave the main process

**Error classification:** `mcp_error_classifiers.ts` distinguishes:
- **OAuth discovery failure**: "well-known" / "does not implement oauth" / "incompatible oidc" patterns → UI shows "Disable OAuth & retry"
- **Unauthorized (401)**: `looksLikeUnauthorized()` regex → UI shows "Reconnect" button
- **Generic failure**: any other error → generic error message

**During chat:** The AI SDK receives MCP tools as standard tool definitions. When the LLM emits a tool call, the main process executes it against the running MCP client and streams the result back. If a 401 appears during a call, the server is flagged in the DB so the UI can persistently show the "needs auth" badge.

## The non-obvious parts

- **8-second tool listing timeout is intentional:** MCP servers often start slowly (spawning Node processes, connecting to APIs). The UI must not block indefinitely; the timeout gives a hard failure so the user knows the server isn't responding, rather than the settings screen freezing.
- **Encryption for OAuth is asymmetric to settings:** API keys use `safeStorage` (Electron's OS keychain bridge). MCP OAuth tokens are encrypted the same way but managed separately, because they're per-server and can be revoked individually without touching the whole settings file.
- **Tool consent per-session reset option:** User consent is DB-persisted (survives restarts), but there's a "reset all consent" action. This matters for security — if a user installs a malicious MCP server and consents to its tools, they need a way to revoke that without deleting the server config.

## Related
- [[ai-chat-stream--from-dyad]] (where MCP tools are invoked during build mode)
- [[byok-settings--from-dyad]] (settings infrastructure MCP config sits alongside)
