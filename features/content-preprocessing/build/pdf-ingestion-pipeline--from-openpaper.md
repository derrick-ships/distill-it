# PDF Ingestion Pipeline (build spec) — distilled from openpaper

## Summary

Two-service, webhook-driven background PDF ingestion. The web server validates + accepts the upload,
stages bytes to S3, and dispatches a Celery task to a separate `jobs` worker. The worker extracts
markdown text (MarkItDown → pymupdf4llm fallback), builds a page→char-offset map, renders a preview
image, and runs **4 parallel Gemini structured-output calls** (sharing a context cache) to extract
metadata/summary/highlights, then POSTs results to a server webhook that enriches a placeholder Paper
row. The client polls a status endpoint. A `skip_metadata_extraction` flag gives Zotero imports a
cheap LLM-free path.

## Core logic (inlined)

### Flow

```
POST /api/paper-upload/  (file)  | POST /api/paper-upload/from-url/  ({url})
  1. validate: size<=30MB, pages<=800, not encrypted, page-1 text extractable (pypdf)
  2. subscription-limit check (can_user_upload_paper)
  3. INSERT PaperUploadJob{status=PENDING}; return 202 {job_id}
  4. BackgroundTask:
       mark_as_running(job_id)
       s3_key, cdn_url = s3.upload_any_file_from_bytes(pdf_bytes)     # public Cloudflare URL
       INSERT Paper{upload_job_id, s3_object_key} (placeholder; metadata NULL)
       webhook = f"{WEBHOOK_BASE_URL}/api/webhooks/paper-processing/{job_id}"
       task = celery.send_task("upload_and_process_file",
                args=[s3_key, webhook], kwargs={"skip_metadata_extraction": bool},
                queue="pdf_processing")
       UPDATE PaperUploadJob.task_id = task.id

Celery worker (queue=pdf_processing):
  upload_and_process_file(s3_key, webhook, skip_metadata_extraction):
    pdf = s3.download_file_to_bytes(s3_key)
    result = run_async_safely(process_pdf_file(pdf, s3_key, ...))   # custom event-loop shim
    requests.post(webhook, json={"task_id":..., "status":"completed"|"failed",
                                 "result": result.model_dump(), "error": None})

process_pdf_file(pdf):
  text         = parser.extract_text(pdf)              # MarkItDown -> pymupdf4llm fallback; sanitize NULL bytes
  page_offsets = parser.map_pages_to_text_offsets(pdf) # {page_num:{start,end}} via pymupdf
  if len(text) < 1000:  raise InsufficientPDFTextError      # scanned/image-only
  if retained_fraction < 0.80: raise ExcessivePDFTextError  # too big for LLM
  preview_task  = generate_pdf_preview(pdf)            # pymupdf page0 @2x -> PIL resize<=800w -> S3
  metadata_task = llm_client.extract_paper_metadata(text) unless skip_metadata_extraction
  gather(preview_task, metadata_task, return_exceptions=True)
  return PDFProcessingResult{metadata, preview_url, raw_text, page_offsets, processing_duration}

webhook handler (server): enrich Paper{title,abstract,authors,keywords,summary,highlights,
    file_url,preview_url,page_offsets,raw_text}; set PaperUploadJob COMPLETED/FAILED.
```

### LLM metadata extraction (4 parallel calls + context cache)

```python
CACHE_MIN_CONTENT_CHARS = 5000
if len(text) >= CACHE_MIN_CONTENT_CHARS:
    cache = genai.create_cache(text, ttl=3600)   # >=1024 tokens required; share across the 4 calls
# else inline text in each request
results = await asyncio.gather(
    call(TitleAuthorsAbstract),    # title, authors[], abstract, publish_date   -- HARD FAIL if this errors
    call(InstitutionsKeywords),    # institutions[], keywords[]
    call(SummaryAndCitations),     # summary (<=200 words), summary_citations[]
    call(Highlights),              # verbatim quotes, typed by HighlightType category
    return_exceptions=True,
)
# model: FAST_CHAT_MODEL = "gemini-3-flash-preview"; response_mime_type="application/json",
# response_schema=<Pydantic>; 3 retries + exp backoff per call.
# title call failure re-raises (whole job fails); others degrade to empty defaults.
```

### Celery config (worker hardening) — `jobs/src/celery_app.py`

```python
BROKER_URL  = os.getenv("CELERY_BROKER_URL", "pyamqp://guest@localhost:5672//")   # RabbitMQ
BACKEND_URL = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")       # Redis
celery_app = Celery("openpaper_tasks", broker=BROKER_URL, backend=BACKEND_URL)
# queues: pdf_processing, user_processing, zotero_sync
worker_prefetch_multiplier = 1        # one task at a time
task_acks_late = True                 # ack after completion
reject_on_worker_lost = True          # re-queue on crash
worker_max_tasks_per_child = 1000     # recycle process (leak control)
worker_max_memory_per_child = 500000  # 500 MB ceiling
result_expires = 3600
# beat: periodic_zotero_sync every 24h on zotero_sync queue
```

