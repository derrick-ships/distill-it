# Schema-Driven Extraction — from [llm-scraper](https://github.com/mishushakov/llm-scraper)

> Domain: [[_domain]] · Source: https://github.com/mishushakov/llm-scraper · NotebookLM: <add link>

## What it does
You hand it a live web page (already opened in a Playwright browser) and a description of the *shape* of data you want — for example, "an array of exactly 5 stories, each with a title, a points number, an author, and a comments URL." It hands back a real, typed object in that exact shape, populated from whatever was on the page. No CSS selectors, no XPath, no brittle DOM walking. The LLM reads the page and fills in your schema.

## Why it exists
Traditional scraping breaks every time a site changes its markup — you wrote `.story-title > a` and the site renamed the class. The job-to-be-done here is **scraping that survives redesigns**: describe the data you want by meaning, not by markup location, and let a model that "understands" the page do the mapping. The payoff is durability and near-zero per-site code. The cost is tokens and latency per scrape, which is why the same library also offers code-generation (see [[scraper-code-generation--from-llm-scraper]]) to amortize that cost.

## How it actually works
Three steps, every time:

1. **Preprocess the page into text the model can read.** The raw page is huge and full of noise (scripts, styling, SVGs). A preprocessing step (its own feature — [[page-format-pipeline--from-llm-scraper]]) reduces the page to one of several formats: cleaned HTML, markdown, readable article text, or even a screenshot image. This is what actually gets sent to the model.

2. **Ask the model to fill the schema.** The preprocessed content becomes a user message. A short system prompt — literally "You are a sophisticated web scraper. Extract the contents of the webpage" — sets the role. Critically, the schema itself is passed to the AI SDK as a *structured-output constraint*, so the model isn't asked politely to return JSON; the SDK forces the response to conform to the schema and parses it for you.

3. **Return the typed object plus the source URL.** The result comes back as `{ data, url }`, where `data` already matches the caller's schema type. In TypeScript the caller gets full type inference — if the schema says `points` is a number, `data.top[0].points` is typed as a number.

The whole public surface is one method, `run(page, output, options)`, on an `LLMScraper` class you construct with a single LLM client. That's the entire ceremony.

## The non-obvious parts
- **The schema does double duty.** It's both the compile-time TypeScript type *and* the runtime constraint sent to the model. One declaration, both guarantees. This is the core elegance.
- **It rides the AI SDK's structured-output feature, not a hand-rolled JSON parser.** This version calls the AI SDK's `generateText` with an `output` argument and reads `result.output` — i.e. it leans on the SDK's own structured-output machinery rather than `generateObject`. That means the SDK handles the provider-specific quirks of forcing JSON (tool-calling on some providers, JSON mode on others).
- **Format choice is a quality/cost dial, not a detail.** Sending a screenshot (`image` format) invokes a vision model and costs more but survives anti-scraping HTML obfuscation; sending cleaned text is cheap but loses layout. The caller picks per call.
- **No retry or validation-repair loop.** If the model returns something the schema rejects, that surfaces as an SDK error — there's no built-in "try again, you got it wrong" loop. Simplicity over robustness.

## Related
- [[streaming-partial-objects--from-llm-scraper]] — same loop, but streams partial objects instead of waiting for the whole thing.
- [[page-format-pipeline--from-llm-scraper]] — the preprocessing step this depends on.
- [[scraper-code-generation--from-llm-scraper]] — the cost-amortizing alternative: generate a reusable scraper once instead of paying per scrape.
- [[provider-agnostic-llm--from-llm-scraper]] — why any of OpenAI/Anthropic/Google/Groq/Ollama can be dropped in.
- See also: [[adaptive-element-relocation--from-scrapling]] — a *non-LLM* answer to the same "selectors break" problem (re-find elements by fingerprint similarity).
