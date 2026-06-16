# Scraper Code Generation — from [llm-scraper](https://github.com/mishushakov/llm-scraper)

> Domain: [[_domain]] · Source: https://github.com/mishushakov/llm-scraper · NotebookLM: <add link>

## What it does
Instead of extracting data from a page, it asks the LLM to *write a JavaScript function* that will extract that data — a self-contained snippet you can run in the browser on that page (and similar pages) to get your schema-shaped result. You get code back, not data. Run the code yourself, as many times as you like, with no further LLM calls.

## Why it exists
LLM extraction ([[schema-driven-extraction--from-llm-scraper]]) is durable but expensive: every scrape is an inference call with token cost and seconds of latency. If you're scraping the same page shape repeatedly (a product listing, a leaderboard, a feed), that's wasteful. Code generation flips the economics: **pay the model once to author a deterministic scraper, then execute it for free forever.** The job-to-be-done is amortizing AI cost across many runs — the LLM as a one-time code author, not a per-request worker.

## How it actually works
1. **Preprocess the page** to `html` or `raw_html` (codegen only allows these two — the model needs real DOM structure to write selectors against, not prose text or an image).
2. **Pull the JSON Schema out of the output definition.** The AI SDK has already converted the caller's Zod schema into JSON Schema; the code generator reaches into the output's `responseFormat` and grabs that schema object to show the model the target shape.
3. **Prompt the model to write runnable code.** A strict system prompt: *"Provide a scraping function in JavaScript that extracts and returns data according to a schema from the current page. The function must be IIFE. No comments or imports. No console.log. The code you generate will be executed straight away, you shouldn't output anything besides runnable code."* The user message carries three things: the website URL, the JSON schema (stringified), and the page content.
4. **Clean the response.** Models love wrapping code in ```` ```javascript ```` fences despite being told not to, so the result is run through a small `stripMarkdownBackticks` helper that trims a leading ```` ```javascript ```` / ```` ``` ```` and a trailing ```` ``` ````.
5. **Return `{ code, url }`** — a string of runnable JS (an IIFE) and the source URL.

## The non-obvious parts
- **It uses plain `generateText`, not structured output.** The other two methods constrain the model to a schema; here the *schema is just context* and the output is free text (the code). The constraint is enforced socially, by the prompt ("output nothing besides runnable code"), not by the SDK.
- **"IIFE, no imports, no console.log" is a deployment contract.** The generated code is meant to be dropped straight into `page.evaluate()` (or an eval) and return a value — so it must be a single self-executing expression with no module system and no stray output. The prompt encodes exactly the constraints of that execution environment.
- **`stripMarkdownBackticks` is a tell about LLM reality.** Even with explicit "no markdown" instructions, models fence code. Rather than fight it, the library cheaply post-processes. A small but battle-tested pattern worth copying.
- **The generated scraper is brittle in the way hand-written scrapers are** — it bakes in selectors for *this* DOM. It trades the LLM's redesign-resilience for speed/cost. The two methods are deliberate opposites; you pick per use case.
- **No execution or validation is included.** The library hands you code; running it, sandboxing it, and trusting it are your problem. Executing model-written JS is a real security surface.

## Related
- [[schema-driven-extraction--from-llm-scraper]] — the alternative cost model (inference every run, more resilient).
- [[page-format-pipeline--from-llm-scraper]] — supplies the html/raw_html context the model writes against.
- See also: [[adaptive-element-relocation--from-scrapling]] — another route to "scrape once, survive changes" without per-run LLM calls.
