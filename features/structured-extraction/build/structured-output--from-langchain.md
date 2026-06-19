# Structured Output (build spec) — distilled from langchain

## Summary

Implement `with_structured_output(schema)` on a chat model: a method that returns a new Runnable chain that always produces a typed, schema-validated Python object instead of free-form text. Uses the model's tool-calling API (or JSON mode as fallback) to enforce the schema at the API level, then validates and instantiates the result via Pydantic or as a plain dict.

## Core logic (inlined)

### The with_structured_output method

```python
from typing import Any, Type
from pydantic import BaseModel
import json

def with_structured_output(
    self,           # BaseChatModel instance
    schema,         # Pydantic class | TypedDict | dict (JSON Schema)
    *,
    method: str = "function_calling",   # "function_calling" | "json_mode"
    include_raw: bool = False,
) -> "Runnable":
    """
    Returns a Runnable: input messages → validated schema instance (or dict).
    """
    if method == "json_mode":
        return _build_json_mode_chain(self, schema, include_raw)

    # Default: tool/function calling
    tool_def = _schema_to_tool_definition(schema)
    tool_name = tool_def["function"]["name"]

    # Bind the schema as the ONLY tool, and force its selection
    model_with_tool = self.bind_tools(
        [tool_def],
        tool_choice={"type": "function", "function": {"name": tool_name}},
    )

    # Build the parser
    if _is_pydantic_class(schema):
        parser = PydanticToolsParser(tools=[schema])
    else:
        parser = JsonOutputKeyToolsParser(key_name=tool_name, first_tool_only=True)

    if include_raw:
        # Wrap to return {raw, parsed, parsing_error}
        return model_with_tool | RunnableLambda(_wrap_include_raw(parser))
    else:
        return model_with_tool | parser
```

### Schema → tool definition conversion

```python
def _schema_to_tool_definition(schema) -> dict:
    """Convert Pydantic class, TypedDict, or JSON Schema dict to OpenAI tool format."""
    if _is_pydantic_class(schema):
        name = schema.__name__
        description = schema.__doc__ or f"Schema for {name}"
        json_schema = schema.model_json_schema()  # Pydantic v2
        # Remove $defs to inline definitions
        json_schema.pop("title", None)
    elif isinstance(schema, dict):
        # Assume it's already a JSON Schema
        name = schema.get("title", "output")
        description = schema.get("description", "Output schema")
        json_schema = schema
    else:
        raise ValueError(f"Unsupported schema type: {type(schema)}")

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": json_schema,
        }
    }

def _is_pydantic_class(schema) -> bool:
    import inspect
    return inspect.isclass(schema) and issubclass(schema, BaseModel)
```

### PydanticToolsParser

```python
class PydanticToolsParser:
    def __init__(self, tools: list[Type[BaseModel]]):
        # Map tool name -> Pydantic class
        self.tool_map = {t.__name__: t for t in tools}

    def invoke(self, message) -> BaseModel:
        """Extract tool call from AIMessage, validate, return Pydantic instance."""
        tool_calls = getattr(message, "tool_calls", [])
        if not tool_calls:
            # Fall back to additional_kwargs (older models)
            raw = message.additional_kwargs.get("function_call")
            if raw:
                tool_calls = [{"name": raw["name"], "args": json.loads(raw["arguments"])}]

        if not tool_calls:
            raise OutputParserException(
                "No tool call found in model output. "
                "The model didn't call the expected tool."
            )

        call = tool_calls[0]  # first_tool_only=True behavior
        tool_name = call["name"]
        args = call["args"] if isinstance(call["args"], dict) else json.loads(call["args"])

        schema_class = self.tool_map.get(tool_name)
        if schema_class is None:
            raise OutputParserException(f"Unknown tool: {tool_name}")

        try:
            return schema_class(**args)
        except Exception as e:
            raise OutputParserException(
                f"Failed to parse tool call args into {tool_name}: {e}\n"
                f"Args received: {args}"
            ) from e
```

### JsonOutputKeyToolsParser (for dict schemas)

```python
class JsonOutputKeyToolsParser:
    def __init__(self, key_name: str, first_tool_only: bool = True):
        self.key_name = key_name
        self.first_tool_only = first_tool_only

    def invoke(self, message) -> dict | list[dict]:
        tool_calls = message.tool_calls or []
        matching = [c for c in tool_calls if c["name"] == self.key_name]
        if not matching:
            raise OutputParserException(f"No tool call named '{self.key_name}' found")
        results = [c["args"] for c in matching]
        return results[0] if self.first_tool_only else results
```

### include_raw wrapper

