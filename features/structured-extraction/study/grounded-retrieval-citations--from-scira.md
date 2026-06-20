# Grounded Retrieval + Inline Citations — from [scira](https://github.com/zaidmukaddam/scira)

> Domain: [[_domain]] · Source: https://github.com/zaidmukaddam/scira · NotebookLM: <link once added>

## What it does

Every factual sentence in a Scira answer is a clickable link to the page it came from — not numbered
footnotes at the bottom, but inline `[descriptive text](url)` right where the claim is made. The
answer reads like a well-cited briefing where you can verify any line in one click.

## Why it exists

An AI research tool that can't show its sources is just a confident guesser. Grounding — tying each
claim to a retrievable URL — is the whole trust proposition. Scira's bet is that *inline* citations
(in the flow of the sentence) are far more useful than a reference list nobody scrolls to, because
they let you check the specific claim you doubt, not hunt through a bibliography.

## How it actually works

The surprising part: **there is no citation engine.** Scira does not parse the answer and inject
links afterward. Instead:

1. **Retrieval** happens in the tools. `web_search` runs 3–5 queries against a provider (Exa,
   Firecrawl, or Parallel, chosen by the user), and returns a structured list of `{ url, title,
   content, published_date, author }` results plus images. The deep-research agent's `webSearch`/
   `browsePage` tools do the same, accumulating a `sources` array.
2. **The model sees the raw results** — title + URL + (truncated) content — as the tool result in its
   message history.
3. **The system prompt does the rest.** The mode's instruction string (for the `web` group, and
   variants per mode) contains an exhaustive set of citation-formatting rules, and the model is told
   to emit `[title](url)` inline as it writes. The rules are strict and specific:
   - Use `[descriptive text](url)` immediately after the sentence the source supports.
   - **No** numbered footnotes (`[1]`), **no** "References" section, **no** bare URLs.
   - Display text must be a real descriptive snippet, never generic "Source" or "Link".
   - No period directly after a citation link; no pipe `|` between or inside citations (use a space).
   - Multiple sources inline as `[text1](url1) [text2](url2)`.
   - Reddit mode: use the actual Reddit post title as the link text.

So grounding is enforced by (a) giving the model real, retrieved sources and (b) prompting it
relentlessly to cite them in a fixed inline format. Quality comes from the retrieval being good and
the prompt being precise — not from post-processing.

A few retrieval-quality moves matter as much as the prompt:
- **Domain dedup.** `deduplicateByDomainAndUrl()` runs on each result set — if two URLs share a
  domain, only the first survives. Keeps the model from citing five pages of the same site.
- **Provider fallback chain.** Exa search → if content empty, Firecrawl scrape per URL → if still
  empty, a Scira-owned `metadata.scira.app` fallback. The model should never get an empty source.
- **Content truncation.** Results are trimmed (Parallel ~1000 chars, Exa highlights ~3000) before the
  model sees them, so the model cites based on snippets, not full pages.

## The non-obvious parts

- **Prompt-as-citation-engine.** The most counterintuitive thing: no regex, no link injector. The
  entire citation system is a long, very specific instruction block + good source data. Cheaper and
  more flexible than building a parser, at the cost of being only as reliable as the model's
  instruction-following.
- **Per-mode citation rules.** Reddit cites post titles; X mode has its own query rules. The citation
  format is tuned per search mode inside each mode's system prompt, not globally.
- **Dedup silently drops sources.** Domain dedup improves readability but means a multi-page result
  from one authoritative site loses all but the first page — a real recall trade-off.
- **Truncation shapes what gets cited.** The model can only ground claims in the snippet it was given;
  facts living past the truncation boundary simply can't be cited.

## Related
- [[agentic-research-planning--from-scira]] (the agent that gathers the sources this cites)
- [[tool-and-search-mode-registry--from-scira]] (where the per-mode citation prompts live)
- [[citation-grounded-chat--from-openpaper]] (a different take on grounded, cited answers)
- [[map-reduce-answer-generation--from-scrapegraph-ai]] (answer synthesis from retrieved chunks)
