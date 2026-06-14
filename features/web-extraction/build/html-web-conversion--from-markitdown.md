# HTML / Web Conversion (build spec) — distilled from markitdown

## Summary

Generic HTML→Markdown converter using BeautifulSoup + a custom markdownify subclass. Strips scripts/styles, extracts body, handles recursion-depth fallback to plaintext. Provides a `convert_string(html)` helper for in-process HTML strings. Specialized sub-converters (Wikipedia, RSS, Bing SERP) inherit from or delegate to this converter.

## Core logic (inlined)

```python
from bs4 import BeautifulSoup
from markdownify import MarkdownConverter

class _CustomMarkdownify(MarkdownConverter):
    """Override markdownify for edge cases — nested tables, special links, etc."""

    def convert_a(self, el, text, convert_as_inline):
        # Keep links unless they're empty or just '#'
        href = el.get("href", "")
        if not href or href == "#":
            return text
        return super().convert_a(el, text, convert_as_inline)

    def convert_table(self, el, text, convert_as_inline):
        # markdownify's default table handling is fragile for nested tables
        # — override to flatten nested tables to plain text if needed
        try:
            return super().convert_table(el, text, convert_as_inline)
        except Exception:
            return el.get_text()


class HtmlConverter(DocumentConverter):
    def accepts(self, stream, stream_info, **kwargs):
        mime = stream_info.mimetype or ""
        ext = (stream_info.extension or "").lower()
        return mime.startswith(("text/html", "application/xhtml")) or ext in (".html", ".htm")

    def convert(self, stream, stream_info, **kwargs):
        charset = stream_info.charset or "utf-8"
        html_bytes = stream.read()
        try:
            html = html_bytes.decode(charset, errors="replace")
        except LookupError:
            html = html_bytes.decode("utf-8", errors="replace")
        return DocumentConverterResult(text_content=self._html_to_md(html, **kwargs))

    def convert_string(self, html: str, **kwargs) -> str:
        """Convert an HTML string directly — used by other converters for table formatting."""
        return self._html_to_md(html, **kwargs)

    def _html_to_md(self, html: str, strict: bool = False, **kwargs) -> str:
        soup = BeautifulSoup(html, "html.parser")

        # Strip noise
        for tag in soup.find_all(["script", "style"]):
            tag.decompose()

        # Extract body content
        body = soup.find("body") or soup

        try:
            return _CustomMarkdownify().convert_soup(body)
        except RecursionError:
            if strict:
                raise
            # Fallback: plain text extraction for deeply-nested HTML
            return body.get_text(separator="\n")
```

```python
# Wikipedia specialization
class WikipediaConverter(HtmlConverter):
    def accepts(self, stream, stream_info, **kwargs):
        url = stream_info.url or ""
        return "wikipedia.org/wiki/" in url and super().accepts(stream, stream_info, **kwargs)

    def convert(self, stream, stream_info, **kwargs):
        html = stream.read().decode(stream_info.charset or "utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find(id="mw-content-text")
        if not content:
            return super().convert(stream, stream_info, **kwargs)
        # Strip TOC, edit links, navigation boxes
        for el in content.find_all(class_=["toc", "mw-editsection", "navbox"]):
            el.decompose()
        return DocumentConverterResult(
            text_content=_CustomMarkdownify().convert_soup(content)
        )
```

## Data contracts

- **Input**: HTML bytes or string; charset from `stream_info.charset` (default UTF-8)
- **Output**: Markdown string; links preserved; tables as `| col | col |\n|---|---|\n| val |`
- **`convert_string(html)`**: returns str directly — used internally by DOCX/PPTX/XLSX converters for table rendering

## Dependencies & assumptions

```
beautifulsoup4 >= 4.12
markdownify >= 0.12
```

## To port this, you need:

- [ ] `HtmlConverter` with `accepts()` on MIME/extension, `convert()` decode+parse+transform
- [ ] `_CustomMarkdownify(MarkdownConverter)` subclass — override `convert_a` and `convert_table` at minimum
- [ ] `convert_string(html: str) -> str` public method for in-process HTML (used by table formatters)
- [ ] Strip `<script>` and `<style>` tags before markdownify
- [ ] `RecursionError` fallback → `body.get_text(separator="\n")`
- [ ] `WikipediaConverter` subclass: URL-detect + extract `#mw-content-text` + strip `.toc`, `.mw-editsection`, `.navbox`

## Gotchas

- `markdownify` has known issues with deeply-nested tables and some link types. The `_CustomMarkdownify` subclass is where you fix these — expect to need at least 2-3 overrides for production use.
- The `RecursionError` fallback fires silently (no warning). If you need to debug conversion quality, log when it fires.
- `convert_string()` is a critical integration point — don't rename it. It's called by name from DOCX, PPTX, and XLSX converters.
- charset detection (from [[magika-file-detection--from-markitdown]]) feeds `stream_info.charset` — don't hardcode UTF-8 for `stream.read().decode()`, always use the hint.

## Origin

https://github.com/microsoft/markitdown — `converters/_html_converter.py`, `converters/_markdownify.py`, `converters/_wikipedia_converter.py`, `converters/_rss_converter.py`, `converters/_bing_serp_converter.py`
