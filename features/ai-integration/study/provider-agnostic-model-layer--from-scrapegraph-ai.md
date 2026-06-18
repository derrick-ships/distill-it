# Provider-Agnostic Model Layer — from [scrapegraph-ai](https://github.com/ScrapeGraphAI/Scrapegraph-ai)

> Domain: [[_domain]] · Source: https://github.com/ScrapeGraphAI/Scrapegraph-ai · NotebookLM: <add link>

## What it does
This is the bit that lets you write `{"llm": {"model": "openai/gpt-4o"}}` — or `"ollama/llama3"`, or `"anthropic/claude-3-5-sonnet"`, or twenty others — and have the library build the right client for you. You give it a model string and maybe some params; it returns a ready-to-use chat model and, crucially, figures out that model's **maximum input token count**, which the rest of the pipeline uses to decide how to chunk pages. One config knob, any of ~19 providers, plus local models.

## Why it exists
A scraping library that's married to one LLM vendor is a liability — prices change, a better model ships elsewhere, some users must run locally for privacy. The job-to-be-done is **make the model a swappable input, not a hardcoded dependency**, so the same pipeline runs on OpenAI today and a local Ollama model tomorrow with a one-line config change. The second, sneakier job is **knowing each model's context size**, because the whole chunk-and-merge extraction strategy is sized to it. Get the token limit wrong and you either waste context or overflow it.

## How it actually works
It centers on one method, `_create_llm(llm_config)`, that runs a small decision tree:

1. **Escape hatch — bring your own instance.** If the config contains a `model_instance`, it's used directly (you must also supply `model_tokens` so chunking still works). Total flexibility for unusual setups.

2. **Parse the provider from the model string.** If the string has a slash (`"openai/gpt-4o"`), the part before the slash is the provider and the part after is the model. If there's *no* slash, it searches a big built-in table (`models_tokens`) for any provider that lists that model name and uses the first match — with a logged warning that you should really specify the provider.

3. **Validate the provider** against a hardcoded set of ~19 known providers (openai, azure_openai, google_genai, google_vertexai, ollama, anthropic, bedrock, mistralai, groq, deepseek, fireworks, togetherai, xai, minimax, nvidia, hugging_face, ernie, oneapi, clod). Unknown → raise with a hint to pass a `model_instance` instead.

4. **Resolve the token limit.** If you passed `model_tokens`, use it. Otherwise look up `models_tokens[provider][model]`. If even that misses, warn and default to 8192. This number becomes `self.model_token` — the chunk size for the whole pipeline.

5. **Build the client.** Most providers go through LangChain's `init_chat_model(**params)` — a single factory that knows how to build any standard provider's client. A handful of providers that LangChain doesn't cover (or covers differently) are special-cased to the library's own thin wrapper classes (DeepSeek, MiniMax, XAI, OneApi, Nvidia, CLoD) or community classes (ErnieBotChat, ChatTogether). Bedrock gets its temperature moved into `model_kwargs` because its API wants it there.

There's also an optional **rate limiter**: pass `rate_limit: {requests_per_second, max_retries}` and it wires LangChain's `InMemoryRateLimiter` into the client — important because the map-reduce node fires many calls at once.

## The non-obvious parts
- **The model string carries the provider.** `"<provider>/<model>"` is the whole UX. It's parsed, not configured separately. Slashless strings trigger a fuzzy lookup that's convenient but ambiguous (same model name under two providers → first wins), hence the warning.
- **Token limit resolution is load-bearing for correctness, not just a nicety.** Because chunking is sized to `model_token`, a wrong or defaulted value silently degrades extraction (over-chunking wastes calls; under-chunking overflows). The 8192 fallback is a safety net, not a good answer.
- **Two construction paths: factory vs. bespoke.** The clean majority go through `init_chat_model`; the messy minority get hand-written classes. This is the honest reality of "support every provider" — the abstraction is leaky at the edges, and the code just absorbs that with `if provider == ...` branches.
- **`model_instance` is the universal escape hatch.** Anything the registry can't express, you bypass by handing in a pre-built client. The price is you must self-declare `model_tokens`.
- **Rate limiting lives here, not in the nodes.** Because the layer owns client construction, it's the natural place to inject a rate limiter that every node-call then respects — a single chokepoint for the whole pipeline's API pressure.
- **Provider support is a maintenance treadmill.** Nineteen providers plus a token table for hundreds of model names means this file is where the library spends a lot of its upkeep. The design contains the churn to one method.

## Related
- [[smart-scraper-pipeline--from-scrapegraph-ai]] — calls `_create_llm` in its base class and uses `model_token` to size Parse.
- [[map-reduce-answer-generation--from-scrapegraph-ai]] — its parallel calls are why the rate limiter matters; its provider branches mirror the special-casing here.
- [[graph-execution-engine--from-scrapegraph-ai]] — the per-node token/cost accounting reads model metadata set up here.
- See also: [[provider-agnostic-llm--from-llm-scraper]] — the same goal solved by depending on the Vercel AI SDK's abstraction instead of a per-provider registry (abstract *above* the vendor vs. enumerate vendors). And [[ai-lead-classification--from-auto-crm]] — the opposite stance: bind to one vendor but make the whole AI path optional.
