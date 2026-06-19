# asyar

**Source**: https://github.com/Xoshbin/asyar  
**Distilled**: 2026-06-18  
**Status**: Distilled

## What it is

A privacy-first, open-source command launcher (Raycast alternative) built with Tauri v2 + Svelte 5. Runs natively on macOS, Windows, and Linux without cloud accounts. Features a full multi-provider AI agent with tool calling, a sandboxed extension system with TypeScript SDK, a clipboard manager with pattern-based secret redaction, MCP auto-detection from Claude Desktop/Cursor/Cline, and silent hotkey-triggered text transformations. AGPLv3.

## Stack

- **Backend**: Rust, Tauri v2, Tokio async runtime
- **Frontend**: Svelte 5, TailwindCSS 4, Vite 6, TypeScript
- **Extension SDK**: TypeScript, Commander CLI, Chokidar
- **Storage**: SQLite (rusqlite), OS Keychain (keyring crate)
- **Build**: pnpm monorepo, Cargo, Tauri CLI
- **AI Providers**: OpenAI, Anthropic, Google Gemini, Ollama, OpenRouter, OpenAI-compatible
- **Language split**: 45% TypeScript, 42% Rust, 10% Svelte

## Distilled features

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Sandboxed Extension System | plugin-architecture | [study](../features/plugin-architecture/study/sandboxed-extension-system--from-asyar.md) | [build](../features/plugin-architecture/build/sandboxed-extension-system--from-asyar.md) |
| AI Agent with Tool Calling | ai-integration | [study](../features/ai-integration/study/ai-agent-tool-calling--from-asyar.md) | [build](../features/ai-integration/build/ai-agent-tool-calling--from-asyar.md) |
| Pattern-Based Secret Redaction | privacy | [study](../features/privacy/study/pattern-based-secret-redaction--from-asyar.md) | [build](../features/privacy/build/pattern-based-secret-redaction--from-asyar.md) |
| MCP Sidecar Auto-Detection | agent-architecture | [study](../features/agent-architecture/study/mcp-sidecar-auto-detection--from-asyar.md) | [build](../features/agent-architecture/build/mcp-sidecar-auto-detection--from-asyar.md) |
| Silent AI Text Transform | ai-workflow | [study](../features/ai-workflow/study/silent-ai-text-transform--from-asyar.md) | [build](../features/ai-workflow/build/silent-ai-text-transform--from-asyar.md) |
| Command-Palette Launcher | launcher | [study](../features/launcher/study/command-palette-launcher--from-asyar.md) | [build](../features/launcher/build/command-palette-launcher--from-asyar.md) |
| Alias System | launcher | [study](../features/launcher/study/alias-system--from-asyar.md) | [build](../features/launcher/build/alias-system--from-asyar.md) |
| Snippets / Text Expansion | productivity | [study](../features/productivity/study/snippets-text-expansion--from-asyar.md) | [build](../features/productivity/build/snippets-text-expansion--from-asyar.md) |
| Deep Link Command Triggers | platform | [study](../features/platform/study/deep-link-command-triggers--from-asyar.md) | [build](../features/platform/build/deep-link-command-triggers--from-asyar.md) |
| Background Command Scheduling | platform | [study](../features/platform/study/background-command-scheduling--from-asyar.md) | [build](../features/platform/build/background-command-scheduling--from-asyar.md) |
| Local Backup & Restore | platform | [study](../features/platform/study/local-backup-restore--from-asyar.md) | [build](../features/platform/build/local-backup-restore--from-asyar.md) |

## Key design decisions

1. **Privacy by default**: secret redaction at capture time + encryption at rest, not just opt-in
2. **iframe sandboxing** for extensions: crashes are isolated, permissions are enforced at two layers (TS + Rust)
3. **Bundled bun/uv sidecars**: zero Node.js/Python dependency for MCP server users
4. **BYOK + local-first**: all AI calls go directly from device to provider; no cloud relay
5. **Silent commands**: hotkey-triggered background AI without modal UI disruption
