# AI Agent with Tool Calling (build spec) — distilled from asyar

## Summary

Multi-provider LLM agent (OpenAI, Anthropic, Google, Ollama, OpenRouter, OpenAI-compatible) with a tool-calling loop. Built-in tools (calculator, clipboard, file I/O, shell, web fetch, launcher search) plus extension-registered tools plus MCP server tools. All registered in a flat `ToolRegistry`. Agentic loop: send messages+tools → execute tool_call responses → append result → repeat until text-only response or iteration limit. Streaming throughout. Privacy redaction runs before every LLM call.

## Core logic (inlined)

### Tool registry

```typescript
interface Tool {
  name: string
  description: string       // CRITICAL: LLM uses this to decide when to call
  inputSchema: JSONSchema   // JSON Schema for the arguments object
  handler: (args: Record<string, unknown>) => Promise<ToolResult>
}

interface ToolResult {
  content: string           // Text result shown in conversation
  isError: boolean
}

class ToolRegistry {
  private tools = new Map<string, Tool>()
  
  register(tool: Tool): void {
    this.tools.set(tool.name, tool)
  }
  
  getAll(): Tool[] {
    return [...this.tools.values()]
  }
  
  async execute(name: string, args: Record<string, unknown>): Promise<ToolResult> {
    const tool = this.tools.get(name)
    if (!tool) {
      return { content: `Tool not found: ${name}`, isError: true }
    }
    try {
      return await tool.handler(args)
    } catch (err) {
      return { content: `Tool error: ${err}`, isError: true }
    }
  }
}
```

### Built-in tool definitions

```typescript
const BUILT_IN_TOOLS: Tool[] = [
  {
    name: 'calculator',
    description: 'Evaluate a mathematical expression. Supports arithmetic, algebra, unit conversion, and currency conversion. Use for any numeric calculation.',
    inputSchema: {
      type: 'object',
      properties: {
        expression: { type: 'string', description: 'Math expression to evaluate, e.g. "100 USD to EUR" or "sqrt(144)"' }
      },
      required: ['expression']
    },
    handler: async ({ expression }) => {
      const result = evaluate(String(expression))  // mathjs evaluate()
      return { content: String(result), isError: false }
    }
  },
  {
    name: 'clipboard_read',
    description: 'Read the current clipboard text content. Use when the user says "the clipboard", "what I copied", or "my clipboard".',
    inputSchema: {
      type: 'object',
      properties: {},
      required: []
    },
    handler: async () => {
      const text = await invoke<string>('get_clipboard_text')
      return { content: text, isError: false }
    }
  },
  {
    name: 'clipboard_write',
    description: 'Write text to the clipboard. Use when the user asks to copy a result.',
    inputSchema: {
      type: 'object',
      properties: {
        text: { type: 'string', description: 'Text to write to clipboard' }
      },
      required: ['text']
    },
    handler: async ({ text }) => {
      await invoke('set_clipboard_text', { text })
      return { content: 'Copied to clipboard', isError: false }
    }
  },
  {
    name: 'web_fetch',
    description: 'Fetch the text content of a web page. Returns stripped plain text. Use for looking up current information.',
    inputSchema: {
      type: 'object',
      properties: {
        url: { type: 'string', format: 'uri', description: 'URL to fetch' }
      },
      required: ['url']
    },
    handler: async ({ url }) => {
      const content = await invoke<string>('fetch_url', { url: String(url) })
      return { content: content.slice(0, 8000), isError: false }  // truncate
    }
  },
  {
    name: 'shell_execute',
    description: 'Execute a shell command and return stdout. Use for running scripts, checking system state, or file operations the other tools don\'t cover.',
    inputSchema: {
      type: 'object',
      properties: {
        command: { type: 'string', description: 'Shell command to execute' },
        working_dir: { type: 'string', description: 'Working directory (optional)' }
      },
      required: ['command']
    },
    handler: async ({ command, working_dir }) => {
      const result = await invoke<ShellResult>('execute_command', { command, workingDir: working_dir })
      const output = result.stdout + (result.stderr ? `\nSTDERR: ${result.stderr}` : '')
      return { content: output, isError: result.exitCode !== 0 }
    }
  },
  // file_read, file_write, launcher_search follow same pattern
]
```

