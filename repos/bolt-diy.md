# bolt.diy

**Source**: https://github.com/stackblitz-labs/bolt.diy  
**Date distilled**: 2026-06-19  
**Product**: Open-source, provider-agnostic AI-powered in-browser full-stack development environment. Fork of bolt.new (StackBlitz) that removes vendor lock-in — lets you bring your own API keys for 19+ LLM providers, run Node.js apps in the browser via WebContainer, and deploy to Vercel/Netlify in one click.

**Stack**: TypeScript, React 18, Remix 2, Vite, WebContainer API, Vercel AI SDK, CodeMirror 6, xterm.js, isomorphic-git, TailwindCSS, Cloudflare Pages, Electron, IndexedDB

## Features distilled

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Multi-Provider LLM System | ai-integration | [study](../features/ai-integration/study/multi-provider-llm--from-bolt-diy.md) | [build](../features/ai-integration/build/multi-provider-llm--from-bolt-diy.md) |
| WebContainer Runtime | runtime | [study](../features/runtime/study/webcontainer-runtime--from-bolt-diy.md) | [build](../features/runtime/build/webcontainer-runtime--from-bolt-diy.md) |
| Artifact Code Generation | code-generation | [study](../features/code-generation/study/artifact-code-generation--from-bolt-diy.md) | [build](../features/code-generation/build/artifact-code-generation--from-bolt-diy.md) |
| Context Optimization | ai-integration | [study](../features/ai-integration/study/context-optimization--from-bolt-diy.md) | [build](../features/ai-integration/build/context-optimization--from-bolt-diy.md) |
| One-Click Deployment | deployment | [study](../features/deployment/study/one-click-deployment--from-bolt-diy.md) | [build](../features/deployment/build/one-click-deployment--from-bolt-diy.md) |
| Browser Git (isomorphic-git + CORS proxy) | git | [study](../features/git/study/browser-git--from-bolt-diy.md) | [build](../features/git/build/browser-git--from-bolt-diy.md) |
| MCP Tool Integration | agent-architecture | [study](../features/agent-architecture/study/mcp-tool-integration--from-bolt-diy.md) | [build](../features/agent-architecture/build/mcp-tool-integration--from-bolt-diy.md) |
| Chat Persistence (IndexedDB) | persistence | [study](../features/persistence/study/chat-persistence--from-bolt-diy.md) | [build](../features/persistence/build/chat-persistence--from-bolt-diy.md) |

## Product notes

**Business model**: fully open source (MIT), community-driven, no monetization. Funded by community enthusiasm and StackBlitz ecosystem visibility.

**Playbook**: bolt.diy wins by removing the single biggest friction of bolt.new — vendor lock-in. By supporting every major LLM provider, it appeals to developers who already have API credits with Anthropic/OpenAI/Google and don't want to pay another service. The desktop Electron app adds offline appeal. Community features (oTTomator Think Tank) build contributor loyalty.

**Cloneability**: moderate effort. WebContainer API is proprietary (but free for public projects). Everything else is OSS. The hardest part to rebuild is the streaming message parser + WebContainer integration — that's the core product. Estimated LLM-assisted rebuild of core: 3-5 days for a skilled developer. The 19-provider LLM system is boilerplate once you understand the pattern.

**Moat**: essentially none — this IS the open-source clone of bolt.new. The community size and momentum are the only durable advantages.
