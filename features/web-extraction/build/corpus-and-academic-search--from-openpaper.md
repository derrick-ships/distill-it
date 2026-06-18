# Corpus & Academic Search (build spec) — distilled from openpaper

## Summary

Two independent search subsystems. (1) **Knowledge-base search**: case-insensitive `ILIKE` substring
scan over a user's papers + highlights + annotations, recency-ranked, no embeddings. (2) **External
academic discovery**: OpenAlex `works` API (UI-wired) with filters/sort and inverted-index abstract
reconstruction; Exa `search_and_contents` over curated academic domains (agent-only, not on a UI
route); a thin OpenAlex→Exa-shape adapter. Plus **metadata hydration**: a 3-pass DOI-resolve →
enrich → agentic-fallback that fills missing bibliographic fields, null-only, 30-day gated.

## Core logic (inlined)

### (1) Knowledge-base search — `database/queries/search.py`

```python
search_pattern = f"%{query.lower()}%"
paper_query = (db.query(Paper)
    .filter(Paper.user_id == user.id)
    .filter(Paper.id.in_(papers_filter) if papers_filter else True)
    .filter(or_(
        func.lower(Paper.title).like(search_pattern),
        func.lower(Paper.abstract).like(search_pattern),
        func.lower(Paper.raw_content).like(search_pattern),     # full PDF text
        Paper.id.in_(db.query(Highlight.paper_id).filter(and_(
            Highlight.user_id == user.id,
            func.lower(Highlight.raw_text).like(search_pattern)))),
        Paper.id.in_(db.query(Annotation.paper_id).filter(and_(
            Annotation.user_id == user.id,
            func.lower(Annotation.content).like(search_pattern)))),
    ))
    .order_by(Paper.last_accessed_at.desc())   # ranking = recency ONLY
    .limit(limit).offset(offset))
# then per paper: fetch the highlights + annotations that matched (N+1)
```

Result: `SearchResults{papers:[PaperResult], total_papers, total_highlights, total_annotations}` where
`PaperResult` includes only the matching `highlights[]` and `annotations[]` (annotations eager-load
their parent highlight via `joinedload`).

Request: `GET /search/?q=<>&limit=50&offset=0&papers_filter=<csv uuids>` (q min 2 chars, limit 1–100).

### (2a) OpenAlex discovery — `helpers/paper_search.py`

```python
def search_open_alex(search_term, filter=None, page=1, sort=None) -> OpenAlexResponse:
    base = "https://api.openalex.org/works"
    params = {"search": quote(search_term or ""), "page": page,
              "filter": quote(construct_open_alex_filter_url(filter)) if filter else None,
              "sort":   quote(sort) if sort else None}
    resp = _request_with_retry(_with_openalex_auth(constructed_url))  # 3 tries, 1s delay
    return OpenAlexResponse(**resp.json())

# filter string examples:
#   authorships.author.id:A123|A456   (pipe = OR)
#   institutions.id:I789
#   open_access.is_oa:true
#   from_publication_date:2023-01-01
#   cited_by_count:>N
# sort: "cited_by_count:desc" | "publication_date:desc"
# auth: optional ?api_key=OPENALEX_API_KEY (unauth works, rate-limited ~10 req/s)

def build_abstract_from_inverted_index(inv: dict) -> str:    # OpenAlex stores {word:[positions]}
    out = [""] * (max_index - min_index + 1)
    for word, positions in inv.items():
        for i in positions:
            out[i - min_index] = word
    return " ".join(out).strip()
```
Route: `POST /paper-search/search?query=&page=` body=`OpenAlexFilter`. Also `POST /paper-search/match`
(citation graph: `cites` + `cited_by`, hard-coded `per_page=20`) and `GET /paper-search/author`.

### (2b) Exa — `helpers/exa_search.py` (agent-only, no UI route)

```python
exa = Exa(api_key=EXA_API_KEY)   # raises ValueError if missing
resp = exa.search_and_contents(query=query, num_results=n, type="auto",
        category="research paper",
        text={"max_characters":500}, highlights={"num_sentences":3},
        summary={"query":"...focus on actual content..."},
        include_domains=domains or ACADEMIC_DOMAINS,   # ~60 curated: arxiv, biorxiv, pubmed, nature, ...
        start_published_date=start_published_date)     # ISO YYYY-MM-DD optional
# retry: 2x exp backoff on 429/500/502/503/504 (detected by regex on exa_py ValueError "status code NNN")
```
`ExaResult{title,url,authors:[str],published_date,text(<=500),highlights:[str],highlight_scores:[float],favicon,summary}`.
`openalex_search.py` returns `OpenAlexResult` with the SAME field shape (+`cited_by_count,source,institutions`) so an agent can run both and merge — that merge logic is upstream, not in these files.

### (3) Metadata hydration — `helpers/metadata_hydration.py`

