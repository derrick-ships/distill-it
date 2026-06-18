# Corpus & Academic Search — from [openpaper](https://github.com/khoj-ai/openpaper)

> Domain: [[_domain]] · Source: https://github.com/khoj-ai/openpaper · NotebookLM: <link once added>

## What it does

Two different "search" jobs share a name. One searches **your own library** — type a phrase and it
finds the papers (and your highlights and notes) that contain it. The other searches **the outside
world of academic papers** — query OpenAlex (and, in the agent paths, Exa) to discover new papers to
add, with rich metadata. Open Paper keeps these as two separate subsystems that don't merge.

## Why it exists

A research workbench needs both "find what I already have" and "find what's out there." Internal
search makes your growing library navigable; external discovery is how the library grows and how the
chat agent pulls in fresh sources. And once a paper exists, **metadata hydration** quietly fills in
the missing journal/DOI/date so citations come out correct.

## How it actually works

**Internal (knowledge-base) search** is deliberately simple: a case-insensitive `ILIKE '%query%'`
substring scan across `Paper.title`, `Paper.abstract`, `Paper.raw_content` (the full extracted PDF
text), plus your `Highlight.raw_text` and `Annotation.content`. Results are papers, each carrying the
specific highlights and annotations that matched. Ranking is **recency only** (`last_accessed_at`
desc) — no relevance scoring, no embeddings, no typo tolerance. Pagination is limit/offset.

**External (OpenAlex) discovery** is the route wired into the UI. It calls
`https://api.openalex.org/works?search=...` with optional filters (authors, institutions,
open-access-only, from-date, min-citations) and sort (`cited_by_count:desc` or
`publication_date:desc`). OpenAlex returns abstracts as an *inverted index* (`{word: [positions]}`),
so there's a small routine that rebuilds the readable abstract string from it. There's also a citation
graph endpoint that pulls a work's references and citing works.

**Exa search** exists (`exa.search_and_contents` restricted to ~60 curated academic domains, with
highlights and AI summaries) but is **not exposed on any UI route** — it's invoked from the chat/agent
pipelines. A thin OpenAlex adapter normalizes OpenAlex results into the same shape as Exa results,
which strongly implies an upstream agent that runs both and compares them.

**Metadata hydration** runs lazily when a paper is read (and in background after upload). It's a
three-pass process: resolve a missing DOI (CrossRef → OpenAlex; Semantic Scholar is coded but
disabled due to 403s), enrich journal/publisher/date from the DOI, and — only when explicitly asked —
an agentic fallback that web-searches (Exa) and scrapes (Firecrawl) with an LLM to fill the last gaps,
writing back only null fields it's confident about. A 30-day stamp stops it re-running constantly.

## The non-obvious parts

- **No vector search anywhere.** Internal search is pure substring `ILIKE`. Simple, no infra, but no
  semantic recall — a deliberate trade.
- **KB and external search never merge.** Two routers, two result shapes; the client calls whichever it needs.
- **Exa is in the codebase but off the UI** — discovery-by-Exa happens only inside agents.
- **Inverted-index abstracts.** OpenAlex doesn't give you a sentence; you reconstruct it from word
  positions. Easy to forget and end up with empty abstracts.
- **Semantic Scholar is permanently disabled** (`DISABLE_SEMANTIC_SCHOLAR = True`) — kept in code, bypassed in practice.
- **Firecrawl key crashes startup if missing** — the scrape module raises at import, so a never-used
  feature can take down the whole server.
- **N+1 in KB search** — one paper query, then two extra queries per matched paper for its
  highlights/annotations.

## Related
- [[citation-grounded-chat--from-openpaper]] (the corpus evidence pass and the metadata-recovery agent both lean on these search paths)
- [[pdf-ingestion-pipeline--from-openpaper]] (produces the `raw_content` that KB search scans)
- [[pdf-highlights-annotations--from-openpaper]] (highlight/annotation text is part of the KB search surface)
- See also: any RAG retrieval layer — here it's keyword + external API, not embeddings.
