# Domain: content-preprocessing

Reducing raw, messy source material into a clean, compact representation an LLM can read cheaply and accurately — *before* any extraction or reasoning happens. The work is format conversion and noise removal: strip what the model doesn't need, keep what carries meaning, choose the representation (text vs markdown vs image) that fits the task.

This is the upstream sibling of [[structured-extraction]]: preprocessing decides what the model *sees*, extraction decides what it *returns*. Better preprocessing = lower token cost, higher accuracy, fewer hallucinations.

## Features studied
- [[page-format-pipeline--from-llm-scraper]] — one function, six output formats (raw_html, markdown, text, cleaned html, image, custom) from a live Playwright page.
- [[html-cleanup--from-llm-scraper]] — the in-browser DOM scrub (drop ~30 tag types + noise attributes) that makes the `html` format cheap.
- [[pdf-ingestion-pipeline--from-openpaper]] — a two-service, webhook-driven background pipeline that turns an uploaded PDF into clean markdown + a page→char-offset map + LLM-extracted metadata. The heavier, production-grade cousin of the llm-scraper page formatters: Celery worker, markitdown→pymupdf fallback, 4 parallel Gemini calls behind a shared context cache, and worker hardening for leaky PDF libs.

## Cross-domain links
- Feeds [[structured-extraction]] and [[code-generation]].
- Compare [[html-web-conversion--from-markitdown]] — a server-side BeautifulSoup+markdownify take on the same HTML→clean-text problem.
