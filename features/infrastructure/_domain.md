# Domain: infrastructure

Core plumbing: local-first data storage, desktop app integration, AI provider routing, and credential management. Covers SQLite persistence, Electron IPC, HTTP/SSE daemon architecture, and bring-your-own-key proxy patterns.

## Features in this domain

- [[byok-proxy--from-open-design]] — provider-agnostic streaming gateway supporting Anthropic, OpenAI, Azure, Google, Ollama, SenseAudio with SSRF protection
- [[local-first-architecture--from-open-design]] — SQLite + Electron + HTTP daemon, all compute on-device, with IPC, PTY terminals, MCP OAuth, and S3-optional project storage
