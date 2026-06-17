# Agent CLI Integration — from [open-design](https://github.com/nexu-io/open-design)

> Domain: [[_domain]] · Source: https://github.com/nexu-io/open-design · NotebookLM: 

## What it does

Open Design detects which AI coding agents you have installed (Claude Code, Cursor, GitHub Copilot, and 19+ others), lets you pick one, then runs your design brief through it while streaming the output live into a sandboxed preview in the UI. You see the agent thinking and building in real time.

## Why it exists

Open Design is explicitly "agent-native" — it's built around the assumption that a coding agent does the actual generation work, not a proprietary in-house model. This means users can use whichever agent they already have and trust. It also means the app gets better automatically as the agents improve.

## How it actually works

**Detection:** When the app starts (or when you run `open-design detect`), it scans your PATH for known agent binaries — `claude`, `cursor`, `gh copilot`, and 19+ others. If an agent isn't in PATH, you can set `HERMES_CLI_PATH` as a fallback. Each agent has a registered adapter that knows its binary name and how to check its version.

**Invocation:** The daemon builds a full prompt — your brief + skill instructions + design system — and passes it to the agent CLI as a command-line argument. The agent runs as a child process. The specific invocation varies by agent (Claude Code uses `claude --print <prompt>`, others vary).

**Streaming:** The agent's stdout streams back to the daemon, which relays it via Server-Sent Events (SSE) to the web UI. You see tool calls, thinking blocks, file writes, and text deltas in real time. Errors and process output come through too (`stdout`/`stderr` events).

**Preview:** When the agent writes an HTML file to the project directory, the daemon picks it up and renders it in a sandboxed `<iframe>` in the UI. The preview updates with a debounced hot-reload as the agent writes. What you see is the actual running code, not a screenshot.

**25+ subcommands:** The `od` CLI tool exposes `od media`, `od plugin`, `od mcp`, `od project`, `od automation`, `od research`, and more. It's a thin client — each subcommand POSTs to the running daemon's HTTP API. This lets the app be scripted and automated from the terminal.

**Recoverable exit codes:** If something goes wrong, the daemon exits with specific codes (64-75) that signal what happened — `daemon-not-running` (64), `capabilities-required` (65), and others. Agents and scripts can inspect these and decide whether to retry.

## The non-obvious parts

**The app doesn't generate designs itself.** Open Design is a coordinator and renderer. The actual design generation happens inside Claude Code (or whatever agent you chose). Open Design provides the skill instructions, injects the brand system, streams the output, and renders the preview. It's a harness, not a model.

**Some agents use ACP (Agent Client Protocol) JSON-RPC over stdio.** Not all agents stream plain text — some use a structured protocol with typed events (thinking, tool_call, file_write, completion). The daemon handles both formats.

**MCP gives agents tool access.** For agents that support MCP (Model Context Protocol), the daemon serves an MCP server so the agent can read project files, call design APIs, and write artifacts — all through a standardized tool interface. OAuth for MCP is daemon-hosted, not a browser popup.

## Related

- [[plugin-ecosystem--from-open-design]] (how agent adapters are registered)
- [[agentic-loop--from-open-design]] (the pipeline agents execute)
- [[local-first-architecture--from-open-design]] (the daemon HTTP server agents connect to)