`run_async_safely()`: new event loop per task, run coroutine, cancel pending tasks + `shutdown_asyncgens()`, close loop — avoids "event loop is closed" in sync Celery workers.

### Status polling

`GET /api/paper-upload/status/{job_id}` reads `PaperUploadJob.status`; if PENDING/RUNNING also calls
the jobs HTTP API `GET {CELERY_API_URL}/task/{task_id}/status` → `{status, progress_message, error}`.
Returns `{job_id, status, celery_status, celery_progress_message, has_file_url, has_metadata, paper_id}`.
`has_metadata = bool(paper.abstract)` is the completion signal.

## Data contracts

- **PaperUploadJob:** `{id, user_id, status: PENDING|RUNNING|COMPLETED|FAILED|CANCELLED, task_id, started_at, completed_at, created_at}`.
- **Paper (relevant):** `{id, upload_job_id, s3_object_key, file_url, preview_url, raw_text, page_offsets: {page:{start,end}}, title, authors, abstract, institutions, keywords, summary, summary_citations, highlights:[{text,annotation,type}], publish_date}`.
- **Celery task args:** `[s3_object_key, webhook_url]` + kwarg `skip_metadata_extraction:bool`.
- **Webhook payload:** `{task_id, status:"completed"|"failed", result: PDFProcessingResult|None, error:str|None}`.
- **PDFProcessingResult:** `{success, metadata, preview_url, raw_text, page_offsets, processing_duration, error}`.
- **S3 keys:** UUID-named (no extension); public URL = `https://<CLOUDFLARE_DOMAIN>/<key>`.

## Dependencies & assumptions

- **jobs service:** celery, pymupdf / pymupdf4llm, markitdown, Pillow, google-genai, boto3, requests, pydantic, fastapi (tiny HTTP API for task status), python-dotenv.
- **server:** fastapi, sqlalchemy, pypdf (validation), requests.
- **Infra:** RabbitMQ (broker) + Redis (result backend) + S3/Cloudflare CDN.
- **Env:** `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `GOOGLE_API_KEY`, `CELERY_API_URL`,
  `WEBHOOK_BASE_URL`, AWS creds + bucket vars (exact names unconfirmed).
- Swappable: any Celery-compatible broker; any markdown-PDF extractor; any structured-output LLM
  (replace the 4 Gemini calls + cache with your provider).

## To port this, you need:

- [ ] A background worker (Celery or equivalent) on a dedicated queue.
- [ ] Object storage (S3) + a public CDN URL scheme.
- [ ] A markdown text extractor with a fallback, and a page→offset mapper.
- [ ] A validation gate (size/pages/encryption/min-text).
- [ ] A structured-output LLM step (parallelized, with graceful per-subtask degradation; only the title call hard-fails).
- [ ] Placeholder-Paper + Job rows, a webhook handler to enrich them, and a status endpoint surfacing live worker progress.
- [ ] A `skip_metadata_extraction` flag for trusted-metadata sources (Zotero).

## Gotchas

- **The worker must not write the DB directly** — it POSTs a webhook; the server owns writes. Keeps the worker stateless.
- **Placeholder rows mean fields are NULL until done** — use `bool(abstract)` (or a job status) as the completion check, never row-existence.
- **Only the title subtask is allowed to hard-fail.** If you make all four hard-fail, one flaky call loses the paper; if none do, you ship papers with no title.
- **Context cache has minimums** (≥1024 tokens, gated at 5,000 chars) — below that, inline the text; cache-create failure must fall back silently.
- **PDF libs leak memory** — without `worker_max_memory_per_child` / `max_tasks_per_child`, workers bloat and OOM.
- **No retry on the outer task** — re-queue-on-crash is the only retry; the LLM calls retry internally (3×). Decide if that's enough.
- **Async-in-Celery** needs the new-loop-per-task shim or you hit "event loop is closed".
- **Scanned PDFs** (image-only) produce <1000 chars → rejected; if you need OCR, add it before the length check.

## Origin (reference only)

khoj-ai/openpaper @ `master`:
`jobs/src/pdf_processor.py`, `jobs/src/parser.py`, `jobs/src/tasks.py`, `jobs/src/celery_app.py`,
`jobs/src/llm_client.py`, `jobs/src/s3_service.py`, `jobs/src/schemas.py`, `jobs/extract_svg.py`
(standalone CLI, not wired into the pipeline);
`server/app/api/paper_upload_api.py`, `server/app/helpers/pdf_jobs.py`,
`server/app/database/crud/paper_upload_crud.py`, `server/app/api/webhook_api.py`.

**Gaps to verify:** exact S3 bucket env var names; `MAX_LLM_CONTENT_CHARS` literal; the webhook
handler's exact field writes; the 4 Pydantic extraction schemas and their prompts (`jobs/src/prompts.py`).
