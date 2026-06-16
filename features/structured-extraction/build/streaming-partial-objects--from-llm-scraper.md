# Streaming Partial Objects (build spec) — distilled from llm-scraper

## Summary
The streaming variant of schema-driven extraction. Identical preprocessing and message assembly, but call the AI SDK's `streamText` with the schema as `output` and return its `partialOutputStream` (async iterable of schema-conformant partial objects). Caller consumes with `for await`.

## Core logic (inlined)

```typescript
// index.ts — the method
async stream<OUTPUT extends Output.Output = Output.Output<string, string>>(
  page: Page, output: OUTPUT, options?: ScraperRunOptions
) {
  const preprocessed = await preprocess(page, options)
  return streamAISDKCompletions<OUTPUT>(this.client, preprocessed, output, options)
}
```

```typescript
// models.ts — note: NOT async; returns the stream immediately
import { streamText, type LanguageModel, type Output, ModelMessage } from 'ai'

export function streamAISDKCompletions<OUTPUT extends Output.Output = Output.Output<string,string>>(
  model: LanguageModel, page: PreProcessResult, output: OUTPUT, options?: ScraperLLMOptions
) {
  const pageContent = prepareAISDKPage(page)   // same helper as non-streaming
  const { system = systemPrompt, messages: messagesOptions, ...rest } = options || {}
  const messages: ModelMessage[] = [
    { role: 'user', content: pageContent },
    ...(messagesOptions || []),
  ]

  const { partialOutputStream } = streamText({ model, output, system, messages, ...rest })

  return { stream: partialOutputStream, url: page.url }
}
```

Caller usage:
```typescript
const { stream } = await scraper.stream(page, Output.object({ schema }), { format: 'html' })
for await (const partial of stream) {
  render(partial)   // each partial conforms to schema, fields fill in over time
}
```

## Data contracts
- Inputs identical to [[schema-driven-extraction--from-llm-scraper]] (`page`, `output`, `options`).
- **Return**: `{ stream: AsyncIterable<DeepPartial<SchemaType>>, url: string }`. Each yielded value is the object-so-far; the final yield is the complete object.

## Dependencies & assumptions
- `ai` SDK with `streamText` returning `{ partialOutputStream }` when given an `output` schema. (Older AI SDK: use `streamObject({ schema })` and consume `partialObjectStream`.)
- Everything else identical to the non-streaming spec — same `preprocess`, same `prepareAISDKPage`, same `systemPrompt`.

## To port this, you need:
- [ ] The non-streaming extraction already ported (this is a ~5-line delta on top of it).
- [ ] An SDK whose structured-output call exposes a partial-object stream; otherwise emulate by streaming raw text and incrementally parsing with a tolerant JSON parser (harder — prefer an SDK that does it).
- [ ] A consumer (UI/CLI) that can re-render on each partial.

## Gotchas
- **`streamText` here is invoked synchronously** (the function isn't `await`ed internally for a value) — it returns the iterable right away. Don't `await` the stream itself; `await` the method, then iterate.
- **No exposed final/aggregated promise** in this implementation — the last partial *is* the result. If you need a clean awaited final object, capture it from the last iteration or add the SDK's final promise.
- **Errors surface mid-stream.** A provider error can throw during iteration, not at call time — wrap the `for await` in try/catch.
- Same version-drift caveat as the base spec: `streamText`+`partialOutputStream` (new) vs `streamObject`+`partialObjectStream` (old).

## Origin (reference only)
`mishushakov/llm-scraper` — `src/index.ts` (`LLMScraper.stream`), `src/models.ts` (`streamAISDKCompletions`).
