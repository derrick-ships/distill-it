# PDF Conversion (build spec) — distilled from markitdown

## Summary

A dual-library PDF converter: pdfplumber as the primary path (with table/form structure detection), pdfminer as fallback. Processes pages sequentially with explicit `page.close()` for constant memory use. Outputs Markdown with tables as pipe-delimited tables.

## Core logic (inlined)

```python
class PdfConverter(DocumentConverter):
    def accepts(self, stream, stream_info, **kwargs):
        return (
            stream_info.mimetype in ("application/pdf", "application/x-pdf")
            or (stream_info.extension or "").lower() == ".pdf"
        )

    def convert(self, stream, stream_info, **kwargs):
        result_parts = []
        try:
            with pdfplumber.open(stream) as pdf:
                for page in pdf.pages:
                    page_text = self._convert_page(page)
                    if page_text:
                        result_parts.append(page_text)
                    page.close()  # IMPORTANT: free cached objects, keep memory constant
        except Exception:
            # Full fallback: pdfminer for the whole document
            stream.seek(0)
            result_parts = [extract_text(stream)]  # from pdfminer.high_level

        return DocumentConverterResult(text_content="\n\n".join(result_parts))

    def _convert_page(self, page) -> str:
        # Try form/table detection first
        words = page.extract_words()
        if self._is_tabular(words):
            return self._extract_as_table(words)
        else:
            return page.extract_text() or ""

    def _is_tabular(self, words) -> bool:
        # Group words by their x0 position into columns
        # If multiple distinct x0 clusters exist, treat as tabular
        x_positions = sorted(set(round(w["x0"] / 10) * 10 for w in words))
        return len(x_positions) >= 2

    def _extract_as_table(self, words) -> str:
        # Sort words by (y_top, x0), group into rows by y_top proximity
        # Then group row-words into columns by x0 cluster
        # Render as Markdown table: header | separator | rows
        rows = self._group_words_into_rows(words)
        if not rows:
            return ""
        header = rows[0]
        separator = ["-" * max(len(c), 3) for c in header]
        lines = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(separator) + " |",
        ]
        for row in rows[1:]:
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)
```

## Data contracts

- **Input**: binary stream of a PDF file, `StreamInfo` with mimetype or extension
- **Output**: `DocumentConverterResult.text_content` — Markdown string
  - Tables: `| col1 | col2 |\n| --- | --- |\n| val | val |`
  - Prose: paragraph text with double-newline page breaks

## Dependencies & assumptions

```toml
# pyproject.toml optional deps
pdfplumber = ">=0.11"     # primary: layout-aware extraction
pdfminer-six = ">=20221105"  # fallback: robust prose extraction
```

- Both must be installed. If only pdfminer is available, skip pdfplumber path entirely.
- No OCR: zero text yield for scanned-only PDFs. Pair with [[azure-doc-intelligence--from-markitdown]] for those.

## To port this, you need:

- [ ] `pdfplumber` and `pdfminer-six` installed
- [ ] `DocumentConverter` base class (from [[converter-pipeline--from-markitdown]])
- [ ] `_is_tabular(words)` — column-clustering heuristic on word x-coordinates
- [ ] `_extract_as_table(words)` — row/column grouping + Markdown table render
- [ ] `page.close()` after each page — mandatory for memory safety on large PDFs
- [ ] Full-document pdfminer fallback wrapped in try/except around pdfplumber

## Gotchas

- `page.close()` is not cleanup — it's correctness. Without it, memory grows linearly with page count.
- pdfplumber's `extract_words()` returns dicts with `x0`, `top`, `text` keys. Clustering on `x0` is how you detect columns.
- pdfminer produces better prose but cannot detect tables. Don't use it as primary.
- "Partial numbering" lines like `.1`, `.2` (common in specifications) should be merged with the following line to avoid formatting noise.

## Origin

https://github.com/microsoft/markitdown — `packages/markitdown/src/markitdown/converters/_pdf_converter.py`
