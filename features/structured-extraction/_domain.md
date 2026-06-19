# Domain: structured-extraction

Turning unstructured content (a webpage, a document, a blob of text) into **typed, schema-validated data** using an LLM as the extraction engine. The defining move is: caller supplies a schema (Zod / JSON Schema), the LLM is constrained to emit data matching it, and the result is parsed back into a typed object — not freeform prose.

This is distinct from [[content-synthesis]] (which clusters/summarizes) and from [[research-automation]] (which gathers sources). Here the input is already in hand; the job is *shape enforcement* on the output.

## Features studied
- [[schema-driven-extraction--from-llm-scraper]] — the core `run()` loop: Playwright page → preprocess → AI SDK structured output → typed object.
- [[streaming-partial-objects--from-llm-scraper]] — `stream()`: progressive partial objects as the model generates, via AI SDK `partialOutputStream`.
- [[map-reduce-answer-generation--from-scrapegraph-ai]] — when the content is bigger than the context window: answer the question per-chunk in parallel, then merge into one schema-shaped result. A contrasting approach to llm-scraper's single SDK call — chunk-and-merge with hand-written JSON instructions instead of one structured-output call.
- [[llm-extract-map-reduce--from-firecrawl]] — prompt+schema+URLs → one structured object via an async map-reduce: classify single-answer vs multi-entity, split the schema, chunk docs ×50 and batch-extract concurrently, then null-aware merge + dedup + rerank. The multi-page, production scale-up of the single-page 'prompt → JSON' extractors.

- [[llm-structured-extraction--from-crawl4ai]] — LiteLLM-backed extraction with Pydantic schema constraints; chunks page content, sends to model, parses XML-tagged JSON blocks; supports any OpenAI-compatible provider; includes token usage tracking and schema auto-generation.
- [[css-xpath-schema-extraction--from-crawl4ai]] — deterministic CSS/XPath extraction via JsonCssExtractionStrategy (BeautifulSoup4) and JsonLxmlExtractionStrategy (lxml with selector caching and multi-strategy fallback); field types include text, attribute, regex, nested, list, computed.
- [[chunking-strategies--from-crawl4ai]] — seven text-splitting strategies (Identity, Regex, NLP Sentence, Topic Segmentation, Fixed Word, Sliding Window, Overlapping Window) for preparing page content for LLM extraction or RAG vector ingestion.

## Cross-domain links
- Depends on [[content-preprocessing]] — the page must be reduced to an LLM-friendly format first.
- Pairs with [[ai-integration]] — the model is provider-agnostic behind one interface.
- Upstream: [[web-scraping]] — crawl4ai's scraping pipeline feeds content into these extraction strategies.
