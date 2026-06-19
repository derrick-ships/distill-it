# MCP Tool Integration — from [bolt.diy](https://github.com/stackblitz-labs/bolt.diy)

> Domain: [[_domain]] · Source: https://github.com/stackblitz-labs/bolt.diy · NotebookLM:

## What it does

Bolt.diy supports connecting external tool servers via the Model Context Protocol (MCP). Users can configure MCP servers in settings — for example, a filesystem server, a database server, or a custom API wrapper. The AI then has access to those tools during conversations, letting it read files, query databases, or call APIs on the user's behalf, without any code changes to bolt itself.

## Why it exists

MCP is a standard interface for exposing tools to LLMs. By supporting MCP, bolt becomes extensible without modification — any tool a user wants to give the AI can be packaged as an MCP server and connected. This transforms bolt from a fixed-capability IDE into a platform where the AI's capabilities grow with the user's configuration.

## How it actually works

There's a singleton `MCPService` that manages all active MCP server connections. Configuration arrives via a POST to `api.mcp-update-config`, which accepts a JSON object typed as `MCPConfig`. The service applies the new config, discovers available tools from each server, and returns them.

When a chat turn begins, the chat API calls `mcpService.processToolInvocations()` before streaming the main response. This step lets the service inject available tool definitions into the system prompt so the LLM knows what tools exist. During generation, if the LLM decides to use a tool (formatted as a tool call in the AI SDK's standard format), the MCP service intercepts it, routes it to the right server, executes it, and returns the result as a tool result message. The conversation then continues with that result in context.

The `api.mcp-check.ts` route provides a health endpoint the UI can use to verify whether a configured MCP server is actually reachable and responding.

## The non-obvious parts

- **Singleton lifetime**: the MCPService lives for the duration of the server process. On Cloudflare Workers (serverless), a new singleton is created per worker instance. This means MCP connections are NOT persistent across requests — each request re-establishes connections based on the stored config.
- **Tool injection into system prompt**: MCP tools aren't passed as Vercel AI SDK `tools` parameter directly. The tool definitions are serialized and injected into the system prompt text, so even models that don't support native tool calling can use them.
- **Config storage**: the MCP config is stored in the browser's `localStorage` or settings store, not on the server. It's sent with each relevant API request. The server is stateless with respect to MCP config.
- **MCPConfig schema**: each entry maps a server name to its transport config. Typical transports are `stdio` (spawn a local process) or `sse` (connect to an HTTP server-sent events endpoint). In the browser/Cloudflare context, `sse` is the only usable transport since there's no filesystem to spawn processes.

## Related
- [[agent-output-contract--from-last30days-skill]] (similar pattern of tool contracts flowing to an AI agent)
- [[multi-provider-llm--from-bolt-diy]] (MCP tools are injected alongside the LLM provider setup)
- [[artifact-code-generation--from-bolt-diy]] (tool results can trigger new artifact generation)
