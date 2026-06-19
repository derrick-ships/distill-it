# Context Optimization (build spec) — distilled from bolt.diy

## Summary

Implement two pre-turn LLM calls: (1) `createSummary` collapses old conversation history into a structured summary; (2) `selectContext` uses AI to pick ≤5 relevant files from the project to include in the prompt. Both run before the main chat response, triggered when `contextOptimization: true`.

## Core logic (inlined)

```typescript
// === PART 1: Chat Summarization ===

async function createSummary(messages: CoreMessage[], options: LLMOptions): Promise<string> {
  // Find existing summary if any
  const existingSummaryMsg = messages.find(m => (m as any).type === 'chatSummary');
  const existingSummary = existingSummaryMsg ? extractSummaryText(existingSummaryMsg) : '';
  
  // Strip bolt actions and thinking blocks (reduce noise)
  const cleanedMessages = messages
    .filter(m => m.role !== 'chatSummary' as any)
    .map(m => ({
      ...m,
      content: typeof m.content === 'string'
        ? m.content.replace(/<boltAction[^>]*>[\s\S]*?<\/boltAction>/g, '[file/command]')
                   .replace(/<div class="__boltThought__">[\s\S]*?<\/div>/g, '')
        : m.content,
    }));

  const summaryPrompt = `
Create a concise project summary covering:
1. Project context: overview, tech stack, current phase
2. Conversation highlights: key decisions, user preferences  
3. Implementation progress: what's done, in-progress, blocked
4. Requirements: completed features, pending items, constraints
5. Critical knowledge: gotchas, unresolved questions

${existingSummary ? `Previous summary:\n${existingSummary}\n\nNew messages to integrate:` : 'Messages:'}
`;

  const { text } = await generateText({
    ...options,
    messages: [
      { role: 'system', content: summaryPrompt },
      ...cleanedMessages.slice(-20), // last 20 messages max
    ],
  });

  return text;
}

// === PART 2: File Context Selection ===

async function selectContext(
  messages: CoreMessage[],
  files: Record<string, string>,
  summary: string,
  contextBuffer: Set<string>,
  options: LLMOptions,
): Promise<Set<string>> {
  // Filter out noise files (gitignore-style)
  const IGNORE_PATTERNS = ['node_modules/**', '.git/**', '*.lock', 'dist/**', 'build/**'];
  const availableFiles = Object.keys(files).filter(p => !matchesIgnore(p, IGNORE_PATTERNS));

  const selectionPrompt = `
You manage a context buffer of max 5 files. Current buffer:
${[...contextBuffer].map(f => `- ${f}`).join('\n') || '(empty)'}

Available files:
${availableFiles.join('\n')}

Project summary:
${summary}

Latest user message: ${getLastUserMessage(messages)}

Output ONLY XML tags to update the buffer:
<includeFile path="path/to/file.ts"/>   (add to buffer)
<excludeFile path="path/to/old.ts"/>    (remove from buffer)

Rules:
- Max 5 files at a time. Exclude before adding if at capacity.
- Only include files directly relevant to the current task.
- Prefer files the user is actively discussing or editing.
`;

  const { text } = await generateText({
    ...options,
    messages: [{ role: 'user', content: selectionPrompt }],
  });

  // Parse XML tags
  const includes = [...text.matchAll(/<includeFile\s+path="([^"]+)"/g)].map(m => m[1]);
  const excludes = [...text.matchAll(/<excludeFile\s+path="([^"]+)"/g)].map(m => m[1]);

  const updated = new Set(contextBuffer);
  excludes.forEach(p => { if (availableFiles.includes(p)) updated.delete(p); });
  includes.forEach(p => { if (availableFiles.includes(p) && updated.size < 5) updated.add(p); });

  return updated;
}

// === Wire into chat API ===

async function handleChatTurn(req: ChatRequest) {
  let messages = req.messages;
  let contextBuffer = new Set<string>();
  let tokenUsage = { prompt: 0, completion: 0 };

  if (req.contextOptimization) {
    // Step 1: summarize
    emitProgress('summary', 'in-progress');
    const summary = await createSummary(messages, llmOptions);
    tokenUsage.prompt += summaryUsage.promptTokens;
    emitProgress('summary', 'complete');

    // Step 2: select context  
    emitProgress('context', 'in-progress');
    contextBuffer = await selectContext(messages, req.files, summary, contextBuffer, llmOptions);
    emitProgress('context', 'complete');

    // Inject selected files into system prompt
    messages = injectFilesIntoSystemPrompt(messages, req.files, contextBuffer);
  }

  // Step 3: main response
  emitProgress('response', 'in-progress');
  const stream = streamText({ messages, ...llmOptions });
  // pipe to client...
}
```

## Data contracts

```typescript
// Context optimization inputs
interface ContextOptimizationOptions {
  contextOptimization: boolean;  // feature flag
  files: Record<string, string>; // full file tree {path: content}
  messages: CoreMessage[];
}

// SSE progress events for UI
type ProgressEvent = {
  type: 'progress';
  label: 'summary' | 'context' | 'response';
  status: 'in-progress' | 'complete';
  message?: string;
};

// Summary stored as special message in history
interface SummaryMessage {
  role: 'assistant';
  type: 'chatSummary';         // custom type flag
  content: string;             // the summary text
  chatId: string;
}
```

## Dependencies & assumptions

- Same LLM provider as main chat (reuses `streamText` / `generateText`)
- `ignore` npm package for gitignore-style filtering
- File tree available at chat turn time
- Summary stored as a special message type in IndexedDB (see `chat-persistence--from-bolt-diy.md`)

## To port this, you need:
- [ ] Implement `createSummary()` that strips bolt actions and produces structured text
- [ ] Implement `selectContext()` with XML parsing for include/exclude tags
- [ ] Add `contextOptimization: boolean` field to chat request
- [ ] Emit SSE progress events for each step so the UI can show spinners
- [ ] Store the summary as a `chatSummary`-typed message in your persistence layer
- [ ] Apply gitignore-style filtering to the file list before passing to selector
- [ ] Enforce the 5-file cap in the selection logic (not just the prompt)

## Gotchas

- **Two extra LLM calls per turn**: this roughly triples LLM costs. Make it opt-in and clearly label it in the UI.
- **Summary drift**: after many summarize-then-summarize cycles, the summary can lose precision. Track the raw message count and occasionally include a wider window.
- **File selector hallucination**: the LLM may output paths that don't exist. Always validate against `Object.keys(files)` before applying.
- **Message filtering**: strip the `chatSummary` message from history before re-summarizing, or you'll double-summarize and bloat the summary.

## Origin (reference only)

- Repo: https://github.com/stackblitz-labs/bolt.diy
- `app/lib/.server/llm/create-summary.ts` — createSummary
- `app/lib/.server/llm/select-context.ts` — selectContext
- `app/routes/api.chat.ts` — orchestration of the three-step pipeline
