# LCEL / Runnable Protocol (build spec) — distilled from langchain

## Summary

Implement the `Runnable[Input, Output]` composition protocol: a universal interface for LLM pipeline components that supports pipe-based composition (`|` operator), sync/async/batch/stream execution modes, and transparent callback propagation. The key deliverable is a `RunnableSequence` that lets you chain arbitrary steps into a pipeline where every execution mode works uniformly.

## Core logic (inlined)

### The Runnable interface

```python
from abc import ABC, abstractmethod
from typing import Any, Iterator, AsyncIterator

class Runnable(ABC):
    @abstractmethod
    def invoke(self, input: Any, config: dict | None = None) -> Any:
        """Synchronous single-input execution."""
        ...

    async def ainvoke(self, input: Any, config: dict | None = None) -> Any:
        """Async; defaults to running invoke in a thread pool."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.invoke, input, config)

    def batch(self, inputs: list, config=None, *, return_exceptions=False) -> list:
        """Parallel batch via ThreadPoolExecutor."""
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor() as ex:
            futures = [ex.submit(self.invoke, inp, config) for inp in inputs]
            results = []
            for f in futures:
                try:
                    results.append(f.result())
                except Exception as e:
                    if return_exceptions:
                        results.append(e)
                    else:
                        raise
        return results

    def stream(self, input: Any, config=None) -> Iterator:
        """Default: invoke once, yield result. Override for true streaming."""
        yield self.invoke(input, config)

    def __or__(self, other: "Runnable") -> "RunnableSequence":
        if isinstance(self, RunnableSequence):
            return RunnableSequence(steps=[*self.steps, other])
        return RunnableSequence(steps=[self, other])

    def __ror__(self, other) -> "RunnableSequence":
        if isinstance(other, dict):
            other = RunnableParallel(other)
        return RunnableSequence(steps=[other, self])
```

### RunnableSequence

```python
class RunnableSequence(Runnable):
    def __init__(self, steps: list[Runnable]):
        self.steps = steps

    def invoke(self, input, config=None):
        result = input
        for step in self.steps:
            result = step.invoke(result, config)
        return result

    def stream(self, input, config=None) -> Iterator:
        # Stream by passing chunks through each step
        # Steps that don't override stream() just buffer and yield once
        it = iter([input])
        for step in self.steps:
            it = step._transform(it, config)
        yield from it

    async def ainvoke(self, input, config=None):
        result = input
        for step in self.steps:
            result = await step.ainvoke(result, config)
        return result
```

### RunnableLambda

```python
import inspect

class RunnableLambda(Runnable):
    def __init__(self, func):
        self.func = func
        self._is_async = inspect.iscoroutinefunction(func)

    def invoke(self, input, config=None):
        if self._is_async:
            import asyncio
            return asyncio.get_event_loop().run_until_complete(self.func(input))
        return self.func(input)

    async def ainvoke(self, input, config=None):
        if self._is_async:
            return await self.func(input)
        return self.func(input)
```

### RunnableParallel

```python
class RunnableParallel(Runnable):
    def __init__(self, steps: dict[str, Runnable]):
        self.steps = steps

    def invoke(self, input, config=None) -> dict:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor() as ex:
            futures = {k: ex.submit(v.invoke, input, config)
                      for k, v in self.steps.items()}
        return {k: f.result() for k, f in futures.items()}

    async def ainvoke(self, input, config=None) -> dict:
        import asyncio
        results = await asyncio.gather(
            *[v.ainvoke(input, config) for v in self.steps.values()]
        )
        return dict(zip(self.steps.keys(), results))
```

### RunnablePassthrough

```python
class RunnablePassthrough(Runnable):
    def invoke(self, input, config=None):
        return input

    @classmethod
    def assign(cls, **kwargs: Runnable) -> "RunnableSequence":
        """Extend a dict input with computed fields."""
        def merge(input_dict):
            extra = {k: v.invoke(input_dict) for k, v in kwargs.items()}
            return {**input_dict, **extra}
        return RunnableSequence(steps=[cls(), RunnableLambda(merge)])
```

