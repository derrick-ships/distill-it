# AI Agent with Tool Calling — from [asyar](https://github.com/Xoshbin/asyar)

> Domain: [[_domain]] · Source: https://github.com/Xoshbin/asyar · NotebookLM:

## What it does

Asyar embeds a full multi-provider AI agent directly in a command launcher. You type a message, and the agent can reason, call tools (calculator, clipboard, file I/O, shell commands, web fetch, launcher search), and compose multi-step responses. Supported providers include OpenAI, Anthropic, Google Gemini, Ollama (local), OpenRouter, and any OpenAI-compatible endpoint. Tool definitions come from three sources: 8 built-in system tools, tools registered by installed extensions, and MCP server tools auto-detected from Claude Desktop/Cursor/Cline/Continue/Zed configs.

## Why it exists

Most launcher AI integrations are thin wrappers that send your question to an LLM and display the text response. Asyar's agent is actually useful in a productivity context because it has *actions*: it can read your clipboard, run a calculation, search your installed apps, execute a shell script, fetch a web page. The tool-calling loop turns the launcher from a smart autocomplete into a genuine task executor. The bring-your-own-key design keeps your data local — requests go from your machine directly to the provider.

## How it actually works

**Conversation threading**: Each AI session starts a conversation thread stored in SQLite. Threads persist across launcher restarts, so you can resume mid-conversation. Thread metadata includes the provider, model, system prompt, and token counts per message.

**Multi-provider abstraction**: The provider layer normalizes the API differences between OpenAI, Anthropic, Google, and others. All providers expose the same `chat(messages, tools, stream) → AsyncIterator<Delta>` interface internally. For local providers (Ollama), the request goes to `localhost:11434`.

**Tool registration**: At startup, the launcher registers 8 built-in tools. Extension-provided tools are registered when extensions are activated. MCP server tools are discovered and registered when the MCP sidecar connects. All tools end up in the same registry as a flat list of `{ name, description, inputSchema, handler }` objects.

**Tool calling loop**: The agentic loop follows the standard function-calling pattern:
1. Send messages + tool definitions to the LLM
2. If the model returns a `tool_use` (Anthropic) or `function_call` (OpenAI) response, execute the named tool with the provided arguments
3. Append the tool result to the message history
4. Send the updated history back to the LLM
5. Repeat until the model returns a text-only response

The loop has a configurable maximum iteration limit (default 10) to prevent runaway tool chains.

**Built-in tools**:
- `calculator` — evaluates math expressions using mathjs; handles unit conversions and currency
- `clipboard_read` — reads the current clipboard content (after privacy redaction)
- `clipboard_write` — writes text to the clipboard
- `file_read` — reads a file from a user-selected path
- `file_write` — writes a file (requires confirmation)
- `shell_execute` — runs a shell command, streams output, returns stdout/stderr
- `web_fetch` — fetches a URL and returns the text content (HTML stripped)
- `launcher_search` — searches the launcher's installed apps and extensions

**Streaming responses**: All providers stream their output. The UI renders text as it arrives. Tool call arguments also stream (the model may emit partial JSON), and the launcher buffers them until the tool call is complete before executing.

## The non-obvious parts

**Privacy scrubbing before each LLM call.** The conversation history is passed through the same pattern-based redaction pipeline as clipboard content before it's included in the request. If an earlier turn contains a secret that slipped through earlier redaction, it's caught here.

**OpenAI-compatible endpoint as the catch-all.** Any provider that exposes the OpenAI chat completions API format works without additional code — just point the base URL to the custom endpoint. This supports hosted alternatives (Together AI, Fireworks, etc.) and locally-hosted models (LM Studio, Jan, etc.) with a single code path.

**Tool schemas follow JSON Schema.** Each tool's `inputSchema` is a JSON Schema object that the LLM uses to know what arguments to pass. Getting the schema right (good `description` fields, proper types, required vs. optional) is critical for the model to use tools correctly. Vague descriptions = wrong tool calls.

**MCP tools are dynamically registered.** MCP servers expose their own tool lists via the `tools/list` method. Asyar calls this at connection time and adds the results to the tool registry. The MCP sidecar handles the subprocess lifecycle; from the agent's perspective, MCP tools look identical to built-in tools.

**Conversation context window management.** Long threads can exceed the model's context limit. Asyar trims message history from the oldest end when the estimated token count approaches the limit, keeping the system prompt and recent messages intact.

## Related

- [[pattern-based-secret-redaction--from-asyar]] — scrubs AI context before each LLM call
- [[mcp-sidecar-auto-detection--from-asyar]] — how MCP tools get into the tool registry
- [[silent-ai-text-transform--from-asyar]] — a simpler, no-UI variant of the same LLM integration
- [[ai-rules-engine--from-inbox-zero]] — a more specialized tool-calling pattern (LLM selects rules then executes actions)
- [[provider-agnostic-llm--from-llm-scraper]] — the Vercel AI SDK abstraction pattern for multi-provider LLMs
