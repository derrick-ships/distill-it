# Domain: document-conversion

Converting structured documents (PDFs, Office files, archives, plaintext) into clean Markdown for downstream text analysis or LLM consumption.

## What this domain is about

Document conversion is the problem of turning binary or richly-formatted files into a plain, portable text format that preserves semantic structure (headings, tables, lists) without the noise of layout metadata. The goal isn't pixel-perfect fidelity — it's producing Markdown that a language model can reason about efficiently.

## Pattern shared across features in this domain

Every converter follows the same interface:
- `accepts(stream, stream_info)` → bool
- `convert(stream, stream_info, **kwargs)` → `DocumentConverterResult`

The result always has a `text_content` field (Markdown string). Converters are priority-sorted and tried in order; the first one that `accepts` and succeeds wins.

## Features in this domain

- [[converter-pipeline--from-markitdown]] — the core dispatch engine
- [[pdf-conversion--from-markitdown]] — pdfplumber/pdfminer dual-path PDF extraction
- [[office-doc-conversion--from-markitdown]] — DOCX, PPTX, XLSX → Markdown
- [[zip-archive-traversal--from-markitdown]] — recursive ZIP unpacking and conversion
