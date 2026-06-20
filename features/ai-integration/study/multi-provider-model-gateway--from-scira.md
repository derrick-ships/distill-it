# Multi-Provider Model Gateway — from [scira](https://github.com/zaidmukaddam/scira)

> Domain: [[_domain]] · Source: https://github.com/zaidmukaddam/scira · NotebookLM: <link once added>

## What it does

Scira lets users pick from ~130 different language models — across 22 providers (OpenAI, Anthropic,
Google, xAI, Groq, Mistral, DeepSeek, Moonshot, Cohere, ByteDance, MiniMax, and more) — from a single
dropdown. Behind that dropdown, every model is referenced by one tidy internal name like
`scira-grok-4` or `scira-ext-5`, and the rest of the app never needs to know which company actually
serves it or how to authenticate to them.

## Why it exists

If you want to offer "any model," you can't litter your codebase with provider-specific SDK calls and
API-key handling everywhere a model is used. You need one indirection layer: an internal model
*alias* that the whole app speaks, and a single place that maps each alias to the real provider call,
the right API key, fallbacks, and any special middleware. That indirection is what lets Scira add a
new model by editing one file, gate models by subscription tier, and silently fail over from one
provider to another.

## How it actually works

There are two pieces, kept deliberately separate:

**1. The registry (`ai/models.ts`) — client-safe metadata.** A plain array of `Model` objects, one
per alias. Each entry carries not just `value` (the `scira-*` id) and `label`, but a full set of
capability and access flags: `vision`, `reasoning`, `pdf`, `experimental`, `category` (Free/Pro),
`pro`, `max`, `requiresAuth`, `freeUnlimited`, `maxOutputTokens`, `extreme` (usable in deep research),
`fast`, plus optional inference `parameters` (temperature, topP, penalties) and the `provider` id.
This file is safe to ship to the browser — it has no secrets, just descriptions. A pile of helper
functions read it: `requiresProSubscription(value)`, `hasVisionSupport(value)`, `supportsExtremeMode`,
`getFilteredModels`, `canUseModel`, etc. The UI uses these to show/hide and lock models.

**2. The provider (`ai/providers.ts`) — the actual wiring, server-only.** A single Vercel AI SDK
`customProvider` named `scira` whose `languageModels` map turns each `scira-*` alias into a real model
instance. The app only ever calls `scira.languageModel('scira-whatever')`; the map decides what that
means. The mappings come in a few flavors:
- **Direct:** `'scira-grok-4': xai('grok-4')` — straight passthrough to a provider SDK.
- **Retryable with fallback:** `createRetryable({ model: openai('gpt-4.1'), retries: [openai_2('gpt-4.1')] })`
  — primary call, and if it fails, retry on a second OpenAI key or via the Vercel AI Gateway.
- **Reasoning middleware:** wrap a model so `<think>…</think>` blocks are extracted as separate
  reasoning output (used for Qwen "thinking" models).
- **Gateway routing:** `gateway('moonshotai/kimi-k2.5')` — no local SDK instance at all; the Vercel AI
  Gateway brokers the call.
- **Custom OpenAI-compatible endpoints:** ByteDance ARK, Sarvam, Z.ai, HuggingFace Inference, Novita,
  MiniMax, Cloudflare Workers AI, OpenRouter — each instantiated with its own base URL + key.

At request time, the search route reads the `model` string from the POST body, checks it against the
registry's gate functions (`requiresAuthentication`/`requiresProSubscription`/`requiresMaxSubscription`)
to reject under-privileged users, then hands `scira.languageModel(model)` to `streamText`. One
exception: "multi-agent" mode bypasses the whole gateway and calls xAI's Grok agent directly.

## The non-obvious parts

- **Two files, two jobs.** Metadata (`models.ts`, browser-safe) is split from wiring (`providers.ts`,
  secrets inside). The UI never touches the provider; the server never re-derives capabilities.
- **The alias is the contract.** Everything downstream speaks `scira-*`. Swapping which real model
  backs an alias is a one-line change with zero blast radius.
- **Fallback is built into the alias.** A single alias can mean "GPT-4.1 on key A, else key B, else
  gateway" — resilience is encoded at the registry level, not in calling code.
- **Dual API keys as cheap load-balancing.** `openai` + `openai_2` (separate keys) are used as
  primary/retry pairs — not a real load balancer, just sequential retry via `ai-retry`.
- **Subscription tiering rides on metadata flags.** `pro`/`max`/`requiresAuth`/`freeUnlimited` live on
  each model object, so access control is data, not scattered conditionals.

## Related
- [[tool-and-search-mode-registry--from-scira]] (the parallel registry pattern, for tools/modes)
- [[multi-provider-llm--from-bolt-diy]] (another multi-provider abstraction — good contrast)
- [[provider-agnostic-model-layer--from-scrapegraph-ai]] (swappable-engine pattern)
- [[provider-agnostic-llm--from-llm-scraper]] (single swappable LLM as the engine)
