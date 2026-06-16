# Provider-Agnostic LLM Layer (build spec) — distilled from llm-scraper

## Summary
Achieve multi-provider LLM support (OpenAI/Anthropic/Google/Groq/Ollama) with zero per-provider code by depending on the Vercel AI SDK's `LanguageModel` abstraction instead of any vendor client. Accept a `LanguageModel` in the constructor; pass it unchanged to `generateText`/`streamText`. Provider selection happens entirely in caller code.

## Core logic (inlined)

```typescript
import { type LanguageModel } from 'ai'

export default class LLMScraper {
  // The ONLY provider-aware line in the whole library: a typed handle.
  constructor(private client: LanguageModel) { this.client = client }

  // every method forwards this.client to the SDK, never touching a provider directly:
  //   generateText({ model: this.client, ... })
  //   streamText({ model: this.client, ... })
}
```

Caller chooses the provider by constructing the model object (outside the library):

```typescript
import { openai } from '@ai-sdk/openai'
import { anthropic } from '@ai-sdk/anthropic'
import { ollama } from 'ollama-ai-provider'   // local, private

const scraper = new LLMScraper(openai('gpt-4o'))               // or
const scraper = new LLMScraper(anthropic('claude-sonnet-...'))  // or
const scraper = new LLMScraper(ollama('llama3'))               // fully local
```

That's the entire mechanism. There is no provider switch, no adapter map, no `if (provider === 'openai')`. The AI SDK normalizes auth, transport, JSON-mode/structured-output, and streaming per provider.

## Data contracts
- **Constructor input**: one `LanguageModel` (AI SDK type). Opaque to the scraper.
- No provider-specific config, env handling, or response shaping lives in this library — it's all in the AI SDK + the provider package the caller imports.

## Dependencies & assumptions
- `ai` (Vercel AI SDK) — supplies the `LanguageModel` type and the unified `generateText`/`streamText`.
- One provider package per provider the caller wants: `@ai-sdk/openai`, `@ai-sdk/anthropic`, `@ai-sdk/google`, `@ai-sdk/groq`, an Ollama provider, etc. API keys are handled by those packages (usually env vars), not by this library.

## To port this, you need:
- [ ] An LLM SDK that exposes a single model interface across providers (AI SDK; or LiteLLM/LangChain equivalents in other ecosystems).
- [ ] To type your entry point against that interface, not a concrete client.
- [ ] To push provider/model/key selection up to the caller (constructor arg or config), never hardcoded inside.

## Gotchas
- **Capability is not uniform even behind a uniform type.** Vision (`image` format) needs a vision-capable model; structured output quality varies; some local models are weak at JSON. The *interface* is portable; the *results* aren't guaranteed. Validate per model.
- **Don't leak provider specifics inward.** The moment you add `if (model is OpenAI)` you've lost the abstraction. Keep all vendor logic in the model-construction site.
- **Auth/keys are the provider package's job** — if you port to a stack without that convention, you must add env/key handling yourself.
- **The "feature" is an architecture decision, not code to copy** — the takeaway is *choose the abstraction one level above the vendor*. Copying the constructor is trivial; internalizing that principle is the value.

## Origin (reference only)
`mishushakov/llm-scraper` — `src/index.ts` (`LLMScraper` constructor, `LanguageModel` typing), `src/models.ts` (all three functions forward `model` to the AI SDK).
