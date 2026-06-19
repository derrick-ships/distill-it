# Artifact Code Generation (build spec) — distilled from bolt.diy

## Summary

Implement a streaming XML parser that converts LLM output containing `<boltArtifact>` / `<boltAction>` tags into real-time file writes and shell executions inside a WebContainer. The parser is a state machine that intercepts tags character-by-character and fires callbacks on open/stream/close events.

## Core logic (inlined)

```typescript
// System prompt instruction (injected before user messages)
const ARTIFACT_SYSTEM_PROMPT = `
You can create and edit files, and run shell commands.
Wrap ALL file writes and commands inside ONE <boltArtifact> block.

<boltArtifact id="unique-id" title="Project Setup">
  <boltAction type="file" filePath="package.json">
  {
    "name": "my-app",
    "scripts": { "dev": "vite" }
  }
  </boltAction>
  <boltAction type="shell">
  npm install
  </boltAction>
  <boltAction type="shell">
  npm run dev
  </boltAction>
</boltArtifact>
`;

// Parser state machine
interface ParserCallbacks {
  onArtifactOpen: (id: string, title: string, type: string) => void;
  onArtifactClose: (id: string) => void;
  onActionOpen: (artifactId: string, action: ActionDescriptor) => void;
  onActionStream: (artifactId: string, actionId: string, chunk: string) => void;
  onActionClose: (artifactId: string, actionId: string) => void;
}

interface ActionDescriptor {
  id: string;
  type: 'file' | 'shell' | 'start';
  filePath?: string;
}

class StreamingMessageParser {
  #state: ParserState = { buffer: '', insideArtifact: false, insideAction: false, artifactCounter: 0 };
  #callbacks: ParserCallbacks;

  constructor(callbacks: ParserCallbacks) { this.#callbacks = callbacks; }

  parse(messageId: string, chunk: string): string {
    this.#state.buffer += chunk;
    let output = '';

    while (this.#state.buffer.length > 0) {
      if (!this.#state.insideArtifact) {
        const artifactStart = this.#state.buffer.indexOf('<boltArtifact');
        if (artifactStart === -1) {
          output += this.#state.buffer;
          this.#state.buffer = '';
          break;
        }
        output += this.#state.buffer.slice(0, artifactStart);
        const tagEnd = this.#state.buffer.indexOf('>', artifactStart);
        if (tagEnd === -1) break; // tag not yet complete, wait for more chunks
        const tag = this.#state.buffer.slice(artifactStart, tagEnd + 1);
        const id = `${messageId}-${this.#state.artifactCounter++}`;
        const title = extractAttribute(tag, 'title') ?? '';
        const type = extractAttribute(tag, 'type') ?? 'bundled';
        this.#callbacks.onArtifactOpen(id, title, type);
        this.#state.currentArtifactId = id;
        this.#state.insideArtifact = true;
        this.#state.buffer = this.#state.buffer.slice(tagEnd + 1);
      } else if (!this.#state.insideAction) {
        const actionStart = this.#state.buffer.indexOf('<boltAction');
        const artifactEnd = this.#state.buffer.indexOf('</boltArtifact>');
        if (artifactEnd !== -1 && (actionStart === -1 || artifactEnd < actionStart)) {
          this.#callbacks.onArtifactClose(this.#state.currentArtifactId!);
          this.#state.insideArtifact = false;
          this.#state.buffer = this.#state.buffer.slice(artifactEnd + '</boltArtifact>'.length);
          continue;
        }
        if (actionStart === -1) break;
        const tagEnd = this.#state.buffer.indexOf('>', actionStart);
        if (tagEnd === -1) break;
        const tag = this.#state.buffer.slice(actionStart, tagEnd + 1);
        const type = extractAttribute(tag, 'type') as 'file' | 'shell';
        const filePath = extractAttribute(tag, 'filePath');
        const actionId = `action-${Date.now()}`;
        this.#callbacks.onActionOpen(this.#state.currentArtifactId!, { id: actionId, type, filePath });
        this.#state.currentActionId = actionId;
        this.#state.insideAction = true;
        this.#state.buffer = this.#state.buffer.slice(tagEnd + 1);
      } else {
        const closeTag = this.#state.buffer.indexOf('</boltAction>');
        if (closeTag === -1) {
          // stream the chunk to the action
          this.#callbacks.onActionStream(this.#state.currentArtifactId!, this.#state.currentActionId!, this.#state.buffer);
          this.#state.buffer = '';
          break;
        }
        const content = this.#state.buffer.slice(0, closeTag);
        this.#callbacks.onActionStream(this.#state.currentArtifactId!, this.#state.currentActionId!, content);
        this.#callbacks.onActionClose(this.#state.currentArtifactId!, this.#state.currentActionId!);
        this.#state.insideAction = false;
        this.#state.buffer = this.#state.buffer.slice(closeTag + '</boltAction>'.length);
      }
    }
    return output; // non-artifact text returned for chat display
  }
}

