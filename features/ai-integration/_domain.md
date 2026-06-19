# Domain: ai-integration

Wiring external AI services (cloud OCR, LLM vision, speech recognition, provider-agnostic LLM SDKs) into a product — as enhancement layers in a pipeline, or as the swappable engine a whole tool is built on.

## What this domain is about

Some documents are only legible to AI: scanned PDFs with no text layer, handwritten forms, complex images. This domain covers how to call external AI services (Azure Document Intelligence, OpenAI-compatible vision APIs) from inside a converter, thread credentials through the pipeline, and produce structured output (Markdown, YAML front matter) from AI results.

## Key design principle

AI integration is always additive, never blocking. Converters in this domain either accept explicit credentials (Azure endpoint/key) or are registered alongside non-AI fallbacks at lower priority. If the AI path fails, the caller can fall through to a dumber-but-always-available converter.

## Features in this domain

- [[azure-doc-intelligence--from-markitdown]] — Azure prebuilt-layout OCR for PDFs, images, and Office files
- [[provider-agnostic-llm--from-llm-scraper]] — multi-provider LLM support (OpenAI/Anthropic/Google/Groq/Ollama) for free by depending on the Vercel AI SDK abstraction instead of any vendor client. A contrasting choice to the Azure node: abstract *above* the vendor rather than bind *to* one.
- [[ai-lead-classification--from-auto-crm]] — optional Claude (Sonnet) lead grader returning strict JSON {temperature, confidence, nextAction, reasoning}; null-client-as-feature-flag, regex JSON extraction, and a *total silent fallback* to a deterministic rule-based scorer. The opposite stance from llm-scraper: bind directly to one vendor, but make the whole AI path optional and degradable.
- [[provider-agnostic-model-layer--from-scrapegraph-ai]] — a `<provider>/<model>` string → the right client across ~19 providers via a registry + LangChain factory, plus a token-limit table that drives pipeline chunking. A third point on the abstraction spectrum: llm-scraper abstracts *above* the vendor (one SDK), auto-crm *binds to* one — this *enumerates* them all with per-provider escape hatches.
- [[streaming-claude-screen-context--from-clicky]] — a real-time *multimodal* Claude loop: base64 screenshot + transcribed question → Claude (`claude-sonnet-4-6`, `stream:true`) through a Cloudflare Worker proxy, parsing SSE `text_delta` events into cumulative text for progressive UI. Adds two hard-won gotchas: media-type sniffing (PNG vs JPEG magic bytes) and a TLS warm-up so large image uploads don't hit `-1200` SSL errors. The vision/streaming counterpoint to the text-only nodes above.
- [[citation-grounded-chat--from-openpaper]] — a RAG chat that answers *only* from pre-extracted evidence and forces inline `@cite[n]` attribution, then parses the markers back into source-anchored footnotes. Where the nodes above wire a vendor in, this one wires the *grounding discipline* in: the model never sees the raw doc, only an evidence block, so hallucinated citations are near-impossible. Includes a no-embeddings word-overlap re-anchor for compacted summaries.
- [[ai-agent-tool-calling--from-asyar]] — full multi-provider AI agent (OpenAI, Anthropic, Google Gemini, Ollama, OpenRouter) with a 3-tier tool registry (builtin/extension/MCP), streaming responses via Tauri events, agentic loop with tool-call rounds, and a provider-abstraction layer that normalizes all vendor APIs to one `chat(messages, tools, options)` interface.
