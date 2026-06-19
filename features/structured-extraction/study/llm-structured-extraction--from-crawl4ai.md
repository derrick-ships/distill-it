# LLM-Based Structured Extraction — from [crawl4ai](https://github.com/unclecode/crawl4ai)

> Domain: [[_domain]] · Source: https://github.com/unclecode/crawl4ai · NotebookLM:

## What it does

`LLMExtractionStrategy` uses a language model to extract typed, structured data from web page content. You supply a Pydantic schema (or a free-form instruction), crawl4ai chunks the page into LLM-sized pieces, sends each to the model with your schema/instruction, parses the responses, and returns a list of schema-conformant objects as JSON. Supports any provider (OpenAI, Anthropic, local) via LiteLLM.

## Why it exists

Web pages have irregular, unstructured content that rule-based extractors miss. Product prices might be buried in text; news article authors might be in different DOM locations on every page. LLMs can understand arbitrary content structure and map it to a schema even when the HTML doesn't follow predictable patterns. This strategy is the escape hatch for everything CSS/XPath can't handle.

## How it actually works

**Schema modes:** There are two extraction types. `"schema"` mode provides a Pydantic model to the LLM as a JSON schema constraint — the LLM is instructed to emit JSON matching that schema. `"block"` mode skips the schema and uses a free-form instruction, returning raw text blocks. Schema mode is the primary use case.

**Chunking:** Before any LLM call, the page content is split into manageable chunks. The strategy calls `merge_chunks(sections, chunk_token_threshold, overlap)` which combines page sections (paragraphs, articles, etc.) up to the token budget per chunk, with configurable overlap between adjacent chunks. Default chunk size is 4096 tokens; default overlap is 10% of the chunk size.

**LLM calls:** Each chunk is sent to the model with a system prompt (describing the extraction task and schema) and the chunk as user content. The LLM's response is expected to contain XML-wrapped JSON blocks: `<block>{"field": "value"}</block>`. The strategy accumulates token usage across all chunks.

**Provider flexibility via LiteLLM:** The `LLMConfig` provider string follows LiteLLM conventions — `"openai/gpt-4o"`, `"anthropic/claude-haiku-4-5-20251001"`, `"ollama/llama3"`, `"groq/llama3-8b-8192"`. All route through the same interface.

**Parallel vs sequential processing:** By default, chunks are processed in parallel via `ThreadPoolExecutor` (4 workers). Groq is an exception — Groq enforces strict rate limits, so chunks are processed sequentially with 500ms delays between calls.

**Schema generation from examples:** If you have example HTML but no schema yet, `agenerate_schema(html, query)` uses an LLM to infer a schema from the page structure. With `validate=True`, the generated schema is tested against the HTML and refined up to `max_refinements` times based on actual extraction results.

## The non-obvious parts

**The LLM response format must be XML-tagged.** The extraction logic expects `<block>JSON</block>` in the response. If the model emits raw JSON without the wrapper, extraction fails silently (empty result). For reliable results, the prompt explicitly instructs the model to use this format.

**Token usage accumulates across chunks and is queryable.** After extraction, `strategy.show_usage()` prints a per-chunk and total token report. Essential for cost tracking on large pages.

**Overlap prevents boundary blindness.** If a key data point falls at the chunk boundary, it appears (partially) in both chunks. The overlap parameter ensures that context around the boundary is preserved in at least one chunk's full view.

**`input_format` selects the input type.** The strategy can take `"markdown"` (the cleaned markdown, default), `"html"` (the cleaned HTML), or `"fit_markdown"` (the noise-filtered markdown). Use `"fit_markdown"` when content filtering has already run to reduce token consumption.

## Related
- [[css-xpath-schema-extraction--from-crawl4ai]] (faster, cheaper alternative for predictable page structures)
- [[content-filtering-strategies--from-crawl4ai]] (run first to reduce tokens sent to LLM)
- [[chunking-strategies--from-crawl4ai]] (chunking is applied before sending to LLM)
- [[llm-extract-map-reduce--from-firecrawl]] (similar pattern but at the multi-page scale)
