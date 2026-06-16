# llm-scraper

- **Source:** https://github.com/mishushakov/llm-scraper
- **Product:** TypeScript library that extracts structured, type-safe data from any webpage using LLMs. Give it a Playwright page + a Zod/JSON schema; it preprocesses the page and returns a typed object matching the schema.
- **Stack:** TypeScript · Playwright · Vercel AI SDK 6 · Zod · Turndown · Mozilla Readability
- **Providers:** OpenAI, Anthropic, Google, Groq, Ollama (via the AI SDK)
- **Date distilled:** 2026-06-15

## Architecture in one breath
One `LLMScraper` class wraps a single AI SDK `LanguageModel`. Three methods — `run` (extract), `stream` (extract progressively), `generate` (write a reusable scraper) — each do `preprocess(page) → AI SDK call`. Preprocessing reduces the page to one of six formats; the default `html` runs an in-browser cleanup scrub first. The whole library is ~4 small source files.

## Features distilled

| Feature | Domain | Study | Build |
|---|---|---|---|
| Schema-Driven Extraction (`run`) | structured-extraction | [study](../features/structured-extraction/study/schema-driven-extraction--from-llm-scraper.md) | [build](../features/structured-extraction/build/schema-driven-extraction--from-llm-scraper.md) |
| Streaming Partial Objects (`stream`) | structured-extraction | [study](../features/structured-extraction/study/streaming-partial-objects--from-llm-scraper.md) | [build](../features/structured-extraction/build/streaming-partial-objects--from-llm-scraper.md) |
| Page Format Pipeline (`preprocess`) | content-preprocessing | [study](../features/content-preprocessing/study/page-format-pipeline--from-llm-scraper.md) | [build](../features/content-preprocessing/build/page-format-pipeline--from-llm-scraper.md) |
| HTML Cleanup (`cleanup`) | content-preprocessing | [study](../features/content-preprocessing/study/html-cleanup--from-llm-scraper.md) | [build](../features/content-preprocessing/build/html-cleanup--from-llm-scraper.md) |
| Scraper Code Generation (`generate`) | code-generation | [study](../features/code-generation/study/scraper-code-generation--from-llm-scraper.md) | [build](../features/code-generation/build/scraper-code-generation--from-llm-scraper.md) |
| Provider-Agnostic LLM Layer | ai-integration | [study](../features/ai-integration/study/provider-agnostic-llm--from-llm-scraper.md) | [build](../features/ai-integration/build/provider-agnostic-llm--from-llm-scraper.md) |

## Source files (reference only — repo may be gone later)
- `src/index.ts` — `LLMScraper` class, `run`/`stream`/`generate`, option types.
- `src/preprocess.ts` — `preprocess`, the six formats, `PreProcessResult`.
- `src/cleanup.ts` — in-browser DOM scrub (tag + attribute strip lists).
- `src/models.ts` — `generateAISDKCompletions`, `streamAISDKCompletions`, `generateAISDKCode`, prompts, `stripMarkdownBackticks`.
