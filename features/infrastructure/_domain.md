# Domain: infrastructure

Core plumbing: local-first data storage, desktop app integration, AI provider routing, and credential management. Covers SQLite persistence, Electron IPC, HTTP/SSE daemon architecture, and bring-your-own-key proxy patterns.

## Features in this domain

- [[byok-proxy--from-open-design]] — provider-agnostic streaming gateway supporting Anthropic, OpenAI, Azure, Google, Ollama, SenseAudio with SSRF protection
- [[local-first-architecture--from-open-design]] — SQLite + Electron + HTTP daemon, all compute on-device, with IPC, PTY terminals, MCP OAuth, and S3-optional project storage
- [[byok-rate-limited-action--from-carousel-generator]] — Next.js server action fronting an AI call with three gates (server key present → optional per-IP Upstash sliding-window rate limit → forward), with a parallel client BYOK key hook; zero-database, opt-in-by-env throttling
- [[modular-permission-packaging--from-permissionskit]] — hub-and-spoke Swift packaging: 15+ per-permission SPM products/CocoaPods subspecs over one core, each gated by a `-D` compile flag, so consumers compile in only what they use and never reference sensitive Apple APIs they don't need (App Review surface reduction)
- [[async-to-sync-status-bridging--from-permissionskit]] — DispatchSemaphore (and static-anchor delegate) pattern that exposes a synchronous `status` getter over Apple's callback/delegate-only authorization APIs; the deadlock-safe async→sync bridge
- [[dispatcher-concurrency-control--from-crawl4ai]] — MemoryAdaptiveDispatcher (RAM-aware priority queue with fairness timeout and pressure throttling) and SemaphoreDispatcher (fixed-count asyncio semaphore), both with domain-level rate limiting; governs parallel URL crawling in crawl4ai's arun_many()