### Dict shortcut (auto-wrap in RunnableParallel)

LangChain auto-wraps plain dicts in the `|` operator:

```python
# Intercept dict.__or__ by wrapping in the sequence creation
def _coerce(obj) -> Runnable:
    if isinstance(obj, dict):
        return RunnableParallel({k: _coerce(v) for k, v in obj.items()})
    if callable(obj) and not isinstance(obj, Runnable):
        return RunnableLambda(obj)
    return obj
```

## Data contracts

### RunnableConfig

```python
RunnableConfig = {
    "tags": list[str],             # filter logs/traces by tag
    "metadata": dict[str, Any],    # arbitrary key-value for tracing
    "callbacks": list[BaseCallback] | None,  # LangSmith, custom handlers
    "run_name": str | None,        # display name in traces
    "max_concurrency": int | None, # cap parallel batch workers
    "recursion_limit": int,        # prevent infinite chain recursion (default 25)
}
```

### StreamEvent (from astream_events)

```python
StreamEvent = {
    "event": "on_chain_start" | "on_chain_end" | "on_llm_start" | "on_llm_stream" | ...,
    "name": str,        # component name
    "run_id": str,      # UUID for this specific run
    "tags": list[str],
    "data": {
        "input": Any | None,   # present on _start events
        "output": Any | None,  # present on _end events
        "chunk": Any | None,   # present on _stream events
    }
}
```

## Dependencies & assumptions

- **Python 3.10+** for `match` statement support (optional; LangChain also supports 3.9)
- **asyncio** for async execution; `ThreadPoolExecutor` from `concurrent.futures` for sync batch
- No external dependencies for the core protocol; actual LLM calls need provider packages
- LangChain uses `pydantic` for `input_schema`/`output_schema` generation (optional; skip if you don't need schema introspection)

## To port this, you need:

- [ ] Define the `Runnable` abstract base class with `invoke`, `ainvoke`, `batch`, `stream`
- [ ] Implement `__or__` on `Runnable` to create `RunnableSequence`
- [ ] Implement `RunnableSequence` with sequential invocation and streaming passthrough
- [ ] Implement `RunnableLambda` to wrap arbitrary functions
- [ ] Implement `RunnableParallel` for dict-fan-out patterns
- [ ] Implement `RunnablePassthrough` with `assign()` class method
- [ ] Add dict coercion in the `|` operator (auto-wrap dicts in `RunnableParallel`)
- [ ] Implement `RunnableConfig` propagation through all methods
- [ ] (Optional) Implement `astream_events` for structured streaming observability

## Gotchas

**Stream fallback is silent.** If a step doesn't override `stream()`, the base implementation calls `invoke()` and yields once. You don't get an error — you just don't get streaming. Add a `_supports_streaming: bool` flag if you need to detect this.

**Dict-as-branch shortcut is magic.** `{"context": retriever, "question": passthrough} | prompt` only works if your `__or__` coerces dicts. Without this, users have to explicitly write `RunnableParallel(...)`. Both work; the dict shorthand is just ergonomics.

**Async default fallback uses threads.** The default `ainvoke` runs `invoke` in a thread pool. This means sync blocking code inside a `Runnable` is safe to call from async context but won't use cooperative scheduling. If the LLM call itself is async (most SDKs have async clients), override `ainvoke` properly.

**RunnableSequence flattening.** When you chain `(a | b) | c`, you want `[a, b, c]` not `[[a, b], c]`. Implement `__or__` to check `isinstance(self, RunnableSequence)` and extend `steps` rather than nest.

**Config propagation**: `config` must be threaded through every `invoke` call in the chain, not just the outermost one. Callbacks won't fire on inner steps if you forget this.

**Concurrency limits**: the `max_concurrency` config key caps the thread pool size in `batch()`. Without this, a batch of 1000 items spins up 1000 threads and likely OOMs or gets rate-limited.

## Origin (reference only)

- Repo: https://github.com/langchain-ai/langchain
- Core file: `libs/core/langchain_core/runnables/base.py`
- Runnable types: `libs/core/langchain_core/runnables/passthrough.py`, `branch.py`, `fallbacks.py`
