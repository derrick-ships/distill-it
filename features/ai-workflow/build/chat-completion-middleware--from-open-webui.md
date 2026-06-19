# Chat-Completion Middleware (build spec) — distilled from open-webui

## Summary
A single ordered async pipeline every chat completion flows through. `process_chat_payload` mutates a shared `form_data` dict in a fixed sequence (filters → memory → web search → image gen → code interpreter → tools → files), then the model is called and streamed, then `process_chat_response` runs output filters + background tasks (title/tags/follow-ups). A central design fork: **native function-calling** exposes capabilities as tool specs the model calls itself, while **non-native** stuffs results into the prompt and uses a separate "task model" call to choose tools. Tools from server-side defs, MCP servers, terminals, client "direct" servers, and builtins all merge into one `tools_dict`. Python/FastAPI, async, SSE streaming via an event-emitter system.

## Core logic (inlined)

### PRE phase — `process_chat_payload(request, form_data, user, metadata, model)` (utils/middleware.py)
```
# Documented order (verbatim comment):
# Pipeline Inlet -> Filter Inlet -> Chat Memory -> Chat Web Search -> Chat Image Generation
# -> Chat Code Interpreter (Form Data Update) -> (Default) Chat Tools Function Calling -> Chat Files

1. Arena model resolution: if model.owned_by=='arena', pick random sub-model id; rewrite form_data['model'].
2. apply_params_to_form_data(form_data, model)         # temperature/top_p/etc from model config
3. regeneration_prompt = form_data.pop('regeneration_prompt', None)   # guided regen, extracted pre-LLM
4. DB message reload (if chat_id & user_message_id, non local:/channel:):
     db_messages = load_messages_from_db(chat_id, user_message_id)   # DB keeps structured 'output' items
     append assistant message (continue), prepend system message, inline image files as image_url parts,
     strip 'files' field from messages
5. process_messages_with_output(messages, reasoning_format=get_reasoning_format(model))
6. apply_system_prompt_to_body(system_message.content, ... replace=True)   # system-prompt variables
7. convert_url_images_to_base64(form_data, user)
8. extra_params = { __event_emitter__, __event_call__, __user__, __metadata__,
                    __oauth_token__, __request__, __model__, __chat_id__, __message_id__ }
9. task_model_id = get_task_model_id(form_data['model'], config.TASK_MODEL, config.TASK_MODEL_EXTERNAL, models)
10. Folder/"project" handling: inject folder system_prompt + accessible folder files (or metadata['folder_knowledge'] if native FC)
11. Model "knowledge": if model_knowledge and not native FC -> append knowledge collections to form_data['files']
12. process_pipeline_inlet_filter(request, form_data, user, models)        # PIPELINE INLET
13. filter_ids = get_sorted_filter_ids(request, model, metadata['filter_ids'])    # FILTER INLET
    form_data, flags = process_filter_functions(filter_functions, 'inlet', form_data, extra_params)
14. features = form_data.pop('features', {}); for each enabled feature, IF function_calling != 'native':
      voice  -> add_or_update_system_message(VOICE_MODE_PROMPT)
      memory -> form_data = chat_memory_handler(request, form_data, extra_params, user)
      web_search -> form_data = chat_web_search_handler(...)
      image_generation -> form_data = chat_image_generation_handler(...)
      code_interpreter -> add_or_update_user_message(CODE_INTERPRETER_PROMPT [+ PYODIDE_PROMPT])
    (native FC: skip all the above; builtins injected as tools below)
15. Skills: parse <$skillId|label> tags; user-selected -> inject <skill>{full content}</skill> into system msg;
    model-attached -> inject <available_skills> name+description only; strip_skill_mentions(messages)
16. files = form_data.pop('files'); resolve folder entries -> accessible files; dedupe
    metadata = {**metadata, model_id, tool_ids, terminal_id, files}; form_data['metadata']=metadata
17. TOOLS (only if caller didn't pass explicit 'tools'):
      tools_dict = {}
      for tool_id in tool_ids:
        if tool_id.startswith('server:mcp:'):
           client, specs = connect_mcp_server(request, server_id, user, metadata, extra_params)
           for spec: wrap as async callable -> mcp_tools_dict[f'{server_id}_{name}'] = {spec, callable, type:'mcp', client}
      tools_dict = get_tools(request, tool_ids, user, {**extra_params, __model__, __messages__, __files__})
      tools_dict |= mcp_tools_dict
      terminal tools (get_terminal_tools) if terminal_id & capability
      direct_tool_servers -> tools_dict[name] = {spec, direct:True, server}
      if native FC and builtin_tools_enabled:
         messages = add_file_context(messages, chat_id, user)
         builtin_tools = get_builtin_tools(request, {**extra_params, __skill_ids__}, features, model)
         merge builtins into tools_dict
      metadata['tools'] = tools_dict
      if native FC:  form_data['tools'] = [{'type':'function','function': t['spec']} for t in tools_dict.values()] (+ inlet_filter_tools)
      else:          form_data, flags = chat_completion_tools_handler(request, form_data, extra_params, user, models, tools_dict)
                     sources.extend(flags['sources'])
18. CHAT FILES (RAG): if file_context_enabled: chat_completion_files_handler(...) -> sources
19. return form_data, metadata, events, sources  (approx — assembles context for the model call)
```

### Non-native tool selection — `chat_completion_tools_handler(request, body, extra_params, user, models, tools)`
```
# Builds a SEPARATE task-model call to choose tool calls from recent history:
get_tools_function_calling_payload(messages, task_model_id, content):
    recent = messages[-4:]   # last 4 turns
    chat_history = "\n".join(f'{role.upper()}: """{content}"""' for m in recent)
    prompt = f"History:\n{chat_history}\nQuery: {user_message}"
    return { model: task_model_id, messages:[{system: tool-selection content},{user: prompt}],
             stream: False, metadata:{task: FUNCTION_CALLING} }
# Then runs the selected tools, collects results + 'sources' (citations), folds into form_data.
```

