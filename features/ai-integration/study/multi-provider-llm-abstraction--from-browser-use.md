# Multi-Provider LLM Abstraction — from [browser-use](https://github.com/browser-use/browser-use)

> Domain: [[_domain]] · Source: https://github.com/browser-use/browser-use · NotebookLM: <link once added>

## What it does

This is browser-use's home-grown layer for talking to *any* LLM provider through one identical interface. You instantiate `ChatOpenAI(...)`, `ChatAnthropic(...)`, `ChatGoogle(...)`, `ChatGroq(...)`, or their own `ChatBrowserUse(...)`, and they all expose the exact same method: `await llm.ainvoke(messages, output_format=SomeModel)`. The rest of the codebase never knows or cares which provider is behind it. Critically, it guarantees **structured output** — you hand it a Pydantic model and you get back a validated instance of that model — even though every provider implements structured output completely differently under the hood.

## Why it exists

browser-use used to depend on LangChain and deliberately ripped it out. The reason is the agent loop needs two things LangChain made awkward: rock-solid structured output (the agent's entire `AgentOutput` schema must come back parseable every single step) and precise token accounting (to manage cost and prompt caching). So they built their own thin layer: shared message types, one async method, and a per-provider adapter that knows that provider's particular quirks. It's the seam that lets a user swap models with one line and lets the agent treat "the LLM" as a single dependable component.

## How it actually works

**One shared message vocabulary.** Everything upstream builds messages as `UserMessage`, `SystemMessage`, `AssistantMessage`. Their content can be plain text or a list of parts (text parts, image parts for vision, refusal parts). There's a `cache: bool` flag on each message — a browser-use abstraction that each provider maps to its own caching mechanism. These shared types are the lingua franca; every provider adapter's first job is to translate them into that provider's native message format.

**One method, one return envelope.** The contract is a `BaseChatModel` Protocol (duck-typed, not an abstract base class — providers are plain dataclasses that just need to match the shape). Its `ainvoke(messages, output_format=None)` returns a `ChatInvokeCompletion[T]`: a small envelope holding `completion` (the result — either a string or your Pydantic instance), optional `thinking`/`redacted_thinking` (for Anthropic extended thinking), `usage` (token counts), and `stop_reason`. Token usage is its own structured object tracking prompt tokens, cached tokens, cache-creation tokens, image tokens, completion tokens, and even a pricing multiplier.

**The schema optimizer.** Given your output Pydantic model, a `SchemaOptimizer` turns it into a clean JSON schema: it inlines all `$ref`/`$defs` (so the schema is flat), strips metadata, and — for strict modes — forces every object's `required` to list all its properties and sets `additionalProperties: false`. This optimized schema is what gets handed to each provider, then adapted further per their rules.

**The per-provider differences are the whole point** — structured output is implemented three genuinely different ways:

- **OpenAI** uses native JSON-schema response format: it passes `response_format={type: json_schema, json_schema: {strict: true, schema}}` and parses `response.choices[0].message.content` back through the Pydantic model. Reasoning models (o1/o3/o4/gpt-5) get `temperature` stripped and `reasoning_effort` added.
- **Anthropic has no native structured output, so it fakes it with a tool-use trick.** The output model becomes a *tool* whose `input_schema` is the JSON schema, and `tool_choice` is forced to *that specific tool* — so Claude is compelled to emit exactly one tool call whose arguments match the schema. The code reads `block.input` (already a dict) and validates it directly. It even has to delete the schema's `title` field because Anthropic rejects it. Some Claude versions don't support forced tool choice, so there's an `auto` fallback.
- **Google Gemini** uses native `response_schema` + `response_mime_type: application/json`, but its schemas are pickier: a `_fix_gemini_schema` pass re-resolves refs, strips `additionalProperties`/`default` (unsupported), and injects a `_placeholder` property into any empty object because Gemini rejects property-less objects.

Every adapter also parses that provider's token-usage response into the shared `ChatInvokeUsage` shape — handling Anthropic's cache-read/cache-creation split, OpenAI's cached-tokens detail, and Gemini's image-token and thinking-token accounting. There's an exception hierarchy (`ModelError` → `ModelProviderError` → `ModelRateLimitError`) that the agent loop keys its provider-fallback logic on, and a lazy-loading `__init__` so importing one provider doesn't drag in every SDK.

## The non-obvious parts

- **Anthropic structured output is a tool-call in disguise.** There's no "JSON mode" — the Pydantic model is converted to a forced tool, and the tool's input *is* the structured output. This is the cleverest and least obvious adapter in the layer.
- **Anthropic chokes on a schema `title`.** The optimizer's output includes `title`; the Anthropic adapter must explicitly `del schema['title']` or the API rejects it. OpenAI and Google don't care.
- **Gemini rejects empty objects.** Any object node with no properties gets a synthetic `_placeholder: string` injected, purely to satisfy the API.
- **It's a Protocol, not a base class.** Providers are dataclasses checked by duck typing; there's no enforced inheritance, no `super()` to call. The schema-optimization step is invoked *inside* each `ainvoke`, not by shared base machinery — so each adapter is fully self-contained.
- **`create_gemini_optimized_schema` is, in practice, identical to the generic optimizer** — the differentiation is documentary; the real Gemini-specific fixing happens later in `_fix_gemini_schema`.
- **`ChatBrowserUse` is a meta-provider** that accepts provider-prefixed model IDs (`anthropic/claude-…`, `openai/gpt-…`) and resolves them server-side — the only adapter that ships the schema as a raw payload for the server to enforce.
- **`ChatOpenAILike`** is a thin subclass that turns "any OpenAI-compatible endpoint" (Groq, DeepSeek, Ollama, …) into a provider for free.

## Related
- [[agent-loop-recovery--from-browser-use]] — calls `ainvoke(messages, output_format=AgentOutput)` every step and switches to a fallback provider on `ModelRateLimitError`/`ModelProviderError`.
- [[action-tool-registry--from-browser-use]] — produces the Pydantic union that becomes the `output_format` passed here.
- See also: [[provider-agnostic-llm--from-llm-scraper]] (the same "one interface, many providers" goal, but solved by *adopting* the Vercel AI SDK rather than hand-rolling) — a sharp contrast in build-vs-buy. Also [[citation-grounded-chat--from-openpaper]] for another structured-LLM integration.
