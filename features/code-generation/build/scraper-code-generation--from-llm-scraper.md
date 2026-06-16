# Scraper Code Generation (build spec) — distilled from llm-scraper

## Summary
Ask the LLM to author a self-contained IIFE JavaScript scraper for a given page + schema, instead of extracting data directly. Uses plain `generateText` (not structured output); the schema is passed as context. Strip code-fence backticks from the response. Return `{ code, url }`. Run the code yourself (e.g. `page.evaluate`) for free repeat scrapes.

## Core logic (inlined)

```typescript
// index.ts — the method (codegen restricts format to html | raw_html)
export type ScraperGenerateOptions = Omit<ScraperLLMOptions, 'mode'> & {
  format?: 'html' | 'raw_html'
}

async generate<OUTPUT extends Output.Output = Output.Output<string, string>>(
  page: Page, output: OUTPUT, options?: ScraperGenerateOptions
) {
  const preprocessed = await preprocess(page, options)
  return generateAISDKCode(this.client, preprocessed, output, options)
}
```

```typescript
// models.ts
const systemCodePrompt =
  "Provide a scraping function in JavaScript that extracts and returns data according to a schema " +
  "from the current page. The function must be IIFE. No comments or imports. No console.log. " +
  "The code you generate will be executed straight away, you shouldn't output anything besides runnable code."

function stripMarkdownBackticks(text: string) {
  let trimmed = text.trim()
  trimmed = trimmed.replace(/^```(?:javascript)?\s*/i, '')
  trimmed = trimmed.replace(/\s*```$/i, '')
  return trimmed
}

export async function generateAISDKCode<OUTPUT extends Output.Output = Output.Output<string,string>>(
  model: LanguageModel, page: PreProcessResult, output: OUTPUT, options?: ScraperGenerateOptions
) {
  const responseFormat = await output.responseFormat

  // AI SDK already converted the Zod schema → JSON Schema; pull it out for the prompt
  const jsonSchema =
    responseFormat.type === 'json' && 'schema' in responseFormat
      ? (responseFormat as { schema: unknown }).schema
      : output

  const { system = systemCodePrompt, messages: messagesOptions, ...rest } = options || {}
  const messages = [
    {
      role: 'user' as const,
      content: `Website: ${page.url}
      Schema: ${JSON.stringify(jsonSchema)}
      Content: ${page.content}`,
    },
    ...(messagesOptions || []),
  ]

  const result = await generateText({ model, system, messages, ...rest })  // NOTE: no `output` — free text

  return { code: stripMarkdownBackticks(result.text), url: page.url }
}
```

## Data contracts
- **Input**: `page` (Playwright Page), `output` (AI SDK Output built from a Zod/JSON schema), `options` (`ScraperGenerateOptions`: AI SDK settings + `format` limited to `'html' | 'raw_html'`).
- **Prompt payload to model**: `Website: <url>` / `Schema: <JSON.stringify(jsonSchema)>` / `Content: <preprocessed html>`.
- **Return**: `{ code: string /* runnable IIFE JS */, url: string }`.
- **Generated code contract**: a single IIFE, no imports, no comments, no console.log, returns the schema-shaped value. Designed to be executed directly (e.g. `await page.evaluate(code)`).

## Dependencies & assumptions
- `ai` SDK `generateText` (text mode — NOT `output`/structured). `result.text` holds the code.
- The `output` object must expose `responseFormat` (a promise) with `{ type: 'json', schema }` so the JSON Schema can be extracted. (AI SDK Output objects do.) Falls back to passing `output` itself if not JSON.
- `preprocess` restricted to html/raw_html (model needs DOM, not prose/image).

## To port this, you need:
- [ ] A text-mode LLM call (no schema constraint) — the schema is context, the output is code.
- [ ] A way to get JSON Schema from your schema lib (zod-to-json-schema, or your SDK's conversion).
- [ ] A backtick/fence stripper on the response (models fence despite instructions).
- [ ] A sandboxed executor for the returned JS (`page.evaluate`, vm2, isolated-vm). **Treat generated code as untrusted.**

## Gotchas
- **Security: you are executing LLM-authored JavaScript.** Never run it in a privileged context unsandboxed. `page.evaluate` runs in the page, which is safer than Node eval but still arbitrary code — review or sandbox.
- **Generated scrapers are DOM-specific and brittle** — they bake selectors for the page they saw. That's the whole point (speed/cost), but they break on redesign, unlike the inference path.
- **Models fence code even when told not to** — keep `stripMarkdownBackticks`; the regex handles ```` ```javascript ```` and bare ```` ``` ````, case-insensitive, leading + trailing.
- **No schema enforcement on the *generated code's* output** — the model may write code that returns a near-but-wrong shape. Validate the code's runtime result against your schema after executing.
- **html/raw_html only** — passing text/image format gives the model no DOM to target. The type limits this, but if you bypass it, codegen quality collapses.

## Origin (reference only)
`mishushakov/llm-scraper` — `src/index.ts` (`LLMScraper.generate`, `ScraperGenerateOptions`), `src/models.ts` (`generateAISDKCode`, `systemCodePrompt`, `stripMarkdownBackticks`).
