# Artifact Code Generation — from [bolt.diy](https://github.com/stackblitz-labs/bolt.diy)

> Domain: [[_domain]] · Source: https://github.com/stackblitz-labs/bolt.diy · NotebookLM:

## What it does

When you tell bolt.diy "build a React todo app," the AI doesn't return a code block you copy-paste. Instead, it streams a response that contains structured XML tags wrapping files and shell commands. A streaming parser intercepts these tags in real time and immediately executes them: writing files to the in-browser filesystem, running `npm install`, starting `npm run dev`. By the time the AI finishes responding, your app is already running in the preview panel.

## Why it exists

The gap being bridged is between "AI output" and "working code." Most AI coding tools produce text that you have to read, parse, and manually apply. Bolt closes that gap by treating the AI response as a structured execution plan. The model is prompted to speak in a domain-specific language (the `boltArtifact` XML schema), and the client has a parser that interprets it as actions rather than text.

## How it actually works

The system prompt teaches the model to wrap its outputs in `<boltArtifact>` tags. Inside, individual operations are `<boltAction>` tags of two types:

- `<boltAction type="file" filePath="src/App.tsx">` — file write operation
- `<boltAction type="shell">` — shell command (install, build, start)

The `StreamingMessageParser` on the client processes the LLM stream character by character using a state machine. When it encounters `<boltArtifact`, it opens a new artifact context and generates a unique ID (`${messageId}-${counter}`). When it sees `<boltAction type="file"`, it starts accumulating file content. As content arrives in chunks, it streams directly to the workbench, so files appear as the AI writes them.

When the action closes (`</boltAction>`), the workbench executes immediately: for file actions, it calls `webcontainer.fs.writeFile()`. For shell actions, it calls `webcontainer.spawn()`. There's no queue — it's a callback chain: `onArtifactOpen → onActionOpen → onActionStream → onActionClose → onArtifactClose`.

The parser also strips markdown code fences (backticks) when they appear at the top of a file — the model sometimes wraps content in triple-backtick blocks out of habit, and the parser removes those before writing.

The chat interface renders the artifact as a collapsible card showing the files written and commands run, with a diff view available for changed files.

## The non-obvious parts

- **Two chat modes**: `discuss` mode doesn't execute actions (for conversations about code). `build` mode is where the execution pipeline runs. The system prompt changes based on mode.
- **LLM "reasoning" wrapping**: if the model supports reasoning/thinking output (like Claude's extended thinking), those tokens are wrapped in `<div class="__boltThought__">` tags before streaming to the client, so the UI can display them in a special collapsible block.
- **Max response segments**: if the model hits its token limit mid-response (e.g., while writing a long file), bolt appends the partial output as an assistant message and sends a continuation prompt, looping up to `MAX_RESPONSE_SEGMENTS` times. The parser handles this seamlessly because it tracks state across message segments.
- **Quick actions**: a `<bolt-quick-actions>` tag lets the model suggest follow-up prompts to the user as clickable buttons.
- **Design scheme**: the request can include a `designScheme` object (color palette, font choices) that gets injected into the system prompt, making the generated UI consistent with the user's brand.

## Related
- [[webcontainer-runtime--from-bolt-diy]] (the runtime that executes the generated files and commands)
- [[multi-provider-llm--from-bolt-diy]] (the LLM system that produces the artifact stream)
- [[context-optimization--from-bolt-diy]] (ensures the model gets the right files as context)
- [[scraper-code-generation--from-llm-scraper]] (LLM-driven code generation in a different domain)
