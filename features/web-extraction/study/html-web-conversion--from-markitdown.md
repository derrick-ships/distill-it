# HTML / Web Conversion — from [markitdown](https://github.com/microsoft/markitdown)

> Domain: [[_domain]] · Source: https://github.com/microsoft/markitdown · NotebookLM:

## What it does

Converts HTML — whether from a local file, a fetched URL, or a raw HTML string — into clean Markdown. The generic path uses BeautifulSoup + a customized markdownify transform. Specialized sub-converters override the generic path for Wikipedia articles, RSS feeds, and Bing search result pages.

## Why it exists

HTML is the lingua franca of web content. Nearly everything that can be fetched from a URL is HTML. A good HTML→Markdown converter is a prerequisite for treating the entire web as an input source. The specializations (Wikipedia, RSS, Bing) exist because those platforms have consistent enough structure to produce much better output than a generic scrape.

## How it actually works

**Generic path:**
1. The `HtmlConverter.convert()` method accepts files with MIME type `text/html` or `application/xhtml`, or extensions `.html`/`.htm`.
2. The HTML bytes are parsed with BeautifulSoup using the specified charset (defaulting to UTF-8).
3. `<script>` and `<style>` tags are stripped.
4. The `<body>` element is extracted (if present).
5. The resulting DOM is passed to `_CustomMarkdownify`, a subclass of the `markdownify` library's converter, which walks the tree and emits Markdown.
6. A fallback handles deeply-nested HTML that would overflow Python's recursion limit: if recursion fails, it extracts plain text instead of Markdown.

**`convert_string()` convenience method:** Accepts a raw HTML string and runs the same pipeline — useful when other converters (DOCX, PPTX) produce intermediate HTML for table formatting.

**Wikipedia specialization:** The WikipediaConverter detects Wikipedia URLs, fetches the page, extracts the `#mw-content-text` div (the article body), and strips navigation boxes and edit links. The result is much cleaner than running the full page through generic markdownify.

**RSS/Atom specialization:** The RssConverter parses XML-structured feeds, iterates items, and formats each as a Markdown section with title, link, date, and description.

**Bing SERP specialization:** The BingSerpConverter detects Bing search result pages, extracts the organic result blocks, and formats them as a structured Markdown list of results with titles, URLs, and snippets.

## The non-obvious parts

- The `_CustomMarkdownify` subclass exists because the base `markdownify` library doesn't handle all edge cases well (e.g., nested tables, certain link types). The override methods fix specific known issues.
- The recursion limit fallback is silent — there's no warning when it fires. Deep HTML nesting just produces plain text output instead of structured Markdown.
- `convert_string()` is a key integration point: both DocxConverter and PptxConverter call it to convert intermediate HTML tables to Markdown. It's not just for web use.

## Related

- [[youtube-extraction--from-markitdown]] — overrides this path for YouTube URLs
- [[office-doc-conversion--from-markitdown]] — calls `convert_string()` for table formatting
- [[converter-pipeline--from-markitdown]] — dispatches to this converter
