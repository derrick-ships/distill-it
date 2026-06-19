# serena

**Source:** https://github.com/oraios/serena  
**Product:** Serena — an IDE-like MCP toolkit for AI coding agents  
**Stack:** Python 3.11+, MCP (Model Context Protocol), Language Server Protocol, Flask, pygls, pywebview, Pydantic  
**License:** MIT  
**Date distilled:** 2026-06-19

## What it is

Serena is an MCP server that gives AI coding agents (Claude Code, Codex, Cursor, etc.) semantic, symbol-level understanding of code. Instead of grep and line-number edits, agents can find symbols by name path (`ClassName/method`), replace symbol bodies, rename across the entire codebase via LSP, check type diagnostics, and navigate reference hierarchies — for 40+ languages. It also includes a live web dashboard for monitoring agent activity in real time.

25.5k stars. Actively maintained by Oraios AI. Available as `pip install serena-agent` (Python 3.11+).

## Features distilled

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Semantic Symbol Tools | code-intelligence | [study](../features/code-intelligence/study/semantic-symbol-tools--from-serena.md) | [build](../features/code-intelligence/build/semantic-symbol-tools--from-serena.md) |
| Agent Dashboard | dev-tooling | [study](../features/dev-tooling/study/agent-dashboard--from-serena.md) | [build](../features/dev-tooling/build/agent-dashboard--from-serena.md) |

## Other notable features (not yet distilled)

- **MCP Server + Context/Mode System** — dynamic tool filtering via YAML-defined contexts and modes; composable per-session
- **Language Server Manager** — concurrent multi-language LSP startup, health monitoring, auto-restart
- **Markdown Memory System** — agents persist project knowledge across sessions in topic-organized `.md` files with cross-references
- **Multi-Project Management** — register multiple projects, run tools against external projects in isolation
- **Hooks System** — Claude Code hooks for session lifecycle and nudging agents toward symbolic tools over grep
- **JetBrains Backend** — alternative to LSP using the JetBrains IDE plugin for analysis and interactive debugging
