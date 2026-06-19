# MCP Integration (build spec) — distilled from dyad

## Summary

Build an MCP (Model Context Protocol) client manager inside a desktop app: store server configs in SQLite, spawn/connect servers on demand, list tools with a hard timeout, track per-tool user consent, handle OAuth flows (discovery + token store), classify errors into actionable categories, and pass consented tools to the AI SDK at chat time.

## Core logic (inlined)

```typescript
// --- SERVER STORAGE ---
// DB table: mcp_servers
interface McpServer {
  id: number
  name: string
  type: 'stdio' | 'sse' | 'streamable-http'
  // stdio: command + args
  command: string | null
  args: string[] | null
  // sse/http: url
  url: string | null
  // OAuth (encrypted in settings file, not in DB)
  oauthEnabled: boolean
  oauthConnected: boolean // derived, not stored
  createdAt: number
}

// DB table: mcp_tool_consent
interface McpToolConsent {
  id: number
  serverId: number
  toolName: string
  consented: boolean
  updatedAt: number
}

// --- PORT CHECK ---
async function isPortFreeOnBothLoopbacks(port: number): Promise<boolean> {
  const check = (host: string) => new Promise<boolean>((resolve) => {
    const server = net.createServer()
    server.once('error', () => resolve(false))
    server.once('listening', () => { server.close(); resolve(true) })
    server.listen(port, host)
  })
  const [ipv4, ipv6] = await Promise.all([check('127.0.0.1'), check('::1')])
  return ipv4 && ipv6
}

// --- CLIENT FACTORY ---
function createMcpClient(server: McpServer): Client {
  if (server.type === 'stdio') {
    return new Client(new StdioClientTransport({
      command: server.command!,
      args: server.args ?? [],
    }))
  } else {
    return new Client(new SSEClientTransport(new URL(server.url!)))
  }
}

// --- TOOL LISTING WITH TIMEOUT ---
async function listServerTools(server: McpServer): Promise<Tool[]> {
  const client = createMcpClient(server)
  const timeout = new Promise<never>((_, reject) =>
    setTimeout(() => reject(new Error('timeout')), 8000)
  )
  try {
    await Promise.race([client.connect(), timeout])
    const result = await Promise.race([client.listTools(), timeout])
    return result.tools
  } catch (err) {
    client.close() // dispose to prevent fd leaks
    throw err
  }
}

// --- ERROR CLASSIFICATION ---
function classifyOAuthError(err: unknown): 'discovery_failed' | 'other' {
  const msg = String(err).toLowerCase()
  if (
    msg.includes('well-known') ||
    msg.includes('does not implement oauth') ||
    (msg.includes('load') && msg.includes('metadata')) ||
    msg.includes('incompatible oidc') ||
    msg.includes('incompatible auth server')
  ) return 'discovery_failed'
  return 'other'
}

function looksLikeUnauthorized(err: unknown): boolean {
  const msg = String(err)
  return /unauthorized/i.test(msg) || /\b401\b/.test(msg)
}

// --- CONSENT MANAGEMENT ---
async function getConsentedTools(serverId: number): Promise<string[]> {
  const rows = await db.select().from(mcpToolConsent)
    .where(and(eq(mcpToolConsent.serverId, serverId), eq(mcpToolConsent.consented, true)))
  return rows.map(r => r.toolName)
}

async function setToolConsent(serverId: number, toolName: string, consented: boolean) {
  await db.insert(mcpToolConsent)
    .values({ serverId, toolName, consented, updatedAt: Date.now() })
    .onConflictDoUpdate({ target: [mcpToolConsent.serverId, mcpToolConsent.toolName],
      set: { consented, updatedAt: Date.now() } })
}

// --- PASS TOOLS TO AI SDK ---
// At chat stream time, fetch consented tools and convert to AI SDK format:
async function getMCPToolsForChat(): Promise<Record<string, Tool>> {
  const servers = await db.select().from(mcpServers)
  const toolMap: Record<string, Tool> = {}
  for (const server of servers) {
    const consentedNames = await getConsentedTools(server.id)
    if (consentedNames.length === 0) continue
    const allTools = await listServerTools(server) // uses cached client
    for (const tool of allTools) {
      if (consentedNames.includes(tool.name)) {
        toolMap[`${server.id}__${tool.name}`] = {
          description: tool.description,
          parameters: jsonSchema(tool.inputSchema),
          execute: async (params) => {
            const client = getOrCreateClient(server)
            return client.callTool({ name: tool.name, arguments: params })
          }
        }
      }
    }
  }
  return toolMap
}

// --- OAUTH FLOW ---
async function connectOAuth(serverId: number) {
  const server = await getServer(serverId)
  // 1. Probe for OAuth metadata
  const discovery = await discoverOAuthMetadata(server.url!)
  if (!discovery) throw new Error('discovery_failed')
  // 2. Generate PKCE + state
  const { codeVerifier, codeChallenge, state } = generatePKCE()
  // 3. Store encrypted pending state in settings
  writeEncryptedOAuthState(serverId, { codeVerifier, state })
  // 4. Open browser to auth URL
  shell.openExternal(buildAuthUrl(discovery, codeChallenge, state))
}

async function handleOAuthCallback(code: string, state: string) {
  const { serverId, codeVerifier } = readAndClearOAuthState(state)
  const tokens = await exchangeCodeForTokens(code, codeVerifier)
  writeEncryptedTokens(serverId, tokens)
  await db.update(mcpServers).set({ oauthEnabled: true })
    .where(eq(mcpServers.id, serverId))
}
```

