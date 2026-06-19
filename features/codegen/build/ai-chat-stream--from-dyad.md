# AI Chat Stream (build spec) — distilled from dyad

## Summary

Build a real-time LLM chat stream that routes to multiple AI providers via a unified SDK, assembles rich context (history, file contents, MCP tools, code index) before each turn, parses AI-emitted XML action tags from the stream to trigger file writes mid-response, and saves both display content and full SDK message objects to a SQLite DB. Designed for Electron (IPC-based) but the core logic is framework-agnostic.

## Core logic (inlined)

```typescript
// --- TURN START ---
// Renderer sends: { chatId, prompt, attachments, chatMode }

// 1. RESOLVE MODEL
const settings = readEffectiveSettings()
const provider = getAIProvider(settings.selectedProvider, settings.apiKeys)
const model = provider.languageModel(settings.selectedModel)

// 2. ASSEMBLE MESSAGES
const history = await db.select().from(messages)
  .where(eq(messages.chatId, chatId))
  .orderBy(asc(messages.createdAt))

// Trim history to token budget (drop oldest first)
const trimmedHistory = trimToTokenBudget(history, MAX_CONTEXT_TOKENS)

// Build AI SDK message array
const aiMessages: CoreMessage[] = [
  { role: 'system', content: buildSystemPrompt(chatMode, codeExplorerIndex) },
  ...trimmedHistory.map(toAISDKMessage),
  { role: 'user', content: buildUserContent(prompt, attachments) }
]

// 3. ATTACH TOOLS (build mode only)
const tools = chatMode === 'build' ? await getMCPTools(consentedOnly=true) : undefined

// 4. STREAM
const abortController = new AbortController()
activeStreams.set(chatId, abortController)

const { textStream, fullStream } = streamText({
  model,
  messages: aiMessages,
  tools,
  abortSignal: abortController.signal,
})

// 5. PROCESS CHUNKS
let fullText = ''
for await (const chunk of fullStream) {
  if (chunk.type === 'text-delta') {
    fullText += chunk.textDelta
    // Forward to renderer
    mainWindow.webContents.send('chat:stream:chunk', { chatId, delta: chunk.textDelta })
    // Parse XML action tags from accumulated text (streaming parse)
    await processActionTags(fullText, appPath, chatId)
  } else if (chunk.type === 'tool-call') {
    await executeMCPToolCall(chunk, chatId)
  }
}

// 6. POST-PROCESSING
// Fix failed search-replace operations (retry with LLM)
const fixedText = await applyIterativeRefinement(fullText, appPath)

// Close any unclosed XML tags
const finalText = closeUnclosedTags(fixedText)

// 7. SAVE TO DB
await db.insert(messages).values({
  chatId,
  role: 'assistant',
  content: finalText,                    // display content (with result tags)
  aiMessagesJson: JSON.stringify(         // full SDK format for next-turn context
    await collectAIMessages(fullStream)
  ),
  commitHash: await getCurrentGitHash(appPath),
})

// 8. CANCEL PATH
ipcMain.handle('chat:stream:cancel', (_, { chatId }) => {
  activeStreams.get(chatId)?.abort()
  activeStreams.delete(chatId)
  // partial text already saved progressively
})
```

**XML action tag parsing (mid-stream):**
```typescript
// Tags emitted by LLM inside response text:
// <dyad-write filename="src/App.tsx">...file content...</dyad-write>
// <dyad-search-replace>
//   <search>old code</search><replace>new code</replace>
// </dyad-search-replace>
// <dyad-add-dependency packages="react-query framer-motion">

function processActionTags(text: string, appPath: string, chatId: string) {
  const writeMatches = text.matchAll(/<dyad-write filename="(.+?)">([\s\S]*?)<\/dyad-write>/g)
  for (const [, filename, content] of writeMatches) {
    const safePath = path.join(appPath, filename)
    if (!safePath.startsWith(appPath)) continue // path traversal guard
    fs.writeFileSync(safePath, content)
    git.add(safePath)
  }

  const depMatches = text.matchAll(/<dyad-add-dependency packages="(.+?)">/g)
  for (const [, packages] of depMatches) {
    await executeAddDependency(packages.split(' '), appPath)
  }
}
```

