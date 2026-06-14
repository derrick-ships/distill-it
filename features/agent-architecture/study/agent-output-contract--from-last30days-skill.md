# Agent Output Contract (5 Laws) — from [last30days-skill](https://github.com/mvanhorn/last30days-skill)

> Domain: [[_domain]] · Source: https://github.com/mvanhorn/last30days-skill · NotebookLM:

## What it does

Defines five non-negotiable rules that the LLM layer must follow when presenting research output to the user. These laws live in SKILL.md — the prose contract between the agent runtime and the model — and constrain how the model formats its response regardless of what the underlying engine returns.

## Why it exists

LLMs are non-deterministic. Without explicit output constraints, the same research results get formatted differently on every run: sometimes with a trailing "Sources:" block, sometimes with invented section headers, sometimes with em-dashes, sometimes without. Downstream consumers (Slack, email, copy-paste workflows) break when formatting is inconsistent. The 5 Laws exist to make output predictable without over-specifying the model's synthesis work.

## How it actually works

The laws are written directly into SKILL.md as numbered constraints under "Output contract." They are enforced by instruction, not code — the model reads them as part of its system prompt and is expected to comply. The engine (Python) does the retrieval; SKILL.md tells the model exactly how to present what the engine returns.

**The 5 Laws:**
1. **No trailing Sources block** — the engine footer already contains citations; adding a second Sources section creates duplication and visual noise.
2. **No invented title lines** — for general queries use "What I learned:" as the opening; don't make up a headline that implies false authority over the topic.
3. **Use ` - ` not em-dashes** — plain hyphens with spaces, not `—`. This is a rendering compatibility choice: em-dashes break in certain Slack/email clients.
4. **No `##` section headers in body** — headers fragment the output into a rigid structure that doesn't match the conversational register of research synthesis. Exception: comparison queries (Tool A vs Tool B) may use headers to separate entities.
5. **Engine footer passes through verbatim** — the Python engine appends a citations/metadata footer. The model must reproduce it exactly, without rewording, summarizing, or moving it.

**The prose/code contract:** SKILL.md is described as the "runtime contract" — when SKILL.md and any other documentation disagree, SKILL.md wins. This makes the output laws robust to documentation drift.

## The non-obvious parts

- The laws are enforced by the skill author having shipped enough versions to know exactly which formatting failures recur. Each law corresponds to a real regression observed in production.
- Cross-harness compatibility is a first-class concern: any law that only works in one platform (e.g., relies on a Claude-specific feature) is a regression. The laws are written in plain natural language precisely so they work in Cursor, Copilot, and Gemini CLI, not just Claude.
- "Verbatim footer passthrough" is the hardest law for models to follow — they naturally want to summarize or reformat. The law must be stated explicitly and without hedging.

## Related

- [[multi-source-research-engine--from-last30days-skill]] — the engine whose output these laws govern
