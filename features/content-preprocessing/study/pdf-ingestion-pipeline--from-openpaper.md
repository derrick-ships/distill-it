# PDF Ingestion Pipeline — from [openpaper](https://github.com/khoj-ai/openpaper)

> Domain: [[_domain]] · Source: https://github.com/khoj-ai/openpaper · NotebookLM: <link once added>

## What it does

You drop a PDF (or paste a URL to one) and a few seconds later the paper shows up in your library with
a title, authors, abstract, keywords, a short summary, a set of auto-pulled highlights, and a preview
thumbnail — without blocking your browser. All the heavy lifting happens in the background while you
keep working; the UI just polls until it's ready.

## Why it exists

Everything else in Open Paper — chat, search, audio overviews — needs the paper turned into clean text
plus structured metadata first. Doing that inline on upload would freeze the request for 10–30 seconds
per paper and fall over on big files. So ingestion is split off into a dedicated background service
that can be scaled, retried, and rate-limited independently of the web app.

## How it actually works

Upload is a **two-phase, webhook-driven** dance across two services (the web `server` and a separate
`jobs` worker).

1. **Accept fast.** The upload endpoint validates the file (≤30 MB, ≤800 pages, not encrypted, has
   extractable text on page 1), checks your subscription quota, writes a *placeholder* `Paper` row plus
   a `PaperUploadJob` row marked `PENDING`, and returns a `job_id` immediately (HTTP 202). The actual
   work is kicked off as a background task.

2. **Stage to S3 + enqueue.** The file bytes go to S3 (returning a public Cloudflare CDN URL). A
   Celery task `upload_and_process_file` is dispatched onto the `pdf_processing` queue, handed the S3
   key and a **webhook URL** that points back at the server with the job id.

3. **Process in the worker.** The Celery worker downloads the PDF from S3 and runs the parse stages:
   - **Text extraction** — MarkItDown first, falling back to pymupdf4llm, producing clean markdown.
   - **Page offset map** — `{page_num: {start, end}}` character offsets into that text (this is what
     lets a citation or highlight map back to a page later).
   - **Validation** — under 1,000 chars means it's probably a scanned image (reject); too large to fit
     the LLM context (reject).
   - **Preview** — render page 0 at 2× zoom to a PNG, resize to ≤800px wide, upload to S3.
   - **LLM metadata** — fire four Gemini structured-output calls *in parallel* to pull
     (title/authors/abstract), (institutions/keywords), (summary + citations), and (verbatim
     highlights typed by category). Above 5,000 chars it creates a Gemini context cache so all four
     calls share one cached copy of the paper instead of re-sending it.

4. **Report via webhook.** When done, the worker POSTs the result back to the server's webhook, which
   enriches the placeholder `Paper` row with all the extracted fields and flips the `PaperUploadJob` to
   `COMPLETED` (or `FAILED`).

5. **Client polls.** The browser hits a status endpoint that reads the job row, and — while still
   running — also asks the jobs service for the live Celery progress message ("Downloading PDF from
   S3", "Processing PDF file", …). When the paper's abstract is non-null, the client knows it's done.

A **Zotero-import fast path** exists: pass `skip_metadata_extraction=true` and the worker only does
text + offsets + preview, no LLM calls — deterministic and cheap, because Zotero already supplies the
metadata.

## The non-obvious parts

- **Placeholder-then-enrich.** The `Paper` row is created *before* processing so `paper.id` exists for
  polling instantly; metadata fields are NULL until the webhook fills them. "Is it done?" =
  "is `abstract` non-null?".
- **Two-service split with a webhook callback**, not a shared DB write from the worker. The worker
  computes; the server owns all DB writes. Cleaner blast radius.
- **Four parallel LLM calls + a shared context cache.** Only one subtask (title/authors/abstract) is a
  hard-fail; the other three degrade to empty defaults so a flaky call doesn't lose the whole paper.
- **MarkItDown → pymupdf4llm fallback.** Two extractors so a PDF that defeats one still gets parsed.
- **Worker hardening.** One task at a time per worker, ack-late, re-queue on crash, recycle the worker
  after 1,000 tasks or 500 MB. PDF parsing is memory-hungry and leaky; these settings contain it.
- **No embeddings/chunking at ingest.** The full markdown is stored as one `raw_text` column. Search is
  keyword-based, not vector — a deliberate simplicity choice (see the search feature).
- **A custom event-loop shim** runs the async processing inside the synchronous Celery worker without
  "event loop is closed" errors.

## Related
- [[citation-grounded-chat--from-openpaper]] (consumes `raw_text` + `page_offsets` to ground answers)
- [[corpus-and-academic-search--from-openpaper]] (searches the `raw_content` this produces)
- [[audio-overview-tts--from-openpaper]] (narrates the summary this extracts)
- [[pdf-highlights-annotations--from-openpaper]] (page offsets anchor marks back to pages)
- See also: [[document-conversion]] domain — markitdown is the same converter, used here as a library.
