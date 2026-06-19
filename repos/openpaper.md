# Open Paper — origin index

- **Source:** https://github.com/khoj-ai/openpaper
- **What it is:** An AI-powered research-paper workbench. Upload PDFs, read and annotate them, search
  your library, and chat with a citation-grounded copilot that answers only from evidence pulled out of
  the actual papers. Also does audio overviews, Zotero import, and multi-paper projects.
- **Author:** Khoj AI · **License:** AGPL-3.0
- **Stack:** TypeScript/Next.js client · Python FastAPI server · separate Celery `jobs` worker ·
  Postgres · S3/Cloudflare CDN · RabbitMQ + Redis · LLMs via Gemini + Cerebras + Azure OpenAI (TTS).
- **Date distilled:** 2026-06-18
- **Architecture in one line:** upload → (Celery worker: markitdown/pymupdf text + page offsets +
  4 parallel Gemini metadata calls) → Postgres Paper row → {citation-grounded chat, ILIKE+OpenAlex
  search, anchored highlights, Azure TTS audio overviews}, all behind opaque-token multi-provider auth.

## Features extracted
| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Citation-Grounded Chat | ai-integration | [study](../features/ai-integration/study/citation-grounded-chat--from-openpaper.md) | [build](../features/ai-integration/build/citation-grounded-chat--from-openpaper.md) |
| PDF Ingestion Pipeline | content-preprocessing | [study](../features/content-preprocessing/study/pdf-ingestion-pipeline--from-openpaper.md) | [build](../features/content-preprocessing/build/pdf-ingestion-pipeline--from-openpaper.md) |
| PDF Highlights & Annotations | canvas-interaction | [study](../features/canvas-interaction/study/pdf-highlights-annotations--from-openpaper.md) | [build](../features/canvas-interaction/build/pdf-highlights-annotations--from-openpaper.md) |
| Corpus & Academic Search | web-extraction | [study](../features/web-extraction/study/corpus-and-academic-search--from-openpaper.md) | [build](../features/web-extraction/build/corpus-and-academic-search--from-openpaper.md) |
| Audio Overview (TTS) | tts | [study](../features/tts/study/audio-overview-tts--from-openpaper.md) | [build](../features/tts/build/audio-overview-tts--from-openpaper.md) |
| Multi-Path Authentication | credential-management | [study](../features/credential-management/study/multi-path-auth--from-openpaper.md) | [build](../features/credential-management/build/multi-path-auth--from-openpaper.md) |

## Not yet distilled (candidates)
- **Stripe subscriptions + usage limits** (checkout/portal/webhook + tier quota gating) → domain: `payments`
- **Zotero library import** (pull a Zotero collection in as papers) → domain: `data-portability`
- **Discover / recommendation feed** → domain: `research-automation`
- **Projects: multi-paper workspace + data-table extraction + role invitations** → domain: `agent-architecture`
- **Abuse/guardrails** (advisory locks, abuse detection, subscription limits) → domain: `agent-guardrails`
- **Referral / growth loop** → domain: `onboarding`

## Verification gaps flagged in build docs (check before transplant)
- Exact generation/evidence prompts and `EvidenceCollection`/`CitationIndex` schemas — citation-grounded-chat build.
- S3 bucket env var names, `MAX_LLM_CONTENT_CHARS`, webhook field writes — pdf-ingestion-pipeline build.
- Client-side ScaledPosition capture/render code (client/ not fetched) — pdf-highlights-annotations build.
- Where Exa/OpenAlex results are merged/ranked (agent pipeline) — corpus-and-academic-search build.
- Script-gen LLM model; `ProjectAudioOverview` population — audio-overview-tts build.
- `ZoteroPending`/`ZoteroConnection` schemas; email transport; OAuth state/CSRF gap — multi-path-auth build.
