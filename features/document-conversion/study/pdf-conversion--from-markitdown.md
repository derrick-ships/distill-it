# PDF Conversion — from [markitdown](https://github.com/microsoft/markitdown)

> Domain: [[_domain]] · Source: https://github.com/microsoft/markitdown · NotebookLM:

## What it does

Converts PDF files into Markdown, preserving table structure and body text. The output is a clean Markdown string with tables rendered as Markdown tables and prose as paragraphs. It handles both text-layer PDFs and form-like structured layouts.

## Why it exists

PDFs are the single most common document format in professional contexts, but they're notorious for being hard to extract text from correctly. Layout information is stored as absolute positions, not semantic structure. MarkItDown's PDF converter exists to bridge the gap: give LLMs readable, structured Markdown instead of a scrambled flat text dump.

## How it actually works

The converter uses two libraries in a layered strategy:

**Primary path (pdfplumber):** For each page, the converter first tries to detect "form-like" structure by analyzing word positions. It groups words into columns by their horizontal position (x-coordinate) and checks whether multiple columns exist side by side. If so, it extracts content as a structured table. For plain prose pages, it falls back to pdfplumber's built-in text extraction.

To keep memory usage constant on large PDFs, it calls `page.close()` after processing each page — this frees pdfplumber's cached page objects rather than holding the entire document in RAM.

**Fallback path (pdfminer):** If pdfplumber fails entirely (corrupt file, unusual encoding), the converter falls back to pdfminer's `extract_text()`, which is slower but more robust for plain prose. pdfminer doesn't do table detection; it produces a flat text dump.

**Table formatting:** Detected tables become Markdown tables with pipe separators and header separator rows. The converter also handles "partial numbering" — cases like ".1" or ".2" at the start of a line (common in structured specs) get merged with the following text line.

## The non-obvious parts

- pdfplumber and pdfminer serve genuinely different use cases: pdfplumber is better for structured/tabular PDFs, pdfminer is better for prose. Using both is the right call.
- There's no OCR here — if the PDF is a scanned image with no text layer, this converter produces nothing useful. For that, see [[azure-doc-intelligence--from-markitdown]].
- Memory management is deliberate: `page.close()` is not optional cleanup — it's load-bearing for large PDFs.

## Related

- [[converter-pipeline--from-markitdown]] — how the pipeline dispatches to this converter
- [[azure-doc-intelligence--from-markitdown]] — handles scanned PDFs that need OCR
