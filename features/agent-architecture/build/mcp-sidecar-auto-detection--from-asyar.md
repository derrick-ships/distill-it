# MCP Sidecar Auto-Detection (build spec) — distilled from asyar

## Summary

Scan known config file locations for Claude Desktop, Cursor, Cline, Continue, and Zed to extract MCP server definitions. Normalize all formats to a common `McpServerConfig`. Rewrite `npx` → bundled `bun x` and `uvx` → bundled `uv tool run` to eliminate Node.js/Python dependencies. Launch servers as child processes, connect via stdio JSON-RPC, call `tools/list`, and register the results in the agent's tool registry under `mcp__<slug>__<toolname>` namespacing.

## Core logic (inlined)

### Config file scanning and parsing

```typescript
import * as fs from 'fs/promises'
import * as path from 'path'
import * as os from 'os'

interface McpServerConfig {
  id: string                    // Normalized slug: "github", "filesystem"
  name: string                  // Human-readable
  command: string               // e.g. "npx", "uvx", "/usr/local/bin/server"
  args: string[]                // e.g. ["-y", "@modelcontextprotocol/server-github"]
  env: Record<string, string>   // e.g. { GITHUB_TOKEN: "..." }
  source: 'claude-desktop' | 'cursor' | 'cline' | 'continue' | 'zed' | 'manual'
  transport: 'stdio' | 'http'
}

async function discoverMcpConfigs(): Promise<McpServerConfig[]> {
  const discovered: McpServerConfig[] = []
  
  // Try each source; silently skip if config file doesn't exist
  const parsers: Array<() => Promise<McpServerConfig[]>> = [
    parseClaudeDesktopConfig,
    parseCursorConfig,
    parseClineConfig,
    parseContinueConfig,
    parseZedConfig,
  ]
  
  for (const parser of parsers) {
    try {
      const configs = await parser()
      discovered.push(...configs)
    } catch (_) {
      // Config file missing or unparseable — skip silently
    }
  }
  
  return discovered
}

async function parseClaudeDesktopConfig(): Promise<McpServerConfig[]> {
  const configPath = process.platform === 'darwin'
    ? path.join(os.homedir(), 'Library/Application Support/Claude/claude_desktop_config.json')
    : path.join(process.env.APPDATA || '', 'Claude/claude_desktop_config.json')
  
  const raw = JSON.parse(await fs.readFile(configPath, 'utf-8'))
  const servers = raw.mcpServers as Record<string, {
    command: string;
    args?: string[];
    env?: Record<string, string>;
  }>
  
  return Object.entries(servers).map(([name, cfg]) => ({
    id: slugify(name),
    name,
    command: cfg.command,
    args: cfg.args ?? [],
    env: cfg.env ?? {},
    source: 'claude-desktop',
    transport: 'stdio',
  }))
}

async function parseCursorConfig(): Promise<McpServerConfig[]> {
  const configPath = path.join(os.homedir(), '.cursor/mcp.json')
  const raw = JSON.parse(await fs.readFile(configPath, 'utf-8'))
  
  // Cursor format: { mcpServers: [{ name, command, args, env }] }
  // OR same as Claude Desktop (object form) — handle both
  const servers = Array.isArray(raw.mcpServers)
    ? raw.mcpServers
    : Object.entries(raw.mcpServers || {}).map(([name, cfg]) => ({ name, ...(cfg as object) }))
  
  return servers.map((cfg: { name: string; command: string; args?: string[]; env?: Record<string, string> }) => ({
    id: slugify(cfg.name),
    name: cfg.name,
    command: cfg.command,
    args: cfg.args ?? [],
    env: cfg.env ?? {},
    source: 'cursor',
    transport: 'stdio',
  }))
}

// parseClineConfig, parseContinueConfig, parseZedConfig follow same pattern
// with their respective file paths and schema shapes

function slugify(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}
```

### Sidecar command rewriting

