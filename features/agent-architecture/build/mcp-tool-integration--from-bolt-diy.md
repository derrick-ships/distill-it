# MCP Tool Integration (build spec) — distilled from bolt.diy

## Summary

Build a singleton `MCPService` that accepts an MCP server config, connects to each server via SSE (or stdio for Node.js), discovers available tools, and intercepts LLM tool calls during streaming to route them to the appropriate server. Config flows in from the client per-request; tools are injected into the system prompt before streaming.

## Core logic (inlined)

```typescript
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { SSEClientTransport } from '@modelcontextprotocol/sdk/client/sse.js';

// MCP config shape
interface MCPConfig {
  servers: Record<string, MCPServerConfig>;
}

interface MCPServerConfig {
  type: 'sse';
  url: string;
  headers?: Record<string, string>;
}

// (For Node.js environments, also support stdio:)
// interface MCPServerConfig { type: 'stdio'; command: string; args: string[]; env?: Record<string,string> }

class MCPService {
  private static _instance: MCPService;
  private clients = new Map<string, Client>();
  private tools = new Map<string, MCPTool[]>();

  static getInstance() {
    if (!MCPService._instance) MCPService._instance = new MCPService();
    return MCPService._instance;
  }

  async updateConfig(config: MCPConfig): Promise<MCPTool[]> {
    // Disconnect removed servers
    const newNames = new Set(Object.keys(config.servers));
    for (const [name, client] of this.clients) {
      if (!newNames.has(name)) {
        await client.close();
        this.clients.delete(name);
        this.tools.delete(name);
      }
    }

    // Connect new servers
    const allTools: MCPTool[] = [];
    for (const [name, cfg] of Object.entries(config.servers)) {
      if (this.clients.has(name)) {
        allTools.push(...(this.tools.get(name) ?? []));
        continue;
      }
      try {
        const client = new Client({ name: 'bolt-diy', version: '1.0.0' }, { capabilities: {} });
        const transport = cfg.type === 'sse'
          ? new SSEClientTransport(new URL(cfg.url), { headers: cfg.headers })
          : /* stdio */ createStdioTransport(cfg);

        await client.connect(transport);
        const { tools } = await client.listTools();
        const mcpTools = tools.map(t => ({ ...t, serverName: name }));
        this.clients.set(name, client);
        this.tools.set(name, mcpTools);
        allTools.push(...mcpTools);
      } catch (err) {
        console.warn(`MCP server "${name}" failed to connect:`, err);
      }
    }
    return allTools;
  }

  // Inject tool definitions into the system prompt
  getToolsSystemPrompt(): string {
    const allTools = [...this.tools.values()].flat();
    if (allTools.length === 0) return '';
    return `
Available external tools (call with JSON tool invocation syntax):
${allTools.map(t => `- ${t.name}: ${t.description}\n  Input schema: ${JSON.stringify(t.inputSchema)}`).join('\n')}
`;
  }

  // Execute a tool call from the LLM
  async executeTool(serverName: string, toolName: string, args: Record<string, unknown>): Promise<string> {
    const client = this.clients.get(serverName);
    if (!client) throw new Error(`MCP server "${serverName}" not connected`);
    const result = await client.callTool({ name: toolName, arguments: args });
    return result.content.map((c: any) => c.type === 'text' ? c.text : JSON.stringify(c)).join('\n');
  }

  // Find which server owns a tool
  findToolServer(toolName: string): string | undefined {
    for (const [serverName, tools] of this.tools) {
      if (tools.some(t => t.name === toolName)) return serverName;
    }
    return undefined;
  }
}

// In the chat API, before calling streamText:
async function processWithMCP(messages: CoreMessage[], mcpConfig?: MCPConfig) {
  if (!mcpConfig) return messages;
  const service = MCPService.getInstance();
  await service.updateConfig(mcpConfig);
  const toolsPrompt = service.getToolsSystemPrompt();
  if (!toolsPrompt) return messages;
  // Prepend tool definitions to system message
  const systemMsg = messages.find(m => m.role === 'system');
  if (systemMsg) {
    (systemMsg as any).content += '\n\n' + toolsPrompt;
  }
  return messages;
}
```

## Data contracts

```typescript
interface MCPTool {
  name: string;
  description: string;
  inputSchema: JSONSchema7;
  serverName: string; // which server owns this tool
}

// Config endpoint: POST /api/mcp-update-config
interface MCPConfigRequest {
  servers: Record<string, { type: 'sse'; url: string; headers?: Record<string,string>; }>;
}

// Tool call format in LLM response (parsed from streaming output)
interface ToolInvocation {
  toolName: string;
  args: Record<string, unknown>;
  toolCallId: string;
}
```

## Dependencies & assumptions

- `@modelcontextprotocol/sdk` — official MCP client SDK
- In browser/Cloudflare: only `SSEClientTransport` works (no filesystem to spawn processes)
- In Node.js (Electron build): `StdioClientTransport` also works for local tool servers
- Config sent with each request (server is stateless); singleton caches active connections

## To port this, you need:
- [ ] `npm install @modelcontextprotocol/sdk`
- [ ] Create `MCPService` singleton with `updateConfig()`, `getToolsSystemPrompt()`, `executeTool()`
- [ ] Add a settings UI for users to enter MCP server URLs and names
- [ ] POST config to `/api/mcp-update-config` when user saves settings
- [ ] In your chat API, call `processWithMCP()` before `streamText()`
- [ ] If the LLM returns a tool call in its response, route it to `executeTool()` and append the result as a `tool` message
- [ ] Add a health-check route `/api/mcp-check` that attempts to connect and list tools

## Gotchas

- **SSE connections drop in serverless**: Cloudflare Worker instances are ephemeral. Each request may get a new worker instance without cached connections. Keep `updateConfig` cheap by detecting unchanged server configs.
- **Tool name collisions**: if two servers expose a tool named `read_file`, your router breaks. Namespace tools as `{serverName}_{toolName}` and teach the LLM the namespaced names.
- **Long-running tool calls**: MCP tool execution can take seconds. The SSE connection to the LLM stays open, but your serverless timeout (Cloudflare: 30s) may fire. Set generous timeout or use Durable Objects.
- **Config validation**: don't trust the client-sent MCPConfig blindly. Validate that URLs are HTTPS and that the server name doesn't allow injection into the system prompt.

## Origin (reference only)

- Repo: https://github.com/stackblitz-labs/bolt.diy
- `app/lib/services/mcp.ts` — MCPService singleton
- `app/routes/api.mcp-update-config.ts` — config update endpoint
- `app/routes/api.mcp-check.ts` — health check endpoint
- `app/routes/api.chat.ts` — where `processToolInvocations` is called before streaming
