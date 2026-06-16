# Schema-Driven Extraction (build spec) — distilled from llm-scraper

## Summary
Build a one-method API: given a Playwright `Page` and an output schema (Zod or JSON Schema), preprocess the page to LLM-friendly content, send it to an LLM under a structured-output constraint derived from the schema, and return `{ data, url }` where `data` is typed to the schema. The schema is simultaneously the TS type and the runtime output constraint.

## Core logic (inlined)

The entire orchestration is tiny. A class holds one `LanguageModel` client; `run()` chains preprocess → structured completion.

```typescript
// index.ts — public surface
import { type Page } from 'playwright'
import { type LanguageModel, type Output, type CallSettings, ModelMessage } from 'ai'
import { preprocess, PreProcessOptions } from './preprocess.js'
import { generateAISDKCompletions } from './models.js'

export type ScraperLLMOptions = CallSettings & {
  system?: string
  messages?: ModelMessage[]
}
type ScraperRunOptions = ScraperLLMOptions & PreProcessOptions

export default class LLMScraper {
  constructor(private client: LanguageModel) { this.client = client }

  async run<OUTPUT extends Output.Output = Output.Output<string, string>>(
    page: Page, output: OUTPUT, options?: ScraperRunOptions
  ) {
    const preprocessed = await preprocess(page, options)
    return generateAISDKCompletions<OUTPUT>(this.client, preprocessed, output, options)
  }
}
```

```typescript
// models.ts — the actual LLM call
import { generateText, type LanguageModel, type UserContent, type Output, ModelMessage } from 'ai'

const systemPrompt = 'You are a sophisticated web scraper. Extract the contents of the webpage'

function prepareAISDKPage(page: PreProcessResult): UserContent {
  if (page.format === 'image') {
    return [{ type: 'image', image: page.content }]   // base64 screenshot
  }
  return [{ type: 'text', text: page.content }]
}

export async function generateAISDKCompletions<OUTPUT extends Output.Output = Output.Output<string,string>>(
  model: LanguageModel, page: PreProcessResult, output: OUTPUT, options?: ScraperLLMOptions
) {
  const pageContent = prepareAISDKPage(page)
  const { system = systemPrompt, messages: messagesOptions, ...rest } = options || {}
  const messages: ModelMessage[] = [
    { role: 'user', content: pageContent },
    ...(messagesOptions || []),
  ]
  const result = await generateText({ model, output, system, messages, ...rest })
  return { data: result.output, url: page.url }
}
```

Key mechanic: the schema is passed as the AI SDK `output` argument to `generateText`, and the structured result is read from `result.output`. The SDK converts a Zod schema to JSON Schema and enforces the constraint provider-appropriately. The caller's generic `OUTPUT` flows through so `data` is typed.

## Data contracts
- **Input `page`**: a Playwright `Page` already navigated to the target URL.
- **Input `output`**: an AI SDK `Output.Output` — in practice built from a Zod object, e.g. `Output.object({ schema })`. README example schema:
  ```typescript
  const schema = z.object({
    top: z.array(z.object({
      title: z.string(), points: z.number(), by: z.string(), commentsURL: z.string(),
    })).length(5)
  })
  ```
- **`options`** (`ScraperRunOptions`): AI SDK `CallSettings` (temperature, maxTokens, etc.) + optional `system` override + optional extra `messages` + preprocessing `format` (see preprocess spec).
- **Return**: `{ data: <typed to schema>, url: string }`.

## Dependencies & assumptions
- `ai` (Vercel AI SDK, v6-era API with `generateText({ output })` + `result.output`). Swappable: any structured-output LLM call works; on older AI SDK use `generateObject({ schema })` and read `result.object`.
- `playwright` for the page. Swappable for Puppeteer if you adapt `preprocess`.
- `zod` for schema authoring (or raw JSON Schema).
- A configured `LanguageModel` instance from any provider (see [[provider-agnostic-llm--from-llm-scraper]]).

## To port this, you need:
- [ ] A browser-automation handle that can yield page content/screenshots.
- [ ] A preprocessing function (port [[page-format-pipeline--from-llm-scraper]]) returning `{ url, content, format }`.
- [ ] An LLM SDK that supports schema-constrained structured output, or a JSON-mode + manual schema validation fallback.
- [ ] A schema library whose schema can both type the result and be converted to JSON Schema for the model.

## Gotchas
- **AI SDK version drift is the #1 break.** This code uses `generateText` + `output` + `result.output` (newer). Many tutorials/older versions use `generateObject` + `schema` + `result.object`. Pick one and be consistent; mixing yields `undefined` data.
- **No validation-repair loop.** A schema-violating model response throws from the SDK; there is no retry. Add your own retry if you need robustness.
- **Image format needs a vision-capable model**, and content must be base64 (no data-URI prefix here — the SDK takes the raw base64 string in `{ type: 'image', image }`).
- **Token cost scales with page size** — always preprocess/clean before sending; raw HTML of a real site can blow your context window.
- **`length(5)` and other Zod refinements** are enforced by the SDK's schema, but a weak model may still under/over-deliver; constrain hard and verify.

## Origin (reference only)
`mishushakov/llm-scraper` — `src/index.ts` (`LLMScraper.run`), `src/models.ts` (`generateAISDKCompletions`, `prepareAISDKPage`, `systemPrompt`).