3 passes, 30-day gate via `Paper.attempted_metadata_at` (bypass `force=True`); `attempted_metadata_at`
always stamped in `finally`.

- **Pass 1 — DOI resolve** (if `doi` missing, `title` present): CrossRef
  `GET api.crossref.org/works?query.title=&query.author=&rows=1` → OpenAlex (title substring + author
  set intersection) → Semantic Scholar **DISABLED** (`DISABLE_SEMANTIC_SCHOLAR=True`, 403s).
- **Pass 2 — enrich** (if `doi` present, journal/publisher missing): OpenAlex
  `GET /works/{doi_url}` → `primary_location.source.display_name` (journal) + resolve `host_organization`
  via `/publishers/{id}` or `/institutions/{id}`; CrossRef fallback (`container-title[0]`, `publisher`,
  `published-*.date-parts`). Returns `EnrichedData(publisher, journal, publication_date)`.
- **Pass 3 — agentic fallback** (only `agentic=True`): the metadata-recovery agent (Exa + Firecrawl +
  LLM), confidence-gated ≥0.7, null-only write-back with `field_provenance`. See
  [[citation-grounded-chat--from-openpaper]] build for the agent loop.

Write-back fields: `doi, journal, publisher, publish_date, attempted_metadata_at`.

## Data contracts

- **KB search req:** `{q:str(>=2), limit:int(1-100)=50, offset:int=0, papers_filter?:csv}`.
- **KB search resp:** `SearchResults{papers:[PaperResult{id,title,authors,abstract,status,publish_date,created_at,last_accessed_at,preview_url,highlights:[HighlightResult],annotations:[AnnotationResult]}], total_papers, total_highlights, total_annotations}`.
- **OpenAlexFilter (body):** `{authors?:[id], institutions?:[id], only_oa?:bool, from_publication_date?:date, min_cited_by_count?:int}`. **PaperSort:** `top_cited|newest`.
- **Unified external result:** `{title,url,authors:[str],published_date,text,highlights:[str],highlight_scores:[float],favicon,summary, (+cited_by_count,source,institutions for OpenAlex)}`.

## Dependencies & assumptions

- `requests` (OpenAlex/CrossRef), `exa_py`, `firecrawl` (`firecrawl-py` 4.x), `httpx` (inside exa_py), `sqlalchemy`, `pydantic` v2, `fastapi`.
- **Env:** `EXA_API_KEY` (required by exa module at use), `OPENALEX_API_KEY` (optional), `FIRECRAWL_API_KEY` (**raises at import if unset**), `SEMANTIC_SCHOLAR_API_KEY` (unused).
- Postgres for the `ILIKE` scan (no extensions required). No vector DB.
- Swappable: OpenAlex ↔ any academic API; Exa ↔ any web-search; the ILIKE scan ↔ tsvector/pg_trgm/vector if you want real ranking.

## To port this, you need:

- [ ] A KB search query over your paper/highlight/annotation tables (start with ILIKE; upgrade later).
- [ ] An OpenAlex client with filter-string construction + inverted-index abstract rebuild.
- [ ] (optional) An Exa client over a curated academic-domain allowlist for agent discovery.
- [ ] A metadata-hydration job: DOI resolve (CrossRef/OpenAlex) → enrich → optional agentic fallback, null-only write-back, with a re-run gate.

## Gotchas

- **ILIKE = full table scan on `raw_content`** per query; fine for small libraries, add an index/tsvector/pg_trgm at scale.
- **Recency-only ranking** — no relevance; the "best" match is just the most recently opened paper.
- **OpenAlex abstracts are inverted indexes** — reconstruct or you get nothing. Watch the 0-vs-nonzero base offset (`i - min_index`).
- **`FIRECRAWL_API_KEY` raises at import** — guard it or an unused scrape feature crashes startup.
- **Semantic Scholar is disabled** — don't rely on it; it 403s.
- **No dedup between Exa and OpenAlex** in these files — if you merge, dedup by DOI/title upstream.
- **N+1 in KB search** — batch the per-paper highlight/annotation fetch if result sets get large.

## Origin (reference only)

khoj-ai/openpaper @ `master`:
`server/app/database/queries/search.py` (KB ILIKE — inlined), `server/app/api/search_api.py`,
`server/app/api/paper_search_api.py`, `server/app/helpers/paper_search.py` (OpenAlex — inlined),
`server/app/helpers/exa_search.py` (Exa — inlined), `server/app/helpers/openalex_search.py` (adapter),
`server/app/helpers/metadata_hydration.py` (3-pass — inlined), `server/app/helpers/scrape.py` (Firecrawl).

**Gaps to verify:** where Exa/OpenAlex results are merged/ranked (agent pipeline not traced);
`Paper` model column names (`raw_content` vs `raw_text`); `bibliographic_gaps()`/`fields_from_paper()`
in `helpers/citations.py`; exact router mount prefixes.