### Multi-provider abstraction

```typescript
interface ChatMessage {
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: string
  toolCallId?: string       // for role='tool' results
  toolCalls?: ToolCall[]    // for role='assistant' with tool calls
}

interface ToolCall {
  id: string
  name: string
  arguments: Record<string, unknown>
}

interface LLMProvider {
  chat(
    messages: ChatMessage[],
    tools: Tool[],
    options: { model: string; stream: boolean }
  ): AsyncIterable<LLMDelta>
}

interface LLMDelta {
  type: 'text' | 'tool_call' | 'tool_call_args' | 'done'
  text?: string
  toolCallId?: string
  toolName?: string
  argsChunk?: string        // streaming JSON fragment
}
```

### Anthropic provider adapter

```typescript
class AnthropicProvider implements LLMProvider {
  async *chat(
    messages: ChatMessage[],
    tools: Tool[],
    options: { model: string }
  ): AsyncIterable<LLMDelta> {
    const anthropicMessages = messages
      .filter(m => m.role !== 'system')
      .map(m => convertToAnthropicMessage(m))
    
    const systemMessage = messages.find(m => m.role === 'system')?.content
    
    const stream = await this.client.messages.stream({
      model: options.model,
      max_tokens: 4096,
      system: systemMessage,
      messages: anthropicMessages,
      tools: tools.map(t => ({
        name: t.name,
        description: t.description,
        input_schema: t.inputSchema,
      })),
    })
    
    for await (const event of stream) {
      if (event.type === 'content_block_delta') {
        if (event.delta.type === 'text_delta') {
          yield { type: 'text', text: event.delta.text }
        } else if (event.delta.type === 'input_json_delta') {
          yield { type: 'tool_call_args', argsChunk: event.delta.partial_json }
        }
      } else if (event.type === 'content_block_start') {
        if (event.content_block.type === 'tool_use') {
          yield { type: 'tool_call', toolCallId: event.content_block.id, toolName: event.content_block.name }
        }
      }
    }
    
    yield { type: 'done' }
  }
}
```

### Agentic loop

```typescript
const MAX_ITERATIONS = 10

async function runAgentLoop(
  messages: ChatMessage[],
  registry: ToolRegistry,
  provider: LLMProvider,
  model: string,
  onDelta: (delta: LLMDelta) => void
): Promise<ChatMessage[]> {
  const history = [...messages]
  
  // Apply privacy redaction before EVERY LLM call
  const redactedHistory = redactSecretsFromMessages(history)
  
  for (let i = 0; i < MAX_ITERATIONS; i++) {
    const pendingToolCalls = new Map<string, { name: string; argsBuffer: string }>()
    let assistantText = ''
    let finishedToolCalls: ToolCall[] = []
    
    // Stream LLM response
    for await (const delta of provider.chat(redactedHistory, registry.getAll(), { model, stream: true })) {
      onDelta(delta)  // stream to UI
      
      if (delta.type === 'text' && delta.text) {
        assistantText += delta.text
      } else if (delta.type === 'tool_call') {
        pendingToolCalls.set(delta.toolCallId!, { name: delta.toolName!, argsBuffer: '' })
      } else if (delta.type === 'tool_call_args') {
        const tc = pendingToolCalls.get(/* find current tool call id */)
        if (tc) tc.argsBuffer += delta.argsChunk
      } else if (delta.type === 'done') {
        // Finalize tool calls
        for (const [id, tc] of pendingToolCalls) {
          finishedToolCalls.push({
            id,
            name: tc.name,
            arguments: JSON.parse(tc.argsBuffer || '{}'),
          })
        }
      }
    }
    
    // Append assistant turn
    history.push({
      role: 'assistant',
      content: assistantText,
      toolCalls: finishedToolCalls.length > 0 ? finishedToolCalls : undefined,
    })
    
    // No tool calls = we're done
    if (finishedToolCalls.length === 0) break
    
    // Execute tool calls and append results
    for (const toolCall of finishedToolCalls) {
      const result = await registry.execute(toolCall.name, toolCall.arguments)
      history.push({
        role: 'tool',
        content: result.content,
        toolCallId: toolCall.id,
      })
    }
  }
  
  return history
}
```

