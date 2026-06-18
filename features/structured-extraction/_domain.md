# Domain: structured-extraction

Turning unstructured content (a webpage, a document, a blob of text) into **typed, schema-validated data** using an LLM as the extraction engine. The defining move is: caller supplies a schema (Zod / JSON Schema), the LLM is constrained to emit data matching it, and the result is parsed back into a typed object — not freeform prose.

This is distinct from [[content-synthesis]] (which clusters/summarizes) and from [[research-automation]] (which gathers sources). Here the input is already in hand; the job is *shape enforcement* on the output.

## Features studied
- [[schema-driven-extraction--from-llm-scraper]] — the core `run()` loop: Playwright page → preprocess → AI SDK structured output → typed object.
- [[streaming-partial-objects--from-llm-scraper]] — `stream()`: progressive partial objects as the model generates, via AI SDK `partialOutputStream`.
- [[map-reduce-answer-generation--from-scrapegraph-ai]] — when the content is bigger than the context window: answer the question per-chunk in parallel, then merge into one schema-shaped result. A contrasting approach to llm-scraper's single SDK call — chunk-and-merge with hand-written JSON instructions instead of one structured-output call.

## Cross-domain links
- Depends on [[content-preprocessing]] — the page must be reduced to an LLM-friendly format first.
- Pairs with [[ai-integration]] — the model is provider-agnostic behind one interface.
