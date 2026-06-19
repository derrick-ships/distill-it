# dyad

**Source:** https://github.com/dyad-sh/dyad  
**Product:** Local, open-source AI app builder — the self-hosted alternative to Lovable/v0/Bolt  
**Stack:** Electron 40, React 19, TypeScript, Vite, Vercel AI SDK, Better-SQLite3, Drizzle ORM, xterm.js, node-pty, Dugite (git)  
**Date distilled:** 2026-06-19

## What it is

Dyad is a desktop app (Mac + Windows) that lets you build full-stack applications by chatting with an AI. It runs entirely locally — your code, your API keys, your files. No cloud proxy. It supports 7+ AI providers (OpenAI, Anthropic, Google, Bedrock, Azure, xAI, custom endpoints) and deploys to Vercel with one click.

## Distilled features

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| AI Chat Stream | codegen | [study](../features/codegen/study/ai-chat-stream--from-dyad.md) | [build](../features/codegen/build/ai-chat-stream--from-dyad.md) |
| MCP Integration | ai-integration | [study](../features/ai-integration/study/mcp-integration--from-dyad.md) | [build](../features/ai-integration/build/mcp-integration--from-dyad.md) |
| Code Explorer | codegen | [study](../features/codegen/study/code-explorer--from-dyad.md) | [build](../features/codegen/build/code-explorer--from-dyad.md) |
| Dependency Manager | dev-tooling | [study](../features/dev-tooling/study/dependency-manager--from-dyad.md) | [build](../features/dev-tooling/build/dependency-manager--from-dyad.md) |
| Cloud Deploy | deployment | [study](../features/deployment/study/cloud-deploy--from-dyad.md) | [build](../features/deployment/build/cloud-deploy--from-dyad.md) |
| BYOK Settings | credential-management | [study](../features/credential-management/study/byok-settings--from-dyad.md) | [build](../features/credential-management/build/byok-settings--from-dyad.md) |
| Multi-App Library | app-management | [study](../features/app-management/study/multi-app-library--from-dyad.md) | [build](../features/app-management/build/multi-app-library--from-dyad.md) |
| Image Generation | codegen | [study](../features/codegen/study/image-generation--from-dyad.md) | [build](../features/codegen/build/image-generation--from-dyad.md) |

## Architecture notes

- **Electron IPC** is the backbone: renderer ↔ main process via typed IPC contracts (`src/ipc/handlers/`). Every feature is a set of IPC handlers.
- **SQLite** (better-sqlite3 + Drizzle ORM) is the persistence layer. Apps, chats, messages, MCP servers, custom models — all local SQLite.
- **Vercel AI SDK** (`ai` package) provides the unified streaming interface across all providers. Provider packages (`@ai-sdk/openai`, etc.) are separate installs.
- **AI response tags** (`<dyad-write>`, `<dyad-search-replace>`, `<dyad-add-dependency>`) are the protocol between LLM and the app — the LLM signals actions via XML in its response text.
- **`src/pro/`** is gated under FSL-1.1 (not Apache 2.0) — subscription-gated features live there.

## Key gotchas

- `safeStorage` (OS keychain) is machine-specific — settings file can't be synced between machines.
- MCP tool listing has an 8s hard timeout to prevent hung servers from blocking the UI.
- Code explorer requires TypeScript in the **app's** `node_modules`, not globally.
- Image generation goes through Dyad's engine (`engine.dyad.sh`), not directly to OpenAI.
