# Domain: ai-integration

Wiring external AI services (cloud OCR, LLM vision, speech recognition, provider-agnostic LLM SDKs) into a product — as enhancement layers in a pipeline, or as the swappable engine a whole tool is built on.

## What this domain is about

Some documents are only legible to AI: scanned PDFs with no text layer, handwritten forms, complex images. This domain covers how to call external AI services (Azure Document Intelligence, OpenAI-compatible vision APIs) from inside a converter, thread credentials through the pipeline, and produce structured output (Markdown, YAML front matter) from AI results.

## Key design principle

AI integration is always additive, never blocking. Converters in this domain either accept explicit credentials (Azure endpoint/key) or are registered alongside non-AI fallbacks at lower priority. If the AI path fails, the caller can fall through to a dumber-but-always-available converter.

## Features in this domain

- [[azure-doc-intelligence--from-markitdown]] — Azure prebuilt-layout OCR for PDFs, images, and Office files
- [[provider-agnostic-llm--from-llm-scraper]] — multi-provider LLM support (OpenAI/Anthropic/Google/Groq/Ollama) for free by depending on the Vercel AI SDK abstraction instead of any vendor client. A contrasting choice to the Azure node: abstract *above* the vendor rather than bind *to* one.
- [[submit-and-poll-generation-client--from-open-generative-ai]] — the universal async-job primitive for wrapping a generation gateway: POST → `request_id` → poll `/predictions/{id}/result` every 2s until a terminal status, then normalize output to one `url`. One function backs image/video/i2v/lipsync/audio.
- [[centralized-model-registry--from-open-generative-ai]] — config-over-code for 200+ models: one declarative record per model (id, endpoint, parameter schema) drives both API routing and self-building UI forms. Adding a model is a data edit.