```typescript
// Sidecar binary paths (inside Tauri app bundle)
const SIDECAR_PATHS = {
  bun: resolveSidecarBinary('bun'),      // ships as bun-x86_64-apple-darwin etc.
  uv: resolveSidecarBinary('uv'),
}

function resolveSidecarBinary(name: string): string {
  // Tauri resolves sidecar binaries based on target triple
  // e.g. bun-aarch64-apple-darwin is available at runtime as "bun"
  return `${process.resourcesPath}/sidecar/${name}`
}

function rewriteCommandForSidecar(config: McpServerConfig): McpServerConfig {
  // npx <package> → bun x <package>
  if (config.command === 'npx') {
    return {
      ...config,
      command: SIDECAR_PATHS.bun,
      args: ['x', ...config.args.filter(a => a !== '-y')],  // bun x doesn't need -y
    }
  }
  
  // uvx <package> → uv tool run <package>
  if (config.command === 'uvx') {
    return {
      ...config,
      command: SIDECAR_PATHS.uv,
      args: ['tool', 'run', ...config.args],
    }
  }
  
  // node, python3, etc. — use as-is
  return config
}
```

### MCP subprocess manager (Rust/Tauri)

```rust
use std::process::{Command, Stdio};
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use serde_json::{json, Value};

pub struct McpProcess {
    pub id: String,
    stdin: tokio::process::ChildStdin,
    responses: tokio::sync::mpsc::Receiver<Value>,
}

impl McpProcess {
    pub async fn spawn(config: &McpServerConfig) -> Result<Self, McpError> {
        let mut child = tokio::process::Command::new(&config.command)
            .args(&config.args)
            .envs(&config.env)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()?;
        
        let stdout = child.stdout.take().unwrap();
        let stdin = child.stdin.take().unwrap();
        
        let (tx, rx) = tokio::sync::mpsc::channel(100);
        
        // Spawn reader task
        tokio::spawn(async move {
            let reader = BufReader::new(stdout);
            let mut lines = reader.lines();
            while let Ok(Some(line)) = lines.next_line().await {
                if let Ok(msg) = serde_json::from_str::<Value>(&line) {
                    let _ = tx.send(msg).await;
                }
            }
        });
        
        Ok(Self { id: config.id.clone(), stdin, responses: rx })
    }
    
    pub async fn list_tools(&mut self) -> Result<Vec<McpTool>, McpError> {
        // Send JSON-RPC request
        let request = json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        });
        
        let request_str = serde_json::to_string(&request)? + "\n";
        self.stdin.write_all(request_str.as_bytes()).await?;
        
        // Wait for response (with timeout)
        let response = tokio::time::timeout(
            std::time::Duration::from_secs(10),
            self.responses.recv()
        ).await??;
        
        let tools = response["result"]["tools"]
            .as_array()
            .unwrap_or(&vec![])
            .iter()
            .map(|t| McpTool {
                name: t["name"].as_str().unwrap_or("").to_string(),
                description: t["description"].as_str().unwrap_or("").to_string(),
                input_schema: t["inputSchema"].clone(),
            })
            .collect();
        
        Ok(tools)
    }
    
    pub async fn call_tool(
        &mut self,
        tool_name: &str,
        arguments: Value,
    ) -> Result<String, McpError> {
        let request = json!({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        });
        
        let request_str = serde_json::to_string(&request)? + "\n";
        self.stdin.write_all(request_str.as_bytes()).await?;
        
        let response = tokio::time::timeout(
            std::time::Duration::from_secs(30),
            self.responses.recv()
        ).await??;
        
        // MCP returns content array: [{ type: "text", text: "..." }]
        let text = response["result"]["content"]
            .as_array()
            .and_then(|arr| arr.first())
            .and_then(|item| item["text"].as_str())
            .unwrap_or("")
            .to_string();
        
        Ok(text)
    }
}
```

### Tool registration in agent registry

```typescript
async function registerMcpTools(
  process: McpProcess,
  registry: ToolRegistry
): Promise<void> {
  const tools = await process.listTools()
  
  for (const mcpTool of tools) {
    // Namespace: mcp__<server-slug>__<tool-name>
    const registeredName = `mcp__${process.id}__${mcpTool.name}`
    
    registry.register({
      name: registeredName,
      description: `[${process.id} MCP] ${mcpTool.description}`,
      inputSchema: mcpTool.inputSchema,
      handler: async (args) => {
        const result = await process.callTool(mcpTool.name, args)
        return { content: result, isError: false }
      }
    })
  }
}
```

### Restart with exponential backoff