## Data contracts

```typescript
// DB: messages table
interface Message {
  id: number
  chatId: number
  role: 'user' | 'assistant'
  content: string              // display text (post-processed, tags replaced with results)
  aiMessagesJson: string | null // JSON of ModelMessage[] (AI SDK v6 format) for tool calls
  commitHash: string | null    // git hash at time of message
  maxTokensUsed: number | null
  createdAt: number            // unix timestamp
}

// DB: chats table
interface Chat {
  id: number
  appId: number
  title: string
  chatMode: 'build' | 'ask' | 'plan' | 'local-agent' | null
  createdAt: number
}

// IPC: chat:stream:start
interface StreamStartPayload {
  chatId: number
  prompt: string
  attachments: { filename: string; content: string; mimeType: string }[]
  chatMode: ChatMode
  contextMode: 'balanced' | 'deep'
}

// IPC: chat:stream:chunk
interface StreamChunkPayload {
  chatId: number
  delta: string
}
```

## Dependencies & assumptions

- **Vercel AI SDK** (`ai` package, v3+): `streamText`, `CoreMessage`, `ModelMessage` types
- **Provider packages**: `@ai-sdk/openai`, `@ai-sdk/anthropic`, `@ai-sdk/google`, `@ai-sdk/bedrock`, `@ai-sdk/azure`, `@ai-sdk/xai`
- **Drizzle ORM** + **better-sqlite3** for DB
- **Electron**: IPC for renderer↔main communication (can adapt to HTTP/WebSocket for non-Electron)
- **Git**: commit after file writes (dugite or simple-git)
- **AbortController**: native in Node 18+

## To port this, you need:

- [ ] Multi-provider AI SDK integration (Vercel AI SDK recommended for unified interface)
- [ ] SQLite schema: `messages` table with `aiMessagesJson` column for full SDK message objects
- [ ] IPC or WebSocket channel for streaming chunks to UI
- [ ] AbortController map keyed by session/chat ID for cancellation
- [ ] XML action tag parser (streaming-aware — tags may span multiple chunks)
- [ ] Path sanitization on all file writes (prevent directory traversal)
- [ ] Token budget trimmer for history (estimate tokens per message, drop oldest)
- [ ] Mode-specific system prompts (build/ask/plan have different instructions)
- [ ] Post-stream iterative refinement loop for failed search-replace

## Gotchas

- **Streaming XML parsing:** Tags from the LLM span multiple chunks. Buffer the full accumulated text and use regex with the `g` flag + track processed offsets. Don't try to parse partial tags.
- **aiMessagesJson is non-trivial:** The AI SDK's `ModelMessage[]` includes tool call objects with IDs that must be preserved for the next turn. If you serialize only the text, tool call context is lost and the LLM will repeat or hallucinate tool calls.
- **Search-replace failure rate:** LLMs frequently emit slightly wrong target strings for search-replace. Budget for a second LLM call to fix failures. Without this, code edits silently fail ~15-20% of the time.
- **Abort doesn't roll back:** Aborting a stream mid-way leaves partial file writes on disk. This is intentional (partial progress is better than nothing) but means the git working tree may be in an intermediate state.
- **safeStorage encryption is machine-specific:** API keys encrypted with Electron safeStorage can't be decrypted on a different machine. Don't try to sync the settings file.

## Origin (reference only)
- Repo: https://github.com/dyad-sh/dyad
- Key files: `src/ipc/handlers/chat_stream_handlers.ts`, `src/ipc/handlers/chat_mode_resolution.ts`, `src/ipc/processors/response_processor.ts`
