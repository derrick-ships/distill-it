# Multi-Provider LLM Abstraction (build spec) — distilled from browser-use

## Summary

A dependency-light layer that unifies many LLM providers behind one async method with guaranteed structured output. Shared message types + a `BaseChatModel` Protocol exposing `ainvoke(messages, output_format) -> ChatInvokeCompletion[T]`. Each provider is a self-contained adapter that serializes the shared messages to its native format and enforces structured output its own way (OpenAI json_schema response_format; Anthropic forced tool-use; Google response_schema). Includes a schema optimizer and unified token accounting. No LangChain.

## Core logic (inlined)

### Shared messages (`llm/messages.py`)
```
_MessageBase: { role: 'user'|'system'|'assistant', cache: bool=False }
UserMessage:   { role='user', content: str | list[TextPart|ImagePart], name?: str }
SystemMessage: { role='system', content: str | list[TextPart], name?: str }
AssistantMessage:{ role='assistant', content: str|list[TextPart|RefusalPart]|None, refusal?: str, tool_calls: list[ToolCall]=[] }
TextPart:  { type:'text', text: str }
ImagePart: { type:'image_url', image_url: { url: str, detail: 'auto'|'low'|'high', media_type } }
RefusalPart:{ type:'refusal', refusal: str }
ToolCall:  { id: str, type:'function', function: { name: str, arguments: str(JSON) } }
BaseMessage = UserMessage | SystemMessage | AssistantMessage
```

### Contract (`llm/base.py`) — a runtime_checkable Protocol (providers are @dataclass, not subclasses)
```
class BaseChatModel(Protocol):
    model: str
    provider: str            # property
    name: str                # property (display)
    model_name: str          # property (alias of model)
    _verified_api_keys: bool = False
    async def ainvoke(self, messages: list[BaseMessage], output_format: type[T] | None = None, **kwargs)
        -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]   # T bound to Union[BaseModel, str]
    # __get_pydantic_core_schema__ -> any_schema()  so it can be a Pydantic field
```

### Return envelope (`llm/views.py`)
```
ChatInvokeUsage: { prompt_tokens, prompt_cached_tokens?, prompt_cache_creation_tokens?,
    prompt_cache_creation_5m_tokens?, prompt_cache_creation_1h_tokens?, prompt_image_tokens?(google),
    completion_tokens, total_tokens, pricing_multiplier?(anthropic US=1.1) }
ChatInvokeCompletion[T]: { completion: T, thinking?: str, redacted_thinking?: str,
    usage: ChatInvokeUsage|None, stop_reason?: str, stop_details?: dict }
```

### Schema optimizer (`llm/schema.py`)
```
SchemaOptimizer.create_optimized_json_schema(model) -> dict:
    s = model.model_json_schema()
    inline every {$ref: '#/$defs/X'} with its definition (recursive); drop $defs
    strip additionalProperties + non-essential metadata; KEEP all 'description' strings
    _make_strict_compatible: for every object node set required = all property keys
    second pass: additionalProperties=false on every object node
create_gemini_optimized_schema(model): in practice delegates to the above (no diff) — Gemini fixes happen in adapter
```

### Provider adapter pattern — OpenAI (`llm/openai/chat.py`)
```
msgs = OpenAIMessageSerializer.serialize_messages(messages)   # -> ChatCompletion*MessageParam list (images as content parts; tool_calls as function tool calls)
if output_format:
    schema = SchemaOptimizer.create_optimized_json_schema(output_format)
    response_format = ResponseFormatJSONSchema(type='json_schema',
        json_schema={'name':'agent_output','strict':True,'schema':schema})
resp = await client.chat.completions.create(messages=msgs, response_format=response_format, ...)
parsed = output_format.model_validate_json(resp.choices[0].message.content)
# reasoning models (o1/o3/o4/gpt-5): drop temperature+frequency_penalty, add reasoning_effort
# flags: dont_force_structured_output (skip response_format, parse raw); add_schema_to_system_prompt
# usage: prompt_tokens, prompt_tokens_details.cached_tokens, completion_tokens(incl reasoning), total_tokens
```

### Provider adapter pattern — Anthropic (`llm/anthropic/chat.py`)  *** structured output via forced tool-use ***
```
msgs, system = AnthropicMessageSerializer.serialize_messages(messages)  # system extracted separately; only last cache=True kept
if output_format:
    schema = SchemaOptimizer.create_optimized_json_schema(output_format)
    del schema['title']                                  # Anthropic rejects title in input_schema
    tool = ToolParam(name=output_format.__name__,
                     description=f'Extract information in the format of {output_format.__name__}',
                     input_schema=schema, cache_control={'type':'ephemeral'})
    tool_choice = {'type':'auto'} if _requires_auto_tool_choice() else {'type':'tool','name':tool.name}
resp = await client.messages.create(messages=msgs, system=system, tools=[tool], tool_choice=tool_choice, ...)
block = first b in resp.content where b.type=='tool_use'
parsed = output_format.model_validate(block.input)       # block.input is already a dict -> model_validate (NOT _json)
# also collect text blocks, thinking, redacted_thinking from resp.content
# usage: prompt_tokens = input_tokens + cache_read_input_tokens; prompt_cached_tokens = cache_read_input_tokens;
#        cache creation 5m/1h; pricing_multiplier=1.1 if inference_geo=='US'
```

