# Multi-Provider LLM System (build spec) — distilled from bolt.diy

## Summary

Build a singleton `LLMManager` that auto-discovers provider classes from a registry, manages static and dynamic model lists, handles caching, and exposes a unified `getModelInstance(providerName, modelName, apiKey)` interface backed by the Vercel AI SDK. API keys travel in cookies, not server storage.

## Core logic (inlined)

```typescript
// Provider interface (minimal shape)
abstract class BaseProvider {
  abstract name: string;
  abstract staticModels: ModelInfo[];
  abstract getModelInstance(options: { model: string; serverEnv: Env; apiKeys: Record<string,string>; providerSettings: Record<string,ProviderSetting>; }): LanguageModelV1;
  getDynamicModels?(apiKeys: Record<string,string>, settings: ProviderSetting, serverEnv: Env): Promise<ModelInfo[]>;
}

// LLMManager singleton
class LLMManager {
  private static _instance: LLMManager;
  private _providers = new Map<string, BaseProvider>();
  private _modelCache = new Map<string, ModelInfo[]>();

  static getInstance(env?: Env) {
    if (!LLMManager._instance) LLMManager._instance = new LLMManager(env);
    return LLMManager._instance;
  }

  private constructor(env?: Env) {
    // Scan PROVIDER_LIST (imported from providers/index.ts), instantiate each
    for (const ProviderClass of PROVIDER_LIST) {
      try {
        const p = new ProviderClass(env);
        this._providers.set(p.name, p);
      } catch { console.warn(`Failed to init provider ${ProviderClass.name}`); }
    }
  }

  async updateModelList(apiKeys, settings, env) {
    const allModels: ModelInfo[] = [];
    for (const [, provider] of this._providers) {
      if (!settings[provider.name]?.enabled) continue;
      const staticIds = new Set(provider.staticModels.map(m => m.name));
      let dynamic: ModelInfo[] = [];
      if (provider.getDynamicModels) {
        const cached = this._modelCache.get(provider.name);
        dynamic = cached ?? await provider.getDynamicModels(apiKeys, settings[provider.name], env);
        this._modelCache.set(provider.name, dynamic);
      }
      // Dedupe: static wins over dynamic for same model name
      const deduped = dynamic.filter(m => !staticIds.has(m.name));
      allModels.push(...provider.staticModels, ...deduped);
    }
    return allModels;
  }

  getProvider(name: string) { return this._providers.get(name); }
}

// streamText bridge
async function streamText({ messages, model, provider, apiKeys, providerSettings, env, ...rest }) {
  const manager = LLMManager.getInstance(env);
  const providerInst = manager.getProvider(provider);
  if (!providerInst) throw new Error(`Unknown provider: ${provider}`);
  const modelInst = providerInst.getModelInstance({ model, serverEnv: env, apiKeys, providerSettings });
  return _streamText({ model: modelInst, messages, ...rest });
}
```

## Data contracts

```typescript
interface ModelInfo {
  name: string;           // model ID as provider expects it
  label: string;          // human display name
  provider: string;       // matches BaseProvider.name
  maxTokenAllowed: number;
}

interface ProviderSetting {
  enabled: boolean;
  baseUrl?: string;       // for self-hosted providers (Ollama, LM Studio)
}

// API keys in cookies (JSON-parsed per request):
// cookie name: "apiKeys" → JSON: { "Anthropic": "sk-ant-...", "OpenAI": "sk-..." }
// cookie name: "providers" → JSON: { "Anthropic": { enabled: true }, ... }
```

## Dependencies & assumptions

- `ai` (Vercel AI SDK) — `@ai-sdk/anthropic`, `@ai-sdk/openai`, etc. — one package per provider
- Runs server-side only (Remix action, Cloudflare Worker)
- Cookies parsed from request headers using `cookie` package
- `PROVIDER_LIST` is a static import of all `BaseProvider` subclasses from `app/lib/modules/llm/providers/`

## To port this, you need:
- [ ] Create `BaseProvider` abstract class with `name`, `staticModels`, `getModelInstance()`, optional `getDynamicModels()`
- [ ] Create one provider file per LLM service, extending `BaseProvider`
- [ ] Create `providers/index.ts` exporting `PROVIDER_LIST = [AnthropicProvider, OpenAIProvider, ...]`
- [ ] Create `LLMManager` singleton that registers all providers on first access
- [ ] Add `apiKeys` and `providers` JSON cookies in your request parsing middleware
- [ ] Wire `streamText` to extract provider/model from request body and call `LLMManager`

## Gotchas

- **Cloudflare Workers**: env bindings aren't available at module init time — accept `env` as a constructor argument and store it on the manager instance.
- **Cookie encryption**: bolt.diy stores keys in plaintext cookies. For production, encrypt at rest.
- **Dynamic model caching**: per-process cache, not per-request. On serverless cold starts, cache is empty and one API call fires per provider. Add a TTL or Redis layer for high-traffic deployments.
- **Token limits**: providers differ in how they express context limits. Build a per-model cap table and apply it before calling the SDK or you'll get cryptic 400 errors.
- **Reasoning models (o1/o3)**: the `maxTokens` param is `max_completion_tokens` for these — Vercel AI SDK handles it, but you must know which model names trigger the alternate path.

## Origin (reference only)

- Repo: https://github.com/stackblitz-labs/bolt.diy
- `app/lib/modules/llm/manager.ts` — LLMManager singleton
- `app/lib/modules/llm/providers/` — all provider implementations
- `app/lib/.server/llm/stream-text.ts` — streamText bridge
- `app/routes/api.chat.ts` — where apiKeys are read from cookies and passed through