```rust
pub async fn manage_mcp_server(
    config: McpServerConfig,
    registry: Arc<Mutex<ToolRegistry>>,
) {
    let mut backoff_ms = 1000u64;
    
    loop {
        match McpProcess::spawn(&config).await {
            Ok(mut process) => {
                backoff_ms = 1000; // Reset backoff on successful start
                
                // Register tools
                if let Ok(tools) = process.list_tools().await {
                    let mut reg = registry.lock().await;
                    reg.register_mcp_tools(&config.id, tools, &mut process);
                }
                
                // Wait for process to die
                process.wait().await;
                
                // Unregister tools
                registry.lock().await.unregister_mcp(&config.id);
            }
            Err(e) => {
                eprintln!("Failed to start MCP server {}: {}", config.id, e);
            }
        }
        
        // Exponential backoff: 1s, 2s, 4s, 8s, max 60s
        tokio::time::sleep(Duration::from_millis(backoff_ms)).await;
        backoff_ms = (backoff_ms * 2).min(60_000);
    }
}
```

## Data contracts

### McpServerConfig (normalized form)
```typescript
interface McpServerConfig {
  id: string                    // kebab-case slug
  name: string                  // original name from source config
  command: string               // absolute path or shell command
  args: string[]
  env: Record<string, string>
  source: 'claude-desktop' | 'cursor' | 'cline' | 'continue' | 'zed' | 'manual'
  transport: 'stdio' | 'http'
  enabled: boolean
}
```

### MCP JSON-RPC protocol (stdio transport)
```
Client → Server (newline-delimited JSON):
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"create_issue","arguments":{...}}}

Server → Client:
{"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"create_issue","description":"...","inputSchema":{...}}]}}
{"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"Issue #42 created"}]}}
```

## Dependencies & assumptions

- **Tauri v2** — sidecar binary bundling (`tauri.conf.json` `externalBin` array)
- **Rust**: `tokio::process::Command`, `serde_json`
- **Bundled binaries**: `bun` (per platform/arch), `uv` (per platform/arch) — add to Tauri's `externalBin`
- MCP servers speak stdio JSON-RPC (the majority do; HTTP transport is secondary)
- Config file locations are hardcoded per known AI tool (update this list as ecosystem grows)

## To port this, you need:

- [ ] Config file paths per tool (Claude Desktop, Cursor, Cline, Continue, Zed — see paths above)
- [ ] A parser per config format that normalizes to `McpServerConfig`
- [ ] Command rewriting: `npx` → bundled bun, `uvx` → bundled uv (or system Node/Python fallback)
- [ ] Bundled `bun` and `uv` binaries per supported platform (macOS arm64/x64, Windows x64, Linux x64)
- [ ] A `McpProcess` that manages stdio subprocess + JSON-RPC request/response correlation
- [ ] Initialize handshake before `tools/list` (some servers require it)
- [ ] Tool registration under `mcp__<slug>__<name>` namespace
- [ ] Restart loop with exponential backoff on subprocess death
- [ ] UI to display detected servers and let user import/enable/disable

## Gotchas

**Initialize handshake is required by spec.** Before sending `tools/list`, send `initialize` with `protocolVersion` and wait for the `initialize` response. Many servers will ignore `tools/list` if they haven't been initialized.

**MCP responses are not always line-delimited.** Some servers emit multi-line JSON. Use a proper JSON parser that handles partial inputs, or require newline-delimited JSON and log warnings when the assumption breaks.

**Environment variable secrets.** MCP configs often contain API keys in the `env` block (e.g., `GITHUB_TOKEN`). Parse and store these in the OS keychain, not in plaintext config storage.

**Sidecar binary permissions on Linux.** Extracted sidecar binaries may not have execute permission. Call `chmod +x` after extraction.

**`bun x` cache.** The first `bun x` call for a package downloads it to a cache directory. Subsequent calls are instant. This first-run latency can surprise users — show a "Downloading..." indicator.

**Different MCP server versions.** The MCP protocol is evolving. `protocolVersion: "2024-11-05"` is current as of this writing. Add version negotiation if you need to support older servers.

## Origin (reference only)

- Repo: https://github.com/Xoshbin/asyar
- Key paths: `asyar-launcher/src-tauri/src/` (Rust MCP process management), `asyar-launcher/src-svelte/src/` (config import UI)
- Stack: Tauri v2, Rust, TypeScript, bundled Bun + uv sidecars
