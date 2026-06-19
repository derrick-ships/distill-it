# AI Lead Classification (Claude) — from [auto-crm](https://github.com/Hainrixz/auto-crm)

> Domain: [[_domain]] · Source: https://github.com/Hainrixz/auto-crm (`src/lib/claude.ts`, `src/app/api/classify/route.ts`) · NotebookLM: <add link>

## What it does
When you turn on the optional Claude integration (by setting an API key), the CRM stops grading
leads with its little arithmetic formula and instead *asks an LLM* to read the lead like a sales
manager would. It hands Claude the contact's name, company, source, notes, and the full history of
logged interactions, and gets back a structured verdict: a temperature (cold/warm/hot), a confidence
score from 0 to 100, a recommended next action ("call them this week", "send the proposal"), and a
short reasoning — all written in Spanish, the product's primary language. If the AI is off, the key
is missing, or anything goes wrong, the product silently falls back to the rule-based score and the
user never sees an error.

## Why it exists
The rule-based engine is fast and free but dumb — it can't read the *content* of a note that says
"customer's budget got cut, revisit Q3." The job-to-be-done here is **qualitative judgment**: a
human-quality read of soft signals (tone of notes, nature of interactions) that no weighted-sum
formula can capture. The product's strategy is a classic free-tier/upgrade ladder: ship a capable
offline baseline, then let power users plug in their own Claude key for a smarter experience. The
key word is *optional* — the AI is never a hard dependency, which protects the "runs locally, no
subscription" promise while still offering an AI upgrade path.

## How it actually works
There's a thin client module that lazily constructs a single Anthropic client the first time it's
needed, reading the API key from the environment. If there's no key, the constructor returns null
and the whole AI path is considered "disabled" — that null check (`isAIEnabled()`) is the on/off
switch for the entire feature.

When classification is requested for a contact, the route first asks "is AI enabled?" If yes, it
builds a prompt: a compact description of the contact (name, company, source, notes) plus a
normalized list of their activities (each reduced to type, description, and date). It sends this to
Claude (the Sonnet model) with a tight 500-token ceiling and instructions to respond *only* with a
specific JSON object — temperature, confidence, next action, reasoning, in Spanish.

The response handling is the clever-but-pragmatic part. Rather than trusting the model to emit clean
JSON, the code scrapes the response text for the first `{...}` block with a regex and parses that.
This survives the model wrapping its JSON in prose or markdown fences. If the parse succeeds, the
structured verdict flows back and the contact's temperature and score get written to the database
with `mode: "ai"` so the UI can show it was AI-graded.

If *anything* fails — no key, network error, malformed JSON, model refusal — the code falls through
to the exact same rule-based path the free tier uses. The fallback even has its own hard-coded
default object ("cold", score 25, next action "Revisar manualmente" / review manually, reasoning
"AI analysis failed") so callers always get a well-formed answer. The user is never shown the error;
the system just quietly degrades to the dumber-but-reliable engine.

## The non-obvious parts
- **The null-client pattern is the feature flag.** There's no separate "enable AI" setting; the
  presence or absence of an API key *is* the flag, surfaced through `isAIEnabled()`. Simple and
  fool-proof.
- **Regex JSON extraction, not strict parsing.** `\{[\s\S]*\}` grabs the first brace-to-last-brace
  span. This is a deliberate robustness hedge against LLMs that add commentary — cheaper than tool
  use / JSON mode, good enough for a single object. (Caveat: it's greedy and assumes one object.)
- **The fallback is total, not partial.** On any AI failure the code doesn't retry or surface an
  error — it runs the full rule-based classifier and returns *that*. From the caller's perspective
  the two modes are interchangeable; only the `mode` field differs.
- **Spanish-first prompting.** The model is explicitly told to answer in Spanish, matching the
  product's bilingual-but-Spanish-primary audience. The next-action and reasoning strings go
  straight into the UI, so language consistency matters.
- **Both paths write identically.** Whether AI or rules, the persistence is the same `UPDATE
  contacts SET temperature, score, updatedAt` — the engines are swappable behind one stable write.
- **500-token cap** keeps cost and latency bounded; the structured output is small by design.

## Related
- [[rule-based-lead-scoring--from-auto-crm]] — the deterministic engine this falls back to; they
  share the same write contract and are interchangeable behind `/api/classify`.
- [[provider-agnostic-llm--from-llm-scraper]] — a contrasting choice: abstract *above* the vendor
  (multi-provider SDK) rather than bind directly to the Anthropic client as auto-crm does here.
- [[mcp-crm-server--from-auto-crm]] — the other half of auto-crm's AI story: instead of calling
  Claude *from* the app, it exposes the app *to* Claude as tools.