## Data contracts

```typescript
// IPC: mcp:list-servers → McpServerView[]
interface McpServerView {
  id: number
  name: string
  type: 'stdio' | 'sse' | 'streamable-http'
  command: string | null
  args: string[] | null
  url: string | null
  oauthEnabled: boolean
  oauthConnected: boolean   // derived from encrypted token presence
}

// IPC: mcp:list-tools(serverId) → McpToolView[]
interface McpToolView {
  name: string
  description: string
  inputSchema: object
  consented: boolean
}

// IPC: mcp:set-consent(serverId, toolName, consented)
// IPC: mcp:connect-oauth(serverId)
// IPC: mcp:disconnect-oauth(serverId)
```

## Dependencies & assumptions

- **`@ai-sdk/mcp`** or **`@modelcontextprotocol/sdk`**: Client, StdioClientTransport, SSEClientTransport
- **Electron safeStorage** for encrypting OAuth tokens (or any KMS/keychain equivalent)
- **Drizzle ORM** + **better-sqlite3** for server/consent persistence
- **Node `net` module** for port availability checking
- OAuth discovery assumes standard `/.well-known/oauth-authorization-server` endpoint

## To port this, you need:

- [ ] DB tables: `mcp_servers` (server configs), `mcp_tool_consent` (per-tool opt-in)
- [ ] MCP client factory supporting stdio, SSE, and streamable-http transport types
- [ ] 8-second timeout wrapper around `client.connect()` + `client.listTools()` with forced close on timeout
- [ ] Tool consent UI (checkbox list per server, persisted to DB)
- [ ] Error classifier: `classifyOAuthError()` and `looksLikeUnauthorized()` for UI-actionable messages
- [ ] OAuth flow: discovery probe → PKCE generation → browser open → callback handler → token store
- [ ] Token encryption (Electron safeStorage or equivalent)
- [ ] Active client pool (don't reconnect on every call; cache client by server ID with cleanup)
- [ ] Chat integration: merge consented MCP tools into Vercel AI SDK `tools` param

## Gotchas

- **Dual loopback port check:** On Linux/macOS, binding `127.0.0.1` doesn't always bind `::1`. Check both or you'll get "address in use" errors with IPv6-default Node versions.
- **fd leaks on timeout:** If you timeout without calling `client.close()`, the subprocess or socket connection stays open. Always dispose on timeout/error.
- **Tool name collisions:** Multiple MCP servers might expose tools with the same name. Namespace them: `{serverId}__{toolName}` as the AI SDK tool key.
- **OAuth credentials must not appear in logs:** Encrypt before DB or settings write. The IPC handler for saving tokens should be unlogged.
- **Consent is sticky across sessions:** Users expect consent decisions to survive app restarts. Store in DB, not in-memory.
- **Discovery failures vs. auth failures:** Treating all MCP errors as "auth failed" leads to confusing UX. The classifier routes users to the right fix (disable OAuth vs. reconnect).

## Origin (reference only)
- Repo: https://github.com/dyad-sh/dyad
- Key files: `src/ipc/handlers/mcp_handlers.ts`, `src/ipc/handlers/mcp_error_classifiers.ts`
