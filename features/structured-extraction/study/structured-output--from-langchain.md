# Structured Output — from [langchain](https://github.com/langchain-ai/langchain)

> Domain: [[_domain]] · Source: https://github.com/langchain-ai/langchain · NotebookLM:

## What it does

`model.with_structured_output(schema)` is a one-liner that wraps any LangChain chat model so that instead of returning a free-form text string, it always returns a Python object matching the schema you gave it. Pass a Pydantic class, get a Pydantic instance back. Pass a TypedDict or JSON Schema dict, get a validated dictionary. The model itself is the same — it's the layer around it that changes.

## Why it exists

LLMs produce text. Applications need structured data. The naive solution — prompt the model to "output valid JSON please" and then parse the result — breaks constantly: the model adds preamble text, wraps the JSON in markdown code fences, or produces invalid JSON with trailing commas. Every team ends up writing its own retry+parse loop.

`with_structured_output` solves this at the protocol level. Instead of asking the model nicely to produce JSON, it uses the model's *function calling* (or *tool calling*) capability, which is a first-class feature of modern model APIs. The model is constrained by the API itself to emit arguments in a validated JSON format, not just prompted to do so.

## How it actually works

Under the hood, `with_structured_output(schema)` does three things:

**Step 1 — convert the schema to a tool definition.** Whether you pass a Pydantic class, a TypedDict, or a raw JSON Schema dict, LangChain converts it to an OpenAI-compatible tool schema: `{"type": "function", "function": {"name": ..., "parameters": ...}}`. For Pydantic v2, it calls `model.model_json_schema()`. For TypedDicts, it uses `typing.get_type_hints()`.

**Step 2 — bind the tool to the model.** It calls `model.bind_tools([schema_as_tool], tool_choice="schema_name")`. The `tool_choice` forces the model to always call this tool — it can't output plain text. This goes into the API request as a parameter the model backend enforces.

**Step 3 — add a parser.** The result is an LCEL chain: `model_with_tools | parser`. If you passed a Pydantic class, the parser is `PydanticToolsParser` — it reads the model's tool call response, extracts the JSON arguments, and instantiates the Pydantic class with them: `MySchema(**tool_call_args)`. If validation fails (wrong types, missing required fields), it raises `OutputParserException`. If you passed a plain dict schema, the parser is `JsonOutputToolsParser` — it just returns the args dict.

**The `include_raw=True` flag** wraps the output in a dict: `{"raw": AIMessage, "parsed": MySchema, "parsing_error": None}`. This is useful when you want to inspect the raw message if parsing fails instead of having the exception bubble up.

**JSON mode alternative**: some models (like `gpt-4o`) support a `response_format: {"type": "json_object"}` parameter. When called with `method="json_mode"`, `with_structured_output` uses this instead of tool calling, then parses the returned JSON string. Less reliable than tool calling since there's no schema enforcement by the API — the model is told to output JSON but not constrained to match a specific shape.

The whole thing looks like this in practice:

```python
from pydantic import BaseModel
from langchain_anthropic import ChatAnthropic

class ProductInfo(BaseModel):
    name: str
    price: float
    in_stock: bool

llm = ChatAnthropic(model="claude-opus-4-8")
structured_llm = llm.with_structured_output(ProductInfo)

result = structured_llm.invoke("Extract info from: MacBook Pro $1299, available")
# result is a ProductInfo instance
# result.name == "MacBook Pro"
# result.price == 1299.0
# result.in_stock == True
```

## The non-obvious parts

**Tool calling, not prompt engineering.** The guarantee of structured output comes from the model API enforcing the schema, not from clever prompting. This is why it's reliable. But it means the model must support tool calling — older models or certain providers may not, in which case you fall back to JSON mode or manual prompting.

**Pydantic field descriptions become the prompt.** The docstring and `Field(description=...)` annotations on your Pydantic class are included in the tool schema sent to the model. This is your natural language prompt to the model about what each field means. Richer descriptions → better extraction.

**`tool_choice` forces the issue.** Without forcing a specific tool, the model might decide it doesn't have enough information and return plain text instead. The `tool_choice=tool_name` parameter eliminates that failure mode — the model must always call the tool.

**Multiple schemas = no tool choice.** If you pass a list of schemas to `bind_tools()`, you can't force a specific one. The model picks. `with_structured_output` avoids this by always binding exactly one schema.

**Validation only on parse.** The Pydantic validation happens in the parser, not in the API. If the API returns valid JSON that doesn't match your Pydantic model, that's caught and raises `OutputParserException`. If the API returns malformed JSON (rare with tool calling), `json.loads()` fails first.

**Streaming doesn't give you a partial Pydantic object.** When streaming `with_structured_output`, the parser accumulates JSON fragments and only emits the final parsed object at the end. There's a `JsonOutputKeyToolsParser` variant that can emit partial dicts as the JSON builds up — useful for showing the user progress.

## Related

- [[lcel-runnable-protocol--from-langchain]] (with_structured_output returns an LCEL chain; the pipe is the mechanism)
- [[schema-driven-extraction--from-llm-scraper]] (same pattern in TypeScript via Vercel AI SDK with Zod schemas)
- [[tool-calling-agent--from-langchain]] (tool schemas use the same JSON Schema conversion as structured output)
- [[ai-carousel-generation--from-carousel-generator]] (same forced-function-call pattern with zodToJsonSchema)