## Data contracts

### Conversation stored in SQLite
```sql
CREATE TABLE conversations (
  id TEXT PRIMARY KEY,          -- UUID v4
  provider TEXT NOT NULL,       -- 'openai' | 'anthropic' | 'google' | 'ollama' | 'openrouter'
  model TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE TABLE messages (
  id TEXT PRIMARY KEY,
  conversation_id TEXT REFERENCES conversations(id),
  role TEXT NOT NULL,           -- 'system' | 'user' | 'assistant' | 'tool'
  content TEXT NOT NULL,
  tool_calls TEXT,              -- JSON array of ToolCall, nullable
  tool_call_id TEXT,            -- for role='tool', nullable
  tokens INTEGER,               -- estimated token count for context management
  created_at INTEGER NOT NULL
);
```

### Provider config (stored in OS keychain)
```typescript
interface ProviderConfig {
  id: string                    // 'openai' | 'anthropic' | 'google' | 'ollama' | 'openrouter' | 'custom'
  apiKey?: string               // stored in OS keychain by provider id
  baseUrl?: string              // for 'ollama' and 'custom' providers
  models: string[]              // available model IDs
  defaultModel: string
}
```

## Dependencies & assumptions

- **Tauri v2** — `invoke()` IPC for tool execution in Rust
- **mathjs** — calculator tool expression evaluation
- **Provider SDKs** — Anthropic SDK, OpenAI SDK (covers OpenRouter + custom endpoints)
- **SQLite** (rusqlite) — conversation history
- **OS keychain** (keyring crate) — API key storage
- Privacy redaction pipeline (see `pattern-based-secret-redaction--from-asyar`) must be available

## To port this, you need:

- [ ] `ToolRegistry` with `register(tool)` and `execute(name, args)` methods
- [ ] Tool definitions with `name`, `description`, `inputSchema` (JSON Schema), `handler`
- [ ] Provider abstraction: `chat(messages, tools, options) → AsyncIterable<LLMDelta>`
- [ ] Adapters for each provider normalizing tool call events to `LLMDelta` shape
- [ ] Agentic loop: iterate until text-only response or `MAX_ITERATIONS` reached
- [ ] Append tool results as `role='tool'` messages between iterations
- [ ] Privacy redaction before each `chat()` call
- [ ] SQLite schema for conversation + message persistence
- [ ] API keys in OS keychain (not config files)
- [ ] Context window trimming: drop oldest non-system messages when estimated tokens exceed limit

## Gotchas

**Tool `description` quality controls everything.** The LLM decides which tool to call based solely on the description. "Calculate math" is worse than "Evaluate a mathematical expression. Supports arithmetic, algebra, unit conversion, and currency conversion. Use for any numeric calculation." Invest time in descriptions.

**Stream argument accumulation.** Tool arguments arrive as streaming JSON fragments. You must buffer them per-tool-call-id and only parse the JSON when the stream indicates the tool call is complete. Partial JSON will throw if you parse early.

**Anthropic's multi-turn tool calling differs from OpenAI's.** Anthropic requires the `tool_result` turn to have `tool_use_id` matching the `tool_use` block id. OpenAI uses `function_call` and `function_call_result`. The abstraction layer must normalize this.

**MAX_ITERATIONS prevents infinite loops.** A misbehaving model could keep calling tools forever. Enforce a hard cap (10 is reasonable) and return what you have when it's hit.

**Ollama and local models often don't support tool calling.** Many quantized local models don't reliably output JSON function calls. Add a fallback: if tool calling fails, retry the same prompt without tools and return the text response.

## Origin (reference only)

- Repo: https://github.com/Xoshbin/asyar
- Key paths: `asyar-launcher/src-tauri/src/` (AI invocation Rust), `asyar-launcher/src-svelte/src/` (agent UI)
- Stack: Tauri v2, Rust, TypeScript, Svelte 5, SQLite, multiple LLM provider SDKs