```python
def _wrap_include_raw(parser):
    def wrapped(message):
        try:
            parsed = parser.invoke(message)
            parsing_error = None
        except Exception as e:
            parsed = None
            parsing_error = e
        return {
            "raw": message,
            "parsed": parsed,
            "parsing_error": parsing_error,
        }
    return wrapped
```

### JSON mode chain (alternative)

```python
def _build_json_mode_chain(model, schema, include_raw: bool):
    from langchain_core.output_parsers import JsonOutputParser

    model_json = model.bind(response_format={"type": "json_object"})

    if _is_pydantic_class(schema):
        # Add instructions to the system message to output the schema
        schema_instructions = (
            f"Return a JSON object matching this schema:\n"
            f"{json.dumps(schema.model_json_schema(), indent=2)}"
        )
        # The caller must add these instructions to the prompt manually,
        # or use a prompt injection approach
        parser = JsonOutputParser(pydantic_object=schema)
    else:
        parser = JsonOutputParser()

    if include_raw:
        return model_json | RunnableLambda(_wrap_include_raw(parser))
    return model_json | parser
```

## Data contracts

### Input (what goes into the chain)

```python
# Same as the underlying chat model - a list of messages or a string
input: str | list[BaseMessage]
```

### Output (what comes out)

```python
# With a Pydantic schema:
output: MyPydanticClass  # fully validated instance

# With a dict/TypedDict/JSON Schema:
output: dict  # raw args dict from tool call

# With include_raw=True:
output: {
    "raw": AIMessage,           # the model's full response
    "parsed": MyPydanticClass | dict | None,  # None if parsing failed
    "parsing_error": Exception | None,
}
```

### Tool call format in AIMessage (from model)

```python
AIMessage(
    content="",  # empty when the model makes a tool call
    tool_calls=[{
        "type": "tool_call",
        "id": "call_abc123",
        "name": "MySchemaName",
        "args": {   # already parsed dict (langchain normalizes this)
            "field_one": "value",
            "field_two": 42
        }
    }]
)
```

## Dependencies & assumptions

- **langchain-core** (or equivalent): `BaseChatModel`, `AIMessage`, `OutputParserException`, `Runnable`
- **pydantic v2**: `BaseModel.model_json_schema()`, `model(**args)` instantiation with validation
- **Model must support tool calling**: OpenAI, Anthropic, Google Gemini, Groq, Mistral all do. Some older or local models don't → fall back to `method="json_mode"` or prompt-based approaches.
- The model must be a `BaseChatModel` (takes messages, returns `AIMessage`) — not an `LLM` (takes a string, returns a string).

## To port this, you need:

- [ ] A `bind_tools(schemas, tool_choice=...)` method on your chat model class
- [ ] Schema-to-tool-definition converter (`_schema_to_tool_definition`)
- [ ] `PydanticToolsParser` that reads `.tool_calls` from model output and instantiates Pydantic
- [ ] `JsonOutputKeyToolsParser` for dict schemas
- [ ] `with_structured_output(schema, method, include_raw)` wiring them together
- [ ] An `OutputParserException` class for parse failures
- [ ] (Optional) JSON mode fallback for models without tool calling

## Gotchas

**`tool_choice` is essential.** Without forcing the tool call, the model may decide to respond with plain text if it doesn't have enough information. Always set `tool_choice` to the tool name when you want guaranteed structured output.

**Pydantic field descriptions are your schema-level prompt.** The model sees `Field(description="The product name as a string, e.g. 'MacBook Pro'")`. Invest in good descriptions — they're the only way to guide the model's extraction logic per-field.

**`args` may be a string, not a dict.** Some model APIs return tool call arguments as a JSON string, not a parsed dict. LangChain normalizes this, but if you're building from scratch, handle `isinstance(args, str)` → `json.loads(args)`.

**Streaming accumulates, doesn't emit partials.** `stream()` on a `with_structured_output` chain collects the full JSON before parsing. To get streaming partials, use `JsonOutputKeyToolsParser` with a streaming parser that accumulates partial JSON and emits intermediate dict states.

**Pydantic validation is post-hoc.** The model API enforces the JSON *structure* (it's valid JSON matching the schema shape), but Pydantic re-validates types and constraints. `EmailStr`, `conint(ge=0)`, etc. can still fail even when the model output is valid JSON.

**Nested schemas need flattened JSON Schema.** Some APIs don't handle `$defs`/`$ref` in JSON Schema for tool parameters. Flatten nested schemas with `model_json_schema()` + manual `$ref` resolution before sending.

## Origin (reference only)

- Repo: https://github.com/langchain-ai/langchain
- Primary file: `libs/core/langchain_core/language_models/chat_models.py` (with_structured_output)
- Parser implementations: `libs/core/langchain_core/output_parsers/openai_tools.py`
