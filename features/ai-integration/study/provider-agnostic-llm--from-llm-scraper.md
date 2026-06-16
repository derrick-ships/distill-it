# Provider-Agnostic LLM Layer — from [llm-scraper](https://github.com/mishushakov/llm-scraper)

> Domain: [[_domain]] · Source: https://github.com/mishushakov/llm-scraper · NotebookLM: <add link>

## What it does
Lets the whole scraper work with any major LLM provider — OpenAI, Anthropic, Google, Groq, Ollama (local) — without changing a line of the scraping logic. You construct the scraper with one "model" object from whichever provider you like, and everything (extraction, streaming, code generation) just works against it.

## Why it exists
LLM providers differ in price, quality, speed, privacy, and availability. Locking a tool to one provider is a liability: prices change, a model gets deprecated, a user needs local/offline (Ollama) for privacy, or wants the cheapest model that passes. The job-to-be-done is **provider optionality** — make the model a swappable input so the user picks per cost/quality/privacy without forking the code.

## How it actually works
The trick is that llm-scraper doesn't talk to providers itself — it delegates entirely to the **Vercel AI SDK**, which already normalizes every provider behind one `LanguageModel` interface. The scraper:

1. **Takes a `LanguageModel` in its constructor** and stores it. That's the only provider-aware surface — and it's just a typed handle, not provider-specific code.
2. **Passes that model straight to the AI SDK calls** (`generateText`, `streamText`) in all three methods. The SDK handles the provider-specific HTTP, auth, JSON-mode quirks, and response parsing.
3. **Stays totally ignorant of which provider it is.** OpenAI vs Anthropic vs Ollama is decided entirely outside the library, when the caller builds the model object (e.g. `openai('gpt-4o')`, `anthropic('claude-...')`, `ollama('llama3')`).

So "multi-provider support" isn't really a feature llm-scraper *implements* — it's a feature it *inherits*, for free, by choosing to depend on the AI SDK abstraction instead of a raw provider client. That architectural choice is the actual lesson.

## The non-obvious parts
- **The moat is the dependency, not the code.** By building on the AI SDK's `LanguageModel` type, llm-scraper gets every provider the SDK supports — present and future — with zero per-provider code. The design insight: pick your abstraction layer one level up from the vendor.
- **Structured-output portability comes along for the ride.** Different providers force JSON differently (tool-calling, JSON mode, grammar). The SDK hides that, so the scraper's schema-driven extraction works uniformly even though the underlying mechanism differs per provider.
- **Local models (Ollama) are first-class**, which matters for privacy-sensitive scraping — you can extract from internal pages without sending content to a third-party API, just by swapping the model object.
- **Cost/quality tuning is a caller concern**, fully decoupled: same scraper, cheap model for easy pages, strong model for hard ones, chosen at construction time.

## Related
- [[schema-driven-extraction--from-llm-scraper]], [[streaming-partial-objects--from-llm-scraper]], [[scraper-code-generation--from-llm-scraper]] — all three ride this layer.
- See also: [[azure-doc-intelligence--from-markitdown]] — a contrasting choice: binding directly to one vendor's specialized API for a capability the generic layer can't give.
