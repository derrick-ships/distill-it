# Chat-Completion Middleware — from [open-webui](https://github.com/open-webui/open-webui)

> Domain: [[_domain]] · Source: https://github.com/open-webui/open-webui · NotebookLM: <add link>

## What it does
It's the assembly line that turns a raw chat request into a finished, streamed answer. Between "user hit send" and "model starts talking," a lot has to happen: run any user-installed filters, pull in relevant memories, do a web search or RAG over attached files, wire up tools (including external MCP servers), inject custom "skills," handle image generation and a code interpreter — then call the model, stream the tokens back, and afterward run output filters and fire off background jobs (auto-title, tags, follow-up suggestions). This middleware orchestrates all of it in a fixed, deliberate order.

## Why it exists
Open WebUI supports an enormous matrix of capabilities (RAG, tools, memory, web search, code execution, multiple providers, user plugins, MCP). If each were bolted on ad hoc, you'd get chaos. The job-to-be-done is "have one well-ordered pipeline that every chat completion flows through, where each capability is a clearly-scoped step that mutates a shared request payload, and where the same code path works whether the model does native function-calling or not." It's the connective tissue that makes all the other subsystems compose.

## How it actually works
The whole thing is two big async functions in `utils/middleware.py`: `process_chat_payload` (everything *before* the model) and `process_chat_response` (everything *after*). A request is a `form_data` dict that gets progressively mutated.

**The PRE phase (`process_chat_payload`) runs in this exact order** (it's even written as a comment in the code):
`Pipeline Inlet → Filter Inlet → Chat Memory → Chat Web Search → Chat Image Generation → Chat Code Interpreter → (Default) Chat Tools Function Calling → Chat Files`

Before that order even begins, it: resolves "arena" models (picks a random sub-model), reloads the conversation from the DB (the DB keeps structured tool-call `output` items the frontend strips), applies system-prompt variable substitution, converts image URLs to base64, and builds an `extra_params` bundle (`__event_emitter__`, `__event_call__`, `__user__`, `__metadata__`, `__request__`, `__model__`, etc.) that's threaded into every plugin call. It folds in model "knowledge" collections and folder/"project" files+system-prompts.

**The big fork: native vs. prompt-based.** If the model/request uses *native* function-calling (`params.function_calling == 'native'`), the forced injections are *skipped* — memory, web search, image gen, code-interpreter prompts, and RAG are not stuffed into the prompt. Instead those become **builtin tools** the model can call itself. Otherwise (non-native), each capability is injected the old-fashioned way: memory/search results and a code-interpreter instruction get written into the system/user messages, and `chat_completion_tools_handler` makes a *separate* call to a "task model" that decides which tools to call from the recent chat history, runs them, and folds the results in as context.

**Tools come from everywhere and get merged into one `tools_dict`:** server-side tools (`get_tools`), MCP servers (a `server:mcp:` tool id triggers `connect_mcp_server`, and each remote tool is wrapped as a callable), terminal tools, client-supplied "direct" tool servers, and builtin tools. For native FC they're emitted as OpenAI `{type:"function", function:…}` specs; for non-native they're executed by the handler.

**Skills** are a neat touch: `<$skillId|label>` mention tags in the message are parsed out; user-selected skills inject their *full* content into the system message, while model-attached skills inject only name+description (so the model can ask for them).

**The POST phase (`process_chat_response`)** routes to `streaming_chat_response_handler` or `non_streaming_chat_response_handler`, then runs `outlet_filter_handler` (output filters) and `background_tasks_handler` (auto-title, tags, follow-up generation). Everything streams to the client through the event-emitter system.

## The non-obvious parts
- **The order is load-bearing and explicit.** Memory before search before image-gen before code-interpreter before tools before files. That comment-as-spec is the single most useful thing to copy.
- **Native-FC short-circuits half the pipeline.** The same request takes a very different path depending on one flag: prompt-stuffing vs. exposing builtin tools. Nearly every injection step has an `if function_calling != 'native'` guard. Miss this and you'd double-inject.
- **It reloads messages from the DB, not the client.** Frontends strip structured tool-call `output` items, which would corrupt multi-turn tool use — so the server trusts its own stored copy.
- **Non-native tool calling uses a *second, separate* model call.** A "task model" is asked (non-streaming) to pick tools from the last ~4 messages; it's a mini-agent step before the real completion. Native FC skips this entirely.
- **MCP tools are first-class.** A tool id prefixed `server:mcp:` connects to an external MCP server and each of its tools becomes a callable merged into the same `tools_dict` as everything else — MCP, builtins, and user tools are indistinguishable downstream.
- **`extra_params` is the dependency-injection vehicle.** Plugins/filters/tools receive request, user, model, metadata, and event emitters by name (`__event_emitter__`, etc.), discovered via signature introspection — so each plugin only declares the params it wants.
- **Citations/sources are tracked as a side-channel.** RAG and tool results accumulate `sources` that get attached to messages for inline citations rather than just dumped into the prompt.

## Related
- [[scraper-code-generation--from-llm-scraper]] / [[multi-source-research-engine--from-last30days-skill]] — adjacent retrieval/agentic flows.
- [[sandboxed-agent-tool-suite--from-devspace]] — a tool-suite design this middleware's tool layer resembles.
- See also: [[agentic-loop--from-open-design]], [[agent-cli-integration--from-open-design]] — other ai-workflow orchestration patterns.
