# open-webui

**Source:** https://github.com/open-webui/open-webui
**Product:** A self-hosted, offline-capable AI platform — a feature-rich web UI for chatting with LLMs (Ollama + any OpenAI-compatible API), with RAG, web search, tools/plugins, voice, image generation, RBAC, and enterprise auth. FastAPI backend + Svelte frontend; ~100k+ stars.
**Distilled:** 2026-06-18

## What this repo actually is
A large, mature AI platform. The backend (`backend/open_webui/`) is FastAPI with ~30 routers and deep subsystems: an 11-backend pluggable vector store, a multi-provider LLM proxy (Ollama/OpenAI/Anthropic), a user-uploadable Python plugin system (pipelines/functions/tools), RBAC+SCIM, socket.io+Redis realtime, MCP client support, and the chat-completion middleware that ties it all together.

## Features distilled

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Chat-completion middleware | ai-workflow | [study](../features/ai-workflow/study/chat-completion-middleware--from-open-webui.md) | [build](../features/ai-workflow/build/chat-completion-middleware--from-open-webui.md) |

## Distill notes / gaps
- `process_chat_payload` (the PRE phase) and the tool-handler / RAG-handler heads were read **verbatim** via targeted curl ranges; the documented step order is from the source comment.
- `middleware.py` is ~5272 lines — only the key functions were read by line range, not the whole file. The POST-phase handlers (`process_chat_response`, `streaming_chat_response_handler`) were mapped by function index but not read line-by-line.
- GAPS flagged in the build doc: exact `rag_template`/citation literal strings, `functions.py` pipe execution, and filter function signatures (WebFetch returned summaries for those) — "verify before relying."

## Not yet distilled (candidates)
- **Pluggable vector-DB layer** (`retrieval/vector/factory.py` + 11 `dbs/*`) — one interface over pgvector/Qdrant/Milvus/Chroma/Pinecone/Weaviate/Elastic/etc.
- **Unified LLM routing/proxy** (`routers/ollama.py`, `openai.py`, `utils/anthropic.py`, `payload.py`) — provider-agnostic streaming with payload translation.
- **User-uploadable plugin system** (`functions.py`, `utils/plugin.py`, `filter.py`, `routers/pipelines.py`) — sandboxed user Python as filters/pipes/actions.
- **RBAC + groups + SCIM 2.0** (`utils/access_control/*`, `models/groups.py`, `routers/scim.py`).
- **Realtime chat over socket.io + Redis** (`socket/main.py`, `session_pool.py`, `utils/redis.py`).
- **Web-search aggregation** (`retrieval/web/*`, 20+ providers).
- **MCP client integration** (`utils/mcp/client.py`).