### POST phase — `process_chat_response(response, ctx)`
```
-> streaming_chat_response_handler(response, ctx)  OR  non_streaming_chat_response_handler(response, ctx)
   (handles SSE token stream, tool-call streaming via _render_openai_tool_call_handler / serialize_output,
    process_tool_result + get_citation_source_from_tool_result for citations)
-> outlet_filter_handler(ctx)        # FILTER OUTLET: process_filter_functions(..., 'outlet', ...)
-> background_tasks_handler(ctx)     # auto title / tags / follow-up generation (uses task model)
```

### Filters (utils/filter.py)
```
get_sorted_filter_ids(): union(global filter ids, model filter ids), keep active (toggle attr),
   sort by priority from valve config.
process_filter_functions(filter_functions, filter_type ['inlet'|'outlet'|'stream'], form_data, extra_params):
   for each: load module, get method == filter_type, inspect.signature() -> build kwargs from extra_params
   + valves/user-valves, call sync/async, replace form_data/response with return value.
```

## Data contracts
- **`form_data`** (mutated throughout): `model`, `messages[]` (OpenAI chat format; user msgs may become content-part arrays with `image_url`), `features{voice,memory,web_search,image_generation,code_interpreter}`, `files[]`, `tool_ids[]`, `tools[]` (OpenAI specs when native), `tool_servers[]`, `skill_ids[]`, `variables`, `params{function_calling:'native'|...}`, `metadata{}`.
- **`extra_params`** (DI bundle): `__event_emitter__`, `__event_call__`, `__user__` (dict), `__metadata__`, `__oauth_token__`, `__request__`, `__model__`, `__chat_id__`, `__message_id__`, `__features__`, `__skill_ids__`.
- **`tools_dict[name]`**: `{spec: <openai-fn-spec>, callable?, type?: 'mcp', client?, direct?: bool, server?}`.
- **`sources[]`**: citation/source records accumulated by RAG + tool results, attached to the response.
- **Events** (SSE to client): `{type: 'status'|'files'|'chat:message:error'|'terminal:*'|..., data:{...}}` via `event_emitter`.

## Dependencies & assumptions
- FastAPI/Starlette `Request`, async everywhere, SSE streaming. A task/utility model (`TASK_MODEL`) separate from the chat model for tool-selection + background tasks.
- Calls into sibling subsystems: filters (`utils/filter.py`), functions/pipes (`functions.py`), tools (`utils/tools.py`, incl. `get_builtin_tools`, external OpenAPI tool servers), RAG (`retrieval/utils.py`, `rag_template`), memory (`models/memories.py`), code interpreter (`utils/code_interpreter.py` — external Jupyter, NOT a local sandbox), MCP (`utils/mcp/client.py`).
- `Chats`/`Folders`/`Skills`/`Functions` DB models; an event-emitter system bound to a chat session.

## To port this, you need:
- [ ] A single mutable request object (`form_data`) and two phases: pre-model assembly, post-model processing.
- [ ] A FIXED, documented step order; gate each capability behind feature flags.
- [ ] A `function_calling: native|non-native` fork: native → expose capabilities as tool specs; non-native → inject results into the prompt + a separate task-model call to choose tools.
- [ ] A unified `tools_dict` that merges server tools, MCP servers, terminals, client tools, and builtins behind one shape.
- [ ] An `extra_params` DI bundle delivered to plugins/filters/tools by signature introspection.
- [ ] Sortable inlet/outlet/stream filters by priority.
- [ ] A `sources` side-channel for citations; background tasks (title/tags/follow-ups) on a task model.

## Gotchas
- **Respect the native-FC guards** — almost every injection is `if function_calling != 'native'`. Without them you double-inject (prompt-stuffed AND tool-exposed).
- **Reload messages from your store, not the client** — clients strip structured tool-call `output`, breaking multi-turn tool use.
- **Non-native tool calling is a whole extra model round-trip** (task model, last-4-message window, non-streaming) — budget for the latency/cost.
- **MCP tool ids are namespaced** (`server:mcp:<id>`, tool names prefixed `<server_id>_<name>`) to avoid collisions in the merged dict.
- **Code interpreter is an external Jupyter server**, not a sandbox — the security boundary is that server's config.
- **Citation injection guards against prompt injection** — `rag_template` uses UUID-placeholder substitution and warns if context contains `<context>` tags. (Exact template string not captured — verify.)
- **Order matters**: memory→search→image→code→tools→files; reordering changes what later steps see.

## Origin (reference only)
Repo: https://github.com/open-webui/open-webui · `backend/open_webui/utils/middleware.py` (~5272 lines; key fns: `process_chat_payload` 2311, `chat_completion_tools_handler` 1246, `chat_completion_files_handler` 1957, `chat_memory_handler` 1459, `chat_web_search_handler` 1494, `process_chat_response` 5259, `background_tasks_handler` 3060, `outlet_filter_handler` 3274, `streaming_chat_response_handler` 3571), `utils/chat.py`, `utils/filter.py`, `utils/tools.py`, `functions.py`, `retrieval/utils.py`, `utils/task.py` (`rag_template`), `utils/code_interpreter.py`, `utils/mcp/client.py`. GAPS: exact `rag_template`/citation literal strings, `functions.py` pipe execution, and filter signatures were read as summaries — verify those specifics against source before relying.
