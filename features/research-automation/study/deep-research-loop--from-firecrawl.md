# Deep Research Loop — from [firecrawl](https://github.com/firecrawl/firecrawl)

> Domain: [[_domain]] · Source: https://github.com/firecrawl/firecrawl · NotebookLM: <link once added>

## What it does

You give it a question, not URLs — "what are the leading approaches to battery recycling and who's
funding them?" — and it goes off, searches the web, reads pages, figures out what it still doesn't know,
searches again, and keeps going until it's confident or runs out of time, then writes you a synthesized
report with its sources. It's autonomous research: you describe the goal, it does the legwork.

## Why it exists

The hardest part of research isn't reading one page — it's deciding *what to read next*. Deep research
automates that loop: each round's findings shape the next round's queries, so the system drills deeper
on its own instead of you babysitting a search box. It's the "agent that gathers data without knowing
the URLs upfront" capability.

## How it actually works

It's an async job with a depth-bounded loop. A `ResearchStateManager` tracks the current depth, the
accumulated sources, and the *next search topic*; a `ResearchLLMService` does the thinking. The loop,
per round (until `maxDepth` or the time limit):

1. **Generate search queries** from the current topic and what's been learned so far.
2. **Search and scrape** those queries — it reuses the existing search-and-scrape machinery to pull
   real page content, not just snippets.
3. **Record sources** and analyze the new content: what did we learn, what's still missing?
4. **Decide the next search topic** from that analysis, and increment depth.

Progress is written to Redis the whole time as an "activities" stream plus the growing source list, so
the client polling `/deep-research/{id}/status` sees live steps ("searching…", "analyzing…",
"complete"). The system budgets `maxDepth × 5` expected steps for a progress bar. When the loop ends, a
final LLM pass synthesizes everything into a report against a system prompt, and the job completes.

## The non-obvious parts

- **The loop is the product.** The intelligence is in "analyze findings → choose the next query," not in
  any single search. That feedback step is what makes it *deep* rather than a one-shot search.
- **It reuses search+scrape wholesale** — deep research doesn't reimplement fetching; it orchestrates the
  same [[web-search-with-scrape--from-firecrawl]] path in a loop.
- **Two stop conditions**: hitting `maxDepth` or a wall-clock `timeLimit`. Autonomous loops need a leash;
  this one has two.
- **Live activity streaming** via Redis is what makes a multi-minute job feel responsive — the user sees
  it thinking.
- **`maxDepth × 5` steps** is a heuristic for the progress estimate, not a hard structure.
- **Final synthesis is a separate pass** with its own system prompt — gather, then write, kept distinct.

## Related
- [[web-search-with-scrape--from-firecrawl]] (each research round calls this to get page content)
- [[agentic-browser-actions--from-firecrawl]] (the single-page agent; deep research is the multi-page agent)
- [[llm-extract-map-reduce--from-firecrawl]] (a structured-output sibling; research outputs prose+sources)
- See also: [[multi-source-research-engine--from-last30days-skill]].
