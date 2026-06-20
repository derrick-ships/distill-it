# Grounded Retrieval + Inline Citations (build spec) — distilled from scira

## Summary

Produce answers where every claim links inline to its source, **without a citation post-processor**.
The recipe: (1) retrieval tools return structured `{url, title, content}` results; (2) the model gets
those raw results as tool output; (3) a strict system-prompt rule-block instructs the model to emit
`[descriptive text](url)` inline as it writes. Grounding quality = good retrieval + precise prompt +
dedup/fallback/truncation hygiene on the results. SDK-agnostic; Scira uses the Vercel AI SDK.

## Core logic (inlined)

**1. Retrieval tool returns a structured, citeable shape** (`web_search`):

```ts
// model calls with: { queries:string[3+], maxResults?:number[], topics?:('general'|'news')[],
//                     quality?:('default'|'best')[], startDates?:(string|null)[] }
// returns:
{
  searches: Array<{
    query: string;
    results: Array<{ url: string; title: string; content: string;   // TRUNCATED before return
                     published_date?: string; author?: string }>;
    images: Array<{ url: string; description: string }>;
  }>
}
```

**2. Retrieval hygiene before the model sees results:**

```ts
// a) domain+url dedup — keep first per domain
function deduplicateByDomainAndUrl(results) {
  const seenDomain = new Set(), seenUrl = new Set(), out = [];
  for (const r of results) {
    const domain = new URL(r.url).hostname;
    if (seenUrl.has(r.url) || seenDomain.has(domain)) continue;
    seenUrl.add(r.url); seenDomain.add(domain); out.push(r);
  }
  return out;
}
// b) fallback chain when content is empty: Exa search -> Firecrawl scrape(url) -> metadata service
// c) truncate content (~1000 Parallel / ~3000 Exa highlights) so prompts stay bounded
```

**3. The citation contract lives in the system prompt** (verbatim-style rule block — this IS the
"engine"):

```text
CITATION RULES (enforced by prompt, not code):
- Cite inline using [descriptive text](url) immediately after the sentence it supports.
- NEVER use numbered footnotes like [1], a "References"/"Sources" section, or bare URLs.
- Display text must be a descriptive snippet — never "Source", "Link", "here", or the bare domain.
- Do NOT put a period immediately after a citation link.
- Do NOT use pipe characters | between or inside citations — separate multiple with a space:
  [text one](url1) [text two](url2)
- (Reddit mode) Use the actual Reddit post title as the citation display text.
- (X mode) Do not use Twitter search operators inside query strings.
```

The model receives `results[]` (title+url+content) as tool output and writes prose with `[title](url)`
inline. No server-side rewrite of the answer occurs.

## Data contracts

The citeable source object the model is handed (and that an optional sources sidebar can render):
```ts
interface SearchResult {
  title: string; url: string; content: string; publishedDate: string;
  favicon: string; description?: string; canonical?: string;
  ogUrl?: string; finalUrl?: string; siteName?: string | null; image?: string;
}
```
Per-query progress event (optional UI):
```ts
{ type: 'data-query_completion',
  data: { query, index, total, status: 'started'|'completed'|'error', resultsCount, imagesCount } }
```

## Dependencies & assumptions

- A search/scrape provider that returns URL + title + text. Scira supports Exa / Firecrawl / Parallel,
  picked per request via a `searchProvider` field; any single provider works.
- An LLM strong at instruction-following (the citation format is enforced purely by prompt).
- (Optional) a metadata-fetch fallback for URLs whose content came back empty.

## To port this, you need:
- [ ] A retrieval tool returning `{ url, title, content }[]` (+ optional images/dates).
- [ ] A dedup pass (by domain and URL) over results before they reach the model.
- [ ] A content-truncation step to bound prompt size.
- [ ] A strict, explicit citation rule-block in your system prompt (copy the rules above).
- [ ] A model that follows formatting instructions reliably; test the format holds under load.
- [ ] (Optional) per-mode prompt variants if different source types need different link text.

## Gotchas

- **It's only as reliable as instruction-following.** No code guarantees the format — weaker models
  drift into footnotes or bare URLs. Validate output format in evals; consider a light post-check
  (regex for `[1]`/"References") as a guardrail if you can't trust the model.
- **Domain dedup drops legitimate sources** from the same site. If recall matters (e.g. multiple docs
  pages from one domain), relax the domain rule and dedup by URL only.
- **Truncation caps what's citeable** — a fact past the cutoff can't be grounded. Tune truncation to
  your model's context budget.
- **Don't add a "Sources:" list** thinking it helps — the whole design is inline-only; a trailing
  list fights the prompt and confuses the model's formatting.
- **Empty content must be prevented, not tolerated** — a result with a URL but no text invites the
  model to cite something it didn't read. The fallback chain exists for exactly this.

## Origin (reference only)

- Repo: https://github.com/zaidmukaddam/scira
- `lib/tools/web-search.ts` (retrieval, provider strategies, dedup, truncation, `data-query_completion`
  events), `lib/search/group-config.ts` (`localGroupInstructions` — the per-mode citation rule blocks),
  `lib/tools/extreme-search.ts` (the deep-research `sources` accumulation).
- **Verify before relying on:** whether `SearchResult[]` is surfaced to the client as a separate
  sources sidebar or only embedded in the answer text was not confirmed — citations in the prose are
  the confirmed mechanism.