### Provider adapter pattern — Google (`llm/google/chat.py`)
```
contents, system_instruction = GoogleMessageSerializer.serialize_messages(messages)  # assistant->role 'model'; images via Part.from_bytes
if output_format and supports_structured_output:
    schema = _fix_gemini_schema(SchemaOptimizer.create_gemini_optimized_schema(output_format))
    # _fix_gemini_schema: resolve $ref inline, drop $defs/additionalProperties/default,
    #   inject {_placeholder: string} into any OBJECT node with no properties (Gemini rejects empty objects)
    config.response_mime_type = 'application/json'; config.response_schema = schema
resp = await client.aio.models.generate_content(contents=contents, config=config, ...)
parsed = output_format.model_validate_json(resp.text)
# fallback (no structured support): append schema text to last message, extract ```json ...``` block, validate
# usage from resp.usage_metadata: prompt_token_count, candidates_token_count (excl thoughts),
#        cached_content_token_count, image tokens filtered from prompt_tokens_details modality==IMAGE
# retry: exp backoff on [429,500,502,503,504]
```

### Exceptions (`llm/exceptions.py`) — drive agent provider-fallback
```
ModelError -> ModelProviderError(status ~502) -> ModelRateLimitError(429)
```

## Data contracts
- **Call:** `await llm.ainvoke(list[BaseMessage], output_format: type[BaseModel]|None) -> ChatInvokeCompletion[T]`.
- **Result:** `.completion` is a validated `output_format` instance (or `str` if none); `.usage` is `ChatInvokeUsage|None`; `.thinking` populated for Anthropic.
- **Provider construction:** each `Chat*` is a dataclass with at least `model: str` + provider-specific config (api_key, base_url, temperature, etc.).

## Dependencies & assumptions
- Per-provider SDKs (`openai`, `anthropic`, `google-genai`, …) — lazy-imported so one import doesn't pull all.
- Pydantic v2 for `model_json_schema`/`model_validate`.
- `ChatOpenAILike` covers any OpenAI-compatible endpoint (Groq/DeepSeek/Ollama) by subclassing the OpenAI adapter.
- `ChatLiteLLM` is the escape hatch for anything else (incl. LangChain-backed models).

## To port this, you need:
- [ ] Shared message types (user/system/assistant + text/image/refusal parts + a `cache` flag).
- [ ] A single `ainvoke(messages, output_format)` contract returning a `{completion, usage, thinking, stop_reason}` envelope.
- [ ] A schema optimizer that inlines `$ref`s, forces strict `required`, sets `additionalProperties:false`.
- [ ] One adapter per provider that (a) serializes shared messages to native format and (b) enforces structured output the provider's way: OpenAI json_schema response_format; **Anthropic forced tool-use** (model->tool, `tool_choice` to that tool, validate `block.input`, delete `title`); Google `response_schema` + empty-object `_placeholder` fix.
- [ ] Per-provider usage parsing into one `ChatInvokeUsage` shape.
- [ ] An exception hierarchy your loop can branch on for rate-limit/provider fallback.

## Gotchas
- **Anthropic = no JSON mode.** You MUST use the tool-forcing trick; and you MUST `del schema['title']`. Validate `block.input` with `model_validate` (it's a dict), not `model_validate_json`.
- **Gemini rejects empty objects** and `additionalProperties`/`default` — run the `_fix_gemini_schema` pass.
- **Some Claude versions reject forced `tool_choice`** — fall back to `auto` and still locate the `tool_use` block.
- **It's a Protocol** — no shared base machinery; each adapter must call the optimizer itself. Don't assume a base class runs it.
- **Token accounting differs wildly** (Anthropic splits cache read/creation; Google has image + thoughts tokens) — normalize carefully or cost math breaks.
- **Reasoning models** need `temperature` removed and `reasoning_effort` added (OpenAI o-series/gpt-5).
- **Image content** must be serialized per provider (OpenAI content parts vs Anthropic image blocks vs Gemini `Part.from_bytes`).

## Origin (reference only)
Repo: https://github.com/browser-use/browser-use (`main`). `browser_use/llm/`:
`base.py` (Protocol), `messages.py`, `views.py` (`ChatInvokeCompletion`/`ChatInvokeUsage`), `schema.py` (`SchemaOptimizer`),
`exceptions.py`, `models.py`/`__init__.py` (lazy loading + factory), and per-provider `openai/`, `anthropic/`, `google/`,
`litellm/`, `browser_use/` (each with `chat.py` + `serializer.py`). `like.py` = `ChatOpenAILike`.
Gaps to verify if reachable: exact `_requires_auto_tool_choice()` model list; Mistral schema stripper; the
groq/cerebras/deepseek/ollama/aws/azure/vercel/openrouter adapters (assumed OpenAI-compatible subclasses); Gemini thinking-config path.
