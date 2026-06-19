# langchain

**Source:** https://github.com/langchain-ai/langchain  
**Date distilled:** 2026-06-19  
**Description:** Python framework for building LLM-powered applications and agents. 140k stars, MIT license. Provides composable abstractions for chains, tools, retrieval, and multi-model integrations.

**Stack:** Python, Pydantic, asyncio, OpenAI / Anthropic / Gemini / Ollama (via partner packages)

---

## Distilled Features

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| LCEL / Runnable Protocol | llm-orchestration | [study](../features/llm-orchestration/study/lcel-runnable-protocol--from-langchain.md) | [build](../features/llm-orchestration/build/lcel-runnable-protocol--from-langchain.md) |
| Structured Output | structured-extraction | [study](../features/structured-extraction/study/structured-output--from-langchain.md) | [build](../features/structured-extraction/build/structured-output--from-langchain.md) |
| Tool Calling + Agent Loop | agent-architecture | [study](../features/agent-architecture/study/tool-calling-agent--from-langchain.md) | [build](../features/agent-architecture/build/tool-calling-agent--from-langchain.md) |
| RAG Pipeline | retrieval | [study](../features/retrieval/study/rag-pipeline--from-langchain.md) | [build](../features/retrieval/build/rag-pipeline--from-langchain.md) |

---

## Product fingerprint

LangChain's core bet is that every LLM primitive — prompts, models, parsers, retrievers, tools, memory — should implement a single `Runnable` interface so they compose uniformly via the `|` operator (LCEL). This makes streaming, async, batching, and observability fall out for free on any chain you assemble. The framework has evolved through two major design eras: the original `Chain` class era (v0.0.x) and the LCEL/Runnable era (v0.1+). By v1.x the older Chain classes are mostly kept for backwards compat while LCEL is the canonical path.

**Cloneability verdict:** High. The core abstractions (Runnable protocol, tool schemas, retrieval chain, structured output) are well-documented patterns that can be reimplemented in any language. The 100+ integrations are the moat, not the framework itself.
