# Multi-Provider Model Gateway (build spec) — distilled from scira

## Summary

One internal alias (`scira-*`) per model; the whole app speaks aliases, and a single
`customProvider` maps each alias to a real provider call (direct, retryable-with-fallback,
gateway-brokered, or custom OpenAI-compatible endpoint). Capability + access metadata lives in a
separate **client-safe** registry array so the UI can filter/lock models without touching secrets.
Built on the Vercel AI SDK (`ai` + `@ai-sdk/*` + `@ai-sdk/gateway`), but the alias-indirection
pattern ports to any LLM stack.

## Core logic (inlined)

**Registry — `ai/models.ts` (browser-safe metadata):**

```ts
export interface Model {
  value: string;            // 'scira-grok-4' — the alias spoken everywhere
  label: string; description: string;
  vision: boolean; reasoning: boolean; experimental: boolean;
  category: 'Free' | 'Pro';
  pdf: boolean; pro: boolean; max?: boolean;
  requiresAuth: boolean; freeUnlimited: boolean;
  maxOutputTokens: number;
  extreme?: boolean; fast?: boolean; isNew?: boolean;
  parameters?: { temperature?: number; topP?: number; topK?: number; minP?: number;
                 frequencyPenalty?: number; presencePenalty?: number; maxOutputTokens?: number };
  provider?: ModelProvider; // one of 22 provider ids
}
type ModelProvider = 'scira'|'xai'|'openai'|'anthropic'|'google'|'alibaba'|'mistral'|'deepseek'
  |'zhipu'|'cohere'|'moonshot'|'minimax'|'bytedance'|'arcee'|'vercel'|'amazon'|'xiaomi'
  |'kwaipilot'|'stepfun'|'sarvam'|'inception'|'nvidia';

export const models: Model[] = [ /* ~130 entries */ ];

// gate/capability helpers read the array:
export const requiresAuthentication = (v) => models.find(m=>m.value===v)?.requiresAuth ?? false;
export const requiresProSubscription = (v) => models.find(m=>m.value===v)?.pro ?? false;
export const requiresMaxSubscription = (v) => models.find(m=>m.value===v)?.max ?? false;
export const hasVisionSupport = (v) => !!models.find(m=>m.value===v)?.vision;
export const supportsExtremeMode = (v) => !!models.find(m=>m.value===v)?.extreme;
// ...isFreeUnlimited, hasPdfSupport, hasReasoningSupport, getFilteredModels, getModelsByProvider,
//    getActiveProviders, shouldBypassRateLimits, canUseModel, isModelRestrictedInRegion
```

**Provider — `ai/providers.ts` (server-only wiring):**

```ts
import { customProvider, wrapLanguageModel, extractReasoningMiddleware } from 'ai';
import { gateway } from '@ai-sdk/gateway';
// provider SDK instances: xai, openai, openai_2 (2nd key), anthropic, google, groq, huggingface, ...
const middleware = extractReasoningMiddleware({ tagName: 'think' });

export const scira = customProvider({
  languageModels: {
    // direct passthrough
    'scira-grok-4':     xai('grok-4'),
    'scira-anthropic':  anthropic('claude-sonnet-4-5'),
    'scira-google':     google('gemini-flash-latest'),
    // retryable: primary + fallback(s)
    'scira-gpt-4.1':    createRetryable({ model: openai('gpt-4.1'), retries: [openai_2('gpt-4.1')] }),
    'scira-google-pro': createRetryable({ model: google('gemini-2.5-pro'),
                                          retries: [gateway('google/gemini-2.5-pro')] }),
    // reasoning middleware (extract <think> blocks)
    'scira-qwen-32b-thinking': wrapLanguageModel({ model: groq('qwen/qwen3-32b'), middleware }),
    // gateway-brokered (no local SDK instance)
    'scira-ext-5':      gateway('moonshotai/kimi-k2.5'),
    'scira-deepseek-chat': gateway('deepseek/deepseek-v3.2'),
    // custom OpenAI-compatible endpoints: ark (ByteDance), sarvam, zai, huggingface, novita,
    //   minimax, workersai (Cloudflare), openrouter — each new OpenAI({ baseURL, apiKey })
  },
});
```

**Selection at request time (`app/api/search/route.ts`):**

```ts
const { model } = body;                       // a scira-* alias from the client
if (requiresAuthentication(model) && !user)        return new ChatSDKError('unauthorized');
if (requiresProSubscription(model) && !isProUser)  return new ChatSDKError('forbidden:pro');
if (requiresMaxSubscription(model) && !isMaxUser)  return new ChatSDKError('forbidden:max');
// normal path:
streamText({ model: scira.languageModel(model), /* ... */ });
// exception: group==='multi-agent' && isPro -> xai.responses('grok-4.20-multi-agent') (bypasses scira)
```

## Data contracts

- The alias string (`scira-*`) is the cross-app contract; nothing downstream references raw provider
  model ids.
- `Model` (above) is the registry record. Access gates are pure functions of `value`.

## Dependencies & assumptions

- Vercel AI SDK: `ai` (`customProvider`, `wrapLanguageModel`, `extractReasoningMiddleware`),
  `@ai-sdk/gateway`, and per-provider `@ai-sdk/*` packages. A retry helper (`ai-retry` →
  `createRetryable`). Custom endpoints use OpenAI-compatible clients with `{ baseURL, apiKey }`.
- Env: one API key per provider (plus `OPENAI_API_KEY_2` for the dual-key retry trick), and a gateway
  credential for `@ai-sdk/gateway`.

## To port this, you need:
- [ ] A single provider/registry indirection: one alias map the whole app calls.
- [ ] A **client-safe** metadata array (no secrets) the UI reads for capability/lock flags.
- [ ] Server-only provider wiring that resolves alias → real call.
- [ ] Pure gate functions (`requiresPro`, `requiresAuth`, …) keyed by alias, checked before each call.
- [ ] (Optional) a retry/fallback wrapper so one alias can fail over across keys/providers.
- [ ] (Optional) reasoning-extraction middleware for `<think>`-style models.

## Gotchas

- **Never import the provider wiring into client code** — it carries API keys. Keep `models.ts`
  (metadata) and `providers.ts` (secrets) strictly separated; the split is the whole safety story.
- **Gate before you call.** Subscription/auth checks must run against the registry *before*
  `languageModel(alias)`, or users can invoke models they shouldn't by POSTing the alias directly.
- **Bypass paths break the abstraction.** Scira's `multi-agent` mode sidesteps the gateway entirely;
  if you add such a path, replicate the gate checks there too or you create a privilege hole.
- **Dual-key "load balancing" is just sequential retry**, not balancing — don't expect even traffic
  splitting from it.
- **Capability flags are data, not behavior.** A model flagged `vision:true` still needs the call site
  to actually pass images; the flag only advertises support.

## Origin (reference only)

- Repo: https://github.com/zaidmukaddam/scira
- `ai/models.ts` (registry + helper gates), `ai/providers.ts` (the `scira` customProvider wiring),
  `app/api/search/route.ts` (gate checks + `scira.languageModel(model)` selection, multi-agent bypass).
