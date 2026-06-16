# Streaming Partial Objects — from [llm-scraper](https://github.com/mishushakov/llm-scraper)

> Domain: [[_domain]] · Source: https://github.com/mishushakov/llm-scraper · NotebookLM: <add link>

## What it does
Same schema-driven extraction as [[schema-driven-extraction--from-llm-scraper]], but instead of waiting for the whole result, you get a stream of progressively-more-complete versions of your object. If you asked for 5 stories, you might first see an object with 1 story, then 2, then 3 — each emission a valid partial of your final schema. Good for showing results in a UI as they arrive instead of staring at a spinner.

## Why it exists
LLM extraction over a big page can take many seconds. For anything user-facing, perceived latency matters: streaming the object as it forms lets a UI render rows the moment they exist. The job-to-be-done is **responsiveness for slow structured generation** — same data, better felt experience.

## How it actually works
It's the `run()` loop with two swaps:

1. **Preprocess identically.** Page → format → content. No difference here.
2. **Use the streaming SDK call.** Instead of `generateText` it calls the AI SDK's `streamText`, again with the schema as the `output` constraint. The SDK exposes a `partialOutputStream` — an async iterable that yields the object-so-far each time the model emits enough new tokens to extend it.
3. **Return the stream, not the data.** The method returns `{ stream, url }`. The caller does `for await (const partial of stream) { ... }` and re-renders on each tick. The final iteration is the complete object.

Note it's *not* awaiting a final value internally — it kicks off the stream and hands back the iterable immediately.

## The non-obvious parts
- **Partials are valid-but-incomplete, not garbage.** The AI SDK guarantees each emission conforms to the schema as a partial (fields may be missing/empty, but types are right). You don't get half-parsed JSON.
- **It reuses the exact same message/prompt assembly** as the non-streaming path — the only real difference is `streamText` vs `generateText` and reading `partialOutputStream` vs `output`. The two methods are near-mirror images by design.
- **No final aggregated return value is exposed here.** You reconstruct "done" by consuming the stream to its end; the last partial is your answer. If you need the awaited final object too, you'd add it (the SDK provides it) — this library keeps the surface minimal.
- **Backpressure/cancellation is the caller's job.** Stop iterating and the underlying request is abandoned by the runtime; the library adds nothing on top.

## Related
- [[schema-driven-extraction--from-llm-scraper]] — the non-streaming sibling; read it first.
- [[page-format-pipeline--from-llm-scraper]] — shared preprocessing.
- [[provider-agnostic-llm--from-llm-scraper]] — streaming works across providers via the SDK.
