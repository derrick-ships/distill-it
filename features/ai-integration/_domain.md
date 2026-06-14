# Domain: ai-integration

Using AI services (cloud OCR, LLM vision, speech recognition) as enhancement layers inside a document conversion pipeline.

## What this domain is about

Some documents are only legible to AI: scanned PDFs with no text layer, handwritten forms, complex images. This domain covers how to call external AI services (Azure Document Intelligence, OpenAI-compatible vision APIs) from inside a converter, thread credentials through the pipeline, and produce structured output (Markdown, YAML front matter) from AI results.

## Key design principle

AI integration is always additive, never blocking. Converters in this domain either accept explicit credentials (Azure endpoint/key) or are registered alongside non-AI fallbacks at lower priority. If the AI path fails, the caller can fall through to a dumber-but-always-available converter.

## Features in this domain

- [[azure-doc-intelligence--from-markitdown]] — Azure prebuilt-layout OCR for PDFs, images, and Office files
