# LCEL / Runnable Protocol — from [langchain](https://github.com/langchain-ai/langchain)

> Domain: [[_domain]] · Source: https://github.com/langchain-ai/langchain · NotebookLM:

## What it does

LCEL (LangChain Expression Language) is the composition protocol at the heart of LangChain. It lets you connect any two LLM building blocks — a prompt, a model, an output parser, a retriever — using a single `|` pipe operator, the same way you'd pipe Unix commands. The result is a chain that automatically supports streaming, async execution, batching, and observability without you writing any boilerplate.

## Why it exists

Before LCEL, LangChain had a zoo of `Chain` subclasses (`LLMChain`, `RetrievalQAChain`, `ConversationalRetrievalChain`, etc.). Each one hard-coded its behavior — streaming didn't work through them uniformly, async was bolted on, and composing two chains together required creating yet another Chain subclass. LCEL replaces all of that by making the composition the primitive. If two things implement `Runnable`, they compose. Full stop.

The job-to-be-done: let a developer assemble `prompt | model | parser` in one line and get production-grade streaming, async, and tracing for free.

## How it actually works

Every component in LangChain implements the `Runnable[Input, Output]` interface. The interface has exactly four execution modes:

1. **invoke** — sync, one input → one output
2. **ainvoke** — async version (defaults to running invoke in a thread pool if not overridden)
3. **batch** — list of inputs → list of outputs; parallelizes using a thread executor (sync) or `asyncio.gather` (async)
4. **stream** / **astream** — yields partial outputs as they arrive; if the underlying component doesn't support native streaming, it falls back to invoking once and yielding the full result

When you write `prompt | model | parser`, Python calls `prompt.__or__(model)` which creates a `RunnableSequence([prompt, model])`. Then `RunnableSequence.__or__(parser)` extends the steps list to `[prompt, model, parser]`. The sequence is flat — no nesting.

When the sequence is invoked, each step's output feeds the next step's input as if you called them in a for loop. For streaming, each step forwards chunks as they arrive to the next step, so token-by-token output from the model flows all the way through to the caller without buffering.

There are four key built-in Runnable types beyond `RunnableSequence`:

- **RunnableLambda** — wraps any Python function so it can sit in a chain. `RunnableLambda(str.upper)` is a valid chain step.
- **RunnableParallel** — takes a dict of runnables and runs them all on the same input simultaneously, returning a dict of results. `{"context": retriever, "question": RunnablePassthrough()}` is a common RAG pattern.
- **RunnablePassthrough** — passes input through unchanged. Used to keep the original question alive while a parallel branch retrieves documents.
- **RunnableBranch** — routes input to different sub-chains based on a condition, like a switch statement.

The `RunnableConfig` object threads through every call carrying: tags (for filtering logs), metadata (arbitrary key-value for tracing), callbacks (for LangSmith / custom event handlers), and concurrency limits. You never have to pass this manually — the framework forwards it automatically through every step in a chain.

Event streaming via `astream_events()` goes one level deeper: instead of yielding the final output, it yields a structured event dict `{event, name, data, run_id, tags}` for every step as it starts and ends. This is how LangSmith instruments chains for the trace UI — each node in the trace corresponds to one `on_chain_start` / `on_chain_end` event pair.

## The non-obvious parts

**Flattening**: `RunnableSequence.__or__` checks if the left side is already a `RunnableSequence`, and if so, extends its steps rather than nesting sequences inside sequences. This matters because a deeply nested structure would be harder to inspect and slower to traverse.

**Stream fallback is silent**: if you compose a step that doesn't override `stream()`, it still works — but it won't actually stream. You get a single-element iterator. This can surprise you if you expect token-by-token output from a custom component.

**The `|` shortcut works on dicts too**: you can write `{"context": retriever, "question": RunnablePassthrough()} | prompt` because LangChain auto-wraps plain dicts in `RunnableParallel`. This is purely syntactic sugar but it's used everywhere in the docs.

**`assign()` adds fields without dropping others**: `RunnablePassthrough.assign(context=retriever | format_docs)` returns a new dict with all existing keys plus `context`. This is how you build up the input dict for a prompt without losing earlier values.

**No schema enforcement by default**: the `input_schema` and `output_schema` properties exist for introspection, but they're not enforced at runtime unless you explicitly validate. Chains are duck-typed at the boundary.

**Thread pools for sync batch**: `batch()` uses a `ThreadPoolExecutor`, which means it's subject to Python's GIL. For CPU-bound tasks that doesn't help. For I/O-bound LLM calls (which are all network calls) it works well.

## Related

- [[rag-pipeline--from-langchain]] (retriever is a Runnable; RAG chains are built with LCEL pipes)
- [[tool-calling-agent--from-langchain]] (agents use LCEL to wire the model + tool executor)
- [[structured-output--from-langchain]] (with_structured_output returns an LCEL chain)
- [[schema-driven-extraction--from-llm-scraper]] (Vercel AI SDK does a similar structured output thing in JS)
