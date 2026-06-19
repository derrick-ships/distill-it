# Context Optimization — from [bolt.diy](https://github.com/stackblitz-labs/bolt.diy)

> Domain: [[_domain]] · Source: https://github.com/stackblitz-labs/bolt.diy · NotebookLM:

## What it does

As your project grows, the files in your bolt.diy session become too large to include in every message — that would be expensive and would push out earlier conversation context. The context optimization system automatically picks which files to include in each prompt using AI, and maintains a rolling summary of the conversation so the model doesn't lose track of decisions made 20 messages ago.

## Why it exists

LLMs have finite context windows, and every token costs money. A 1,000-file codebase can't fit in a prompt. But sending no files means the AI can't write coherent updates. The system navigates this tension: send the minimum relevant files, summarize what happened before, and let the AI tell you what it needs next.

## How it actually works

There are two complementary systems that run before each chat turn when `contextOptimization` is enabled:

**Chat Summarization** (`createSummary`): The system takes the full message history and condenses it into a structured summary covering: project overview, tech stack, key decisions made, in-progress features, known bugs, and user preferences. This summary replaces older messages in the conversation history — new turns only see the summary plus the last few exchanges. When a summary already exists (marked with a special `chatSummary` message type), the system extracts it and re-summarizes from there, layering.

**File Context Selection** (`selectContext`): An LLM receives the full list of available file paths plus the current context buffer (up to 5 files). It also receives the conversation summary and the user's latest message. Its job is to output `<includeFile path="...">` and `<excludeFile path="...">` XML tags — telling the system which files are worth including and which can be dropped. The system validates paths against the actual file list before applying changes.

The result is injected into the system prompt: the assistant sees only the files the selector chose, not the entire workspace.

## The non-obvious parts

- **The "5 file" cap is strict**: the prompt literally tells the LLM "only 5 files can be in the context buffer at a time." When it wants to add a 6th, it must first evict one with `<excludeFile>`. This forces prioritization.
- **Two separate LLM calls before the actual chat response**: each turn with context optimization enabled fires createSummary (one LLM call), then selectContext (another LLM call), then the main response (third call). Users see these as progress indicators in the UI.
- **Token tracking**: the system tracks cumulative token usage across all three calls and surfaces it in the SSE progress events so the UI can show cost information.
- **Gitignore-style filtering**: before passing the file list to the selector, the system filters it through an ignore pattern list (node_modules, .git, lockfiles, etc.). The selector never even sees irrelevant files.
- **The selector gets the summary too**: this means if the AI just learned that "we're building the auth flow," the file selector already knows to prioritize `auth/` files without needing to re-read the conversation.

## Related
- [[multi-provider-llm--from-bolt-diy]] (both summarization and selection use the LLM system)
- [[artifact-code-generation--from-bolt-diy]] (context optimization feeds selected files into code generation prompts)
- [[chat-persistence--from-bolt-diy]] (summaries are stored as special messages in IndexedDB)
