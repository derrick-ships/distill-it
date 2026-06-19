# Multi-Provider LLM System — from [bolt.diy](https://github.com/stackblitz-labs/bolt.diy)

> Domain: [[_domain]] · Source: https://github.com/stackblitz-labs/bolt.diy · NotebookLM:

## What it does

Bolt.diy connects to 19+ AI providers — OpenAI, Anthropic, Google, Groq, Mistral, Cohere, DeepSeek, Amazon Bedrock, Ollama, and more — through a single unified interface. The user picks a provider and model from a dropdown; the rest of the app doesn't care which backend is running. API keys live in cookies and are injected per-request. Adding a new provider requires no changes outside of a single provider file.

## Why it exists

The original bolt.new was locked to Anthropic. The entire bolt.diy fork was created to break that lock-in. The core job-to-be-done is: "let me use my own API keys with my preferred LLM, not just whatever StackBlitz chose." This matters because AI costs vary wildly, some models are faster, others are cheaper, and developers have free tier credits scattered across providers. A provider-agnostic system captures all of that.

## How it actually works

Every provider implements a `BaseProvider` interface. At startup, an `LLMManager` singleton scans a provider registry file and instantiates every class that extends `BaseProvider`. These are stored in a Map by provider name.

Each provider declares which models it supports **statically** (listed at class definition time) and optionally **dynamically** (fetched live from the provider's own model listing API). Dynamic models are cached to avoid repeated API calls.

When the chat API receives a request, it extracts the chosen `model` and `provider` from the last user message, grabs the API key from cookies (keyed by provider name), and passes everything to the `streamText` utility. That utility finds the right provider instance from `LLMManager`, calls the provider's `getModelInstance()` method to get a Vercel AI SDK-compatible language model, then calls the underlying `streamText` from the Vercel AI SDK.

The Vercel AI SDK handles the actual network calls, streaming, and tool-calling differences between providers. Bolt wraps this with model-specific token limit logic — some providers cap differently, and reasoning models like o1 need different max-completion handling.

## The non-obvious parts

- **Model deduplication**: if a model appears in both the static list and the dynamic API response, the static version wins. This prevents duplicates in the UI.
- **Cookie-based key storage**: API keys are NOT stored server-side. They're encrypted in cookies per-request. This is how a multi-tenant hosted version can work without a backend key store.
- **Provider fallback**: if a requested model isn't found in the static list, the manager queries the provider's dynamic model API before giving up. If still not found, it logs a warning and defaults to the first available model.
- **Cloudflare-specific initialization**: the LLMManager can accept fresh environment bindings at construction time because Cloudflare Workers re-execute the module on each request.

## Related
- [[context-optimization--from-bolt-diy]] (context selection also routes through the LLM system)
- [[artifact-code-generation--from-bolt-diy]] (code generation is the consumer of this provider layer)
- [[provider-agnostic-llm--from-llm-scraper]] (similar multi-provider pattern in a different context)
