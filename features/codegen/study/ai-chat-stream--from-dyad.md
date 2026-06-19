# AI Chat Stream — from [dyad](https://github.com/dyad-sh/dyad)

> Domain: [[_domain]] · Source: https://github.com/dyad-sh/dyad · NotebookLM: 

## What it does

When you type a message in Dyad, the app streams a real-time response from whichever AI provider you've configured — OpenAI, Anthropic, Google, Amazon Bedrock, Azure, or xAI — and the assistant writes code directly into your local app files as it talks. You see the text appear word-by-word, and file changes land on disk before the turn is finished.

## Why it exists

This is the entire core of the product. Dyad is an AI app builder: the chat stream *is* the build action. Without streaming, the user would wait 30+ seconds for a silent response before seeing anything. Streaming makes it feel conversational and gives users early feedback to cancel if the AI is going in the wrong direction.

## How it actually works

**Turn start:** The renderer sends a "chat:stream:start" IPC message with the user's prompt, chat ID, any file/image attachments, and the chat mode (build / ask / plan / local-agent). The main process picks this up in `chat_stream_handlers.ts`.

**Context assembly:** Before calling the LLM, the handler assembles context:
- Loads the chat's message history, trimming it to a token budget (the "balanced" context mode keeps recent messages; "deep" mode keeps more history)
- If the user @mentioned files or apps, those file trees and contents are injected
- If code explorer is enabled and available, a TypeScript symbol index is queried and prepended
- MCP tool definitions are fetched and attached (build mode only)
- A mode-specific system prompt is prepended (build mode gets the file-writing prompt, ask mode gets the Q&A prompt, etc.)

**Streaming call:** The Vercel AI SDK's `streamText()` is invoked with the assembled messages, the selected model/provider, and the tool definitions. The SDK handles SSE chunking across all providers with a unified API.

**Chunk processing:** Each streamed chunk arrives as either text, a tool call, or a tool result. Text chunks are forwarded to the renderer immediately via `chat:stream:chunk` IPC events so the UI can render them. Tool calls (in build mode) trigger file-write operations mid-stream — the AI can emit `<dyad-write>`, `<dyad-search-replace>`, and `<dyad-add-dependency>` XML tags which are parsed and executed in real time.

**Post-processing fixes:** After the stream ends, the handler runs iterative refinement: it auto-fixes common search-replace failures (e.g., the AI's target string didn't exactly match the file) and closes any uncaught XML tags. Failures trigger a second LLM call with the error context injected.

**Response save:** The complete assistant message (plus all AI SDK message objects that include tool call/result pairs) is committed to SQLite. A commit hash is recorded if any files changed.

**Cancellation:** Every active stream is tracked by chat ID in an `AbortController` map. When the user clicks "stop", a "chat:stream:cancel" IPC message aborts the controller, partially-written file changes are preserved (not rolled back), and the truncated message is saved to DB.

## The non-obvious parts

- **Two message representations:** The chat DB stores *display* content (what the user sees) and *aiMessagesJson* (the full `ModelMessage[]` array including tool call objects from the AI SDK v6). The latter is needed to reconstruct context for the next turn without re-running tool calls.
- **Token budget trimming:** Context is cut from the *oldest* end, not summarized. The system estimates tokens per message and stops including older messages once the budget is exceeded. This means very long chats silently lose early context.
- **Mode-aware tools:** MCP tools are only provided to the LLM in "build" mode. In "ask" or "plan" mode, the same stream path runs but tools are omitted — cheaper, faster, no file side effects.
- **Attachment deduplication:** Images/files uploaded as attachments are SHA256-hashed and stored under `.dyad/media/<hash>.<ext>` — uploading the same screenshot twice doesn't create duplicates.
- **Partial cancel state:** Cancelling mid-stream saves the partial text but marks the message status so the UI shows the response as truncated, not complete.

## Related
- [[mcp-integration--from-dyad]] (tools invoked during build-mode chat)
- [[code-explorer--from-dyad]] (TypeScript symbol context injected pre-call)
- [[byok-settings--from-dyad]] (which provider/model is selected)
- [[dependency-manager--from-dyad]] (dependency XML tags parsed from stream output)
