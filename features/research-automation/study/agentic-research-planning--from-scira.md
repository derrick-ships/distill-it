# Agentic Research Planning — from [scira](https://github.com/zaidmukaddam/scira)

> Domain: [[_domain]] · Source: https://github.com/zaidmukaddam/scira · NotebookLM: <link once added>

## What it does

You ask a hard, open-ended question — "what's the state of solid-state batteries and who's
shipping them?" — and instead of one search-and-summarize pass, Scira's "Extreme" mode plans the
research first, then sends an autonomous agent to do dozens of searches, read pages, run code, and
keep digging until it has enough to write a cited answer. You watch the plan and the steps stream in
live. It's the difference between asking a librarian for a book versus asking them to write you a
briefing.

## Why it exists

The hard part of research isn't reading a page — it's deciding *what to look up next*. A single
LLM call with a web-search tool gives shallow answers because the model only gets one or two rounds.
Scira splits the work: a cheap planning pass turns the question into a structured research plan
(topics + the specific things to find for each), and a separate long-running agent executes that
plan with a big step budget. This gets depth (the agent can run up to ~75 tool steps) without
letting the *outer* chat loop run wild.

## How it actually works

When the user is in "Extreme" mode, the model is given exactly one tool: `extreme_search`. When it
calls that tool, two phases run *inside the tool*, before the tool returns anything:

**Phase A — Planning.** A fixed cheap model (`scira-ext-1`) is asked to produce a structured plan:
1–5 research *topics*, each with a 10–70-char title and 3–5 concrete "todos" (things to find out).
This plan is generated with the AI SDK's structured-output mode (a Zod schema forces the shape), and
it's streamed to the UI immediately so the user sees "here's how I'll research this."

**Phase B — Execution.** A second, more capable model runs as an autonomous agent with a budget of
up to **75 steps** and its own toolbox: `webSearch` (Exa neural search + content extraction),
`browsePage` (scrape a specific URL), `xSearch` (X/Twitter), `codeRunner` (run Python in a Daytona
sandbox, e.g. to chart data), `fileQuery` (search the user's uploaded files), `thinking` (emit
visible reasoning), and `done` (signal completion and hand back the accumulated sources + charts).
The agent loops: think → search/browse/run → accumulate sources → decide next move → … → done.

Every step emits a typed `data-extreme_search` event (`kind: plan | thinking | search | browse |
file_query | code`) so the UI renders a live activity feed. When the agent calls `done`, the tool
returns a `Research` object (`{ toolResults, sources, charts }`) to the *outer* chat model, which
then writes the final prose answer with inline citations.

The outer loop is deliberately tiny: the main `streamText` call uses `stopWhen: stepCountIs(5)` — at
most 5 outer tool cycles. All the depth lives in the 75-step inner agent. Two separate step counters,
two separate models, two separate jobs.

## The non-obvious parts

- **Plan-then-execute beats one big loop.** Separating a cheap structured planning pass from an
  expensive execution agent is what makes this reliable. The plan is a contract the executor follows.
- **The planning model is hardcoded** to `scira-ext-1` regardless of which model the user picked for
  execution. Planning is cheap and standardized; execution is where the user's model choice matters.
- **Nested step budgets.** Outer chat: 5 steps. Inner research agent: 75. A re-implementer who only
  sees the outer `stepCountIs(5)` will wrongly conclude the system can't go deep.
- **The "multi-agent" mode is a totally different animal** — it doesn't use `extreme_search` at all;
  it hands the whole job to xAI's server-side Grok agent with native web/X tools. Same UI, different
  engine underneath.
- **Citations aren't post-processed** — see [[grounded-retrieval-citations--from-scira]]. The agent
  collects sources; the final model is *prompted* to cite them inline as it writes.

## Related
- [[grounded-retrieval-citations--from-scira]] (the citation half of the same answer)
- [[tool-and-search-mode-registry--from-scira]] (how "Extreme" mode maps to just `extreme_search`)
- [[resumable-streaming-search--from-scira]] (how the live plan/steps reach the browser)
- [[deep-research-loop--from-firecrawl]] (a simpler depth-bounded research loop — good contrast)
- [[multi-source-research-engine--from-last30days-skill]] (parallel-source research, different shape)
