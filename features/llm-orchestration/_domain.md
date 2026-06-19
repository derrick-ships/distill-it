# Domain: llm-orchestration

How LLM calls are composed, routed, streamed, and chained into larger pipelines. Covers the protocol layer that sits between raw model calls and application logic.

## What belongs here

- Pipe/chain composition protocols (LCEL, Vercel AI SDK, similar)
- Prompt template systems
- Streaming and async execution patterns
- Parallel/fan-out execution
- Conditional branching in LLM flows
- Config / tracing propagation through chains

## What does NOT belong here

- Individual model integrations → `llm-integration`
- Agent loops (tool calling cycles) → `agent-architecture`
- RAG / retrieval → `retrieval`
- Output parsing / structured extraction → `structured-extraction`

## Features in this domain

| Feature | From repo | Summary |
|---------|-----------|---------|
| [[lcel-runnable-protocol--from-langchain]] | langchain | Universal `Runnable` interface + pipe composition; LCEL |
