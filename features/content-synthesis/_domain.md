# Domain: content-synthesis

Turning raw multi-source retrieval results into coherent, deduplicated, ranked summaries — clustering duplicate stories, selecting diverse representatives, and generating shareable output formats.

## What this domain is about

Raw retrieval from multiple sources produces redundancy: the same story appears on Reddit, X, and YouTube with different phrasing. Content synthesis covers the algorithms that merge these duplicates, select the best representative items, and shape the output into something a human or LLM can consume efficiently.

## Core patterns

- **Two-pass clustering**: Text similarity (greedy) then entity-based merging for same-story-different-phrasing
- **MMR representative selection**: Maximal Marginal Relevance balances quality vs diversity within clusters
- **Uncertainty flagging**: Single-source and thin-evidence signals get explicit flags rather than silent omission

## Features in this domain

- [[cross-source-clustering--from-last30days-skill]] — two-pass clustering with MMR representative selection
- [[ai-carousel-generation--from-carousel-generator]] — forced OpenAI function-call into a Zod content schema, with a styled/unstyled split so the LLM fills only content and styling defaults are merged in deterministically
- [[generate-llms-txt--from-firecrawl]] — auto-build a site's llms.txt (titled page list + one-line descriptions) and optional llms-full.txt by composing map → scrape → per-page summary LLM. A clean example of synthesizing a machine-readable index from a whole site.