function extractAttribute(tag: string, name: string): string | undefined {
  const match = tag.match(new RegExp(`${name}="([^"]*)"` ));
  return match?.[1];
}

// Execution handler (wires parser callbacks to WebContainer)
const parser = new StreamingMessageParser({
  onArtifactOpen(id, title) { addArtifactToUI(id, title); },
  onArtifactClose(id) { markArtifactComplete(id); },
  onActionOpen(artifactId, action) { addActionToUI(artifactId, action); },
  async onActionClose(artifactId, actionId) {
    const action = getAction(artifactId, actionId);
    if (action.type === 'file') {
      let content = action.content;
      // Strip markdown code fences if present
      content = content.replace(/^```[\w]*\n?/, '').replace(/\n?```$/, '');
      await webcontainer.fs.writeFile(action.filePath!, content, 'utf-8');
    } else if (action.type === 'shell') {
      await webcontainer.spawn('sh', ['-c', action.content]);
    }
  },
  onActionStream(artifactId, actionId, chunk) { appendToActionBuffer(artifactId, actionId, chunk); },
});
```

## Data contracts

```typescript
// LLM message shape (request body)
interface ChatRequest {
  messages: CoreMessage[];
  model: string;
  provider: string;
  files: Record<string, string>; // current file tree
  chatMode: 'discuss' | 'build';
  contextOptimization: boolean;
  maxLLMSteps: number;
  supabase?: { isConnected: boolean; credentials: SupabaseCredentials };
  designScheme?: { primaryColor: string; fontFamily: string; };
}

// SSE response format
type ProgressEvent =
  | { type: 'progress'; label: 'summary' | 'context' | 'response'; status: 'in-progress' | 'complete'; message: string }
  | { type: 'usage'; label: string; value: TokenUsage }
  | { type: 'error'; message: string };
```

## Dependencies & assumptions

- WebContainer must already be booted (see `webcontainer-runtime--from-bolt-diy.md`)
- Vercel AI SDK `streamText()` for the LLM call
- The model must be prompted to produce `<boltArtifact>` / `<boltAction>` tags
- Client reads the SSE stream and feeds text chunks to `StreamingMessageParser.parse()`

## To port this, you need:
- [ ] Write the system prompt teaching the model the XML schema
- [ ] Implement `StreamingMessageParser` state machine (states: outside, insideArtifact, insideAction)
- [ ] Wire `onActionClose` to WebContainer's `fs.writeFile` and `spawn`
- [ ] Strip markdown code fences before writing file content
- [ ] Add UI components for artifact cards (title, file list, command list, status badges)
- [ ] Handle the continuation loop when the model hits token limits mid-artifact

## Gotchas

- **Partial tags at chunk boundaries**: the state machine MUST buffer incomplete tags and wait for the closing `>` before processing. Never assume a chunk ends on a tag boundary.
- **Code fence stripping**: the model frequently wraps file content in triple backticks even though you told it not to. Always strip.
- **Shell action ordering matters**: `npm install` must complete before `npm run dev`. The system runs shell actions sequentially using `process.exit` promises.
- **`start` action type**: some versions use `type="start"` for long-running processes (dev servers). Treat it like `type="shell"` but don't await exit — it runs in background.
- **Max segments**: if a file is very large, the model may hit context limits mid-file. Detect partial artifacts and re-prompt with a continuation message.

## Origin (reference only)

- Repo: https://github.com/stackblitz-labs/bolt.diy
- `app/lib/runtime/message-parser.ts` — StreamingMessageParser
- `app/routes/api.chat.ts` — chat API, streaming, continuation logic
- `app/lib/.server/llm/stream-text.ts` — streamText bridge
- `app/components/workbench/` — UI for artifact display
