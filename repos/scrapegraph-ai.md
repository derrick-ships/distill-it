# scrapegraph-ai

- **Source:** https://github.com/ScrapeGraphAI/Scrapegraph-ai
- **Product:** Python library for LLM-powered web scraping. You give it a natural-language prompt + a source (URL, local file, or just a question) and it returns structured data — no CSS selectors or XPath. Scraping logic is expressed as graphs of nodes that pass a shared state.
- **Stack:** Python · LangChain (`init_chat_model`, runnables, parsers) · Playwright/Chromium · Pydantic · semchunk · BeautifulSoup · pandas · optional BrowserBase / Scrape.do / Serper
- **Providers:** ~19 via a model-string registry — OpenAI, Azure OpenAI, Anthropic, Google (GenAI/Vertex), Groq, Bedrock, Mistral, Ollama (local), DeepSeek, Fireworks, TogetherAI, XAI, MiniMax, Nvidia, HuggingFace, Ernie, OneApi, CLoD
- **Date distilled:** 2026-06-18

## Architecture in one breath
Everything is a **graph of nodes over a shared mutable state dict**. A ~100-line `BaseGraph` walks nodes from an entry point, each node reading the state keys it declares (via a boolean input-key DSL) and writing its results back. The flagship `SmartScraperGraph` is just three nodes — Fetch → Parse → GenerateAnswer — reshaped by feature flags into 8 variants via a lookup table. Fetch normalizes any source (URL through Chromium/requests/BrowserBase/Scrape.do, or local files) into clean Markdown `Document`s; Parse chunks to the model's token budget; GenerateAnswer map-reduces (parallel per-chunk LLM calls + a merge call) into a schema-shaped result. The model is provider-agnostic: a `<provider>/<model>` string is parsed and built via LangChain's factory, and the model's token limit drives chunking. Higher-level graphs (e.g. `SearchGraph`) compose by running SmartScraper inside a node.

## Features distilled

| Feature | Domain | Study | Build |
|---|---|---|---|
| Graph Execution Engine (BaseGraph + BaseNode + input-key DSL) | pipeline-orchestration | [study](../features/pipeline-orchestration/study/graph-execution-engine--from-scrapegraph-ai.md) | [build](../features/pipeline-orchestration/build/graph-execution-engine--from-scrapegraph-ai.md) |
| SmartScraper Pipeline (Fetch→Parse→Generate, 8-variant matrix, retry loop) | web-extraction | [study](../features/web-extraction/study/smart-scraper-pipeline--from-scrapegraph-ai.md) | [build](../features/web-extraction/build/smart-scraper-pipeline--from-scrapegraph-ai.md) |
| Multi-Source Fetch Node (4 web backends + local files → Documents) | web-extraction | [study](../features/web-extraction/study/multi-source-fetch-node--from-scrapegraph-ai.md) | [build](../features/web-extraction/build/multi-source-fetch-node--from-scrapegraph-ai.md) |
| Map-Reduce Answer Generation (parallel chunks + merge, Pydantic output) | structured-extraction | [study](../features/structured-extraction/study/map-reduce-answer-generation--from-scrapegraph-ai.md) | [build](../features/structured-extraction/build/map-reduce-answer-generation--from-scrapegraph-ai.md) |
| Provider-Agnostic Model Layer (`_create_llm`, token registry, rate limit) | ai-integration | [study](../features/ai-integration/study/provider-agnostic-model-layer--from-scrapegraph-ai.md) | [build](../features/ai-integration/build/provider-agnostic-model-layer--from-scrapegraph-ai.md) |
| Search-Driven Scraping (query-gen → search → iterate-scrape → merge) | research-automation | [study](../features/research-automation/study/search-driven-scraping--from-scrapegraph-ai.md) | [build](../features/research-automation/build/search-driven-scraping--from-scrapegraph-ai.md) |

## Source files (reference only — repo may be gone later)
- `scrapegraphai/graphs/base_graph.py` — `BaseGraph` engine (traversal, conditional edges, token/cost accounting).
- `scrapegraphai/nodes/base_node.py` — `BaseNode` contract + `_parse_input_keys` boolean DSL.
- `scrapegraphai/graphs/abstract_graph.py` — base class: `_create_llm`, `set_common_params`, `model_token`.
- `scrapegraphai/graphs/smart_scraper_graph.py` — flagship pipeline + 8-entry variation matrix.
- `scrapegraphai/graphs/search_graph.py` — search→iterate→merge pipeline.
- `scrapegraphai/nodes/fetch_node.py` — multi-source ingestion + 4 web backends.
- `scrapegraphai/nodes/parse_node.py` + `utils/split_text_into_chunks.py` — token-sized chunking (semchunk).
- `scrapegraphai/nodes/generate_answer_node.py` + `prompts/generate_answer_node_prompts.py` — map-reduce + templates.
- `scrapegraphai/nodes/search_internet_node.py`, `graph_iterator_node.py`, `merge_answers_node.py` — search pipeline nodes.
- `scrapegraphai/helpers/models_tokens.py` — provider→model→max-tokens table.
