# Agentic Browser Actions (smart-scrape) — from [firecrawl](https://github.com/firecrawl/firecrawl)

> Domain: [[_domain]] · Source: https://github.com/firecrawl/firecrawl · NotebookLM: <link once added>

## What it does

For pages where the content only appears after you *do* something — click a "load more," fill a search
box, dismiss a cookie wall, scroll to lazy-load — you give a plain-English instruction ("expand all the
FAQ items, then grab the page") and an AI agent drives a real browser to satisfy it before the page is
captured. The scrape then returns the post-interaction HTML/markdown.

## Why it exists

A huge slice of "the web that won't scrape" isn't blocked — it's *interactive*. The data is there but
gated behind clicks and JS. Hard-coding a click sequence per site doesn't scale; describing the goal in
words and letting an agent figure out the actions does. This is what turns "JS-heavy pages" from a
failure into a result.

## How it actually works

It's a transformer in the scrape pipeline (`performAgent`) that fires only when the request carries an
agent `prompt`. It hands the URL + prompt off to **smart-scrape**, a call into fire-engine's hosted
browser that runs an LLM-driven loop: the model is given the page and the goal and decides the browser
actions (click/scroll/type/wait) to take, iterating until the goal is met. It returns a list of
`scrapedPages`, each with the HTML at that step; firecrawl takes the **last page's HTML** (the final
post-interaction state) and converts it to markdown/HTML per the requested formats.

The smart-scrape model is tiered: a primary model (`gemini-2.5-pro`) with a faster fallback
(`gemini-2.5-flash`). The whole thing is **cost-tracked and cost-capped** — if it blows the cost limit
it returns the page with a warning instead of failing the scrape. It's explicitly **disabled under
zero-data-retention** (the agent loop needs to retain page state), where it returns a warning and the
plain page.

## The non-obvious parts

- **Goal in words, actions inferred.** You don't script clicks; the agent decides them from your prompt.
  This is the difference from a fixed `actions: [...]` list (which firecrawl also supports separately).
- **It's a pipeline transformer**, not a separate endpoint — agent mode bolts onto a normal scrape via
  `internalOptions.v1Agent.prompt`, so it composes with all the other formats.
- **"Last page wins."** The agent may visit several intermediate states; only the final HTML is kept.
- **Cost-capped, soft-fail.** Exceeding the budget yields a warning + best-effort page, never a hard
  error — agentic browsing is expensive and unbounded by nature, so it's fenced.
- **Off under ZDR** — the agent needs to hold page state, which conflicts with zero-data-retention.
- **Needs the hosted browser** (fire-engine) — there's no local-only agent path.

## Related
- [[scrape-engine-fallback-pipeline--from-firecrawl]] (agent mode is a transformer in this pipeline; `actions` need fire-engine)
- [[deep-research-loop--from-firecrawl]] (the macro version: an agent loop over many pages, not one)
- [[llm-extract-map-reduce--from-firecrawl]] (smart-scrape can also return structured data per its schema)
