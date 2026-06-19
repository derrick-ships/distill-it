# Tool Calling + Agent Loop (build spec) — distilled from langchain

## Summary

Implement a tool-calling agent: define tools with `@tool`, bind them to a chat model, then run a ReAct loop that cycles through (model decides → execute tool → feed result back) until the model produces a final answer with no tool calls. The loop is capped by iteration/time limits and includes error handling so individual tool failures don't crash the agent.

## Core logic (inlined)

### Tool definition

```python
from pydantic import BaseModel, Field
from typing import Any, Callable
import inspect, json

class ToolCall(dict):
    """Shape: {"type": "tool_call", "id": str, "name": str, "args": dict}"""

class ToolMessage:
    def __init__(self, content: str, tool_call_id: str, name: str, status: str = "success"):
        self.content = content
        self.tool_call_id = tool_call_id
        self.name = name
        self.status = status  # "success" | "error"
        self.type = "tool"

class BaseTool:
    name: str
    description: str
    args_schema: type[BaseModel]

    def invoke(self, tool_call: dict | str) -> ToolMessage:
        if isinstance(tool_call, str):
            args = json.loads(tool_call)
            tool_call_id = ""
        else:
            args = tool_call.get("args", {})
            tool_call_id = tool_call.get("id", "")

        try:
            # Filter out injected args before passing to _run
            clean_args = {k: v for k, v in args.items()
                         if k not in self._injected_arg_names}
            result = self._run(**clean_args)
            return ToolMessage(
                content=str(result),
                tool_call_id=tool_call_id,
                name=self.name,
                status="success"
            )
        except Exception as e:
            if self.handle_tool_error:
                return ToolMessage(
                    content=f"Error: {e}",
                    tool_call_id=tool_call_id,
                    name=self.name,
                    status="error"
                )
            raise

    def _run(self, **kwargs) -> Any:
        raise NotImplementedError

    def as_tool_schema(self) -> dict:
        """Serialize to OpenAI-compatible tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema()
            }
        }
```

### @tool decorator

```python
def tool(func: Callable = None, *, name: str = None, description: str = None,
         args_schema=None, handle_tool_error: bool = True):
    """Decorate a function to create a BaseTool."""
    def decorator(f):
        tool_name = name or f.__name__
        tool_desc = description or (f.__doc__ or "").strip()

        # Build args_schema from function signature if not provided
        if args_schema is None:
            hints = {
                k: v for k, v in f.__annotations__.items()
                if k != "return"
            }
            # Create dynamic Pydantic model
            fields = {}
            sig = inspect.signature(f)
            for param_name, param in sig.parameters.items():
                if param_name in ("self", "run_manager"):
                    continue
                annotation = hints.get(param_name, Any)
                default = param.default if param.default != inspect.Parameter.empty else ...
                fields[param_name] = (annotation, Field(default=default))
            from pydantic import create_model
            schema = create_model(f"_{tool_name}_schema", **fields)
        else:
            schema = args_schema

        class DerivedTool(BaseTool):
            pass

        instance = DerivedTool()
        instance.name = tool_name
        instance.description = tool_desc
        instance.args_schema = schema
        instance.handle_tool_error = handle_tool_error
        instance._injected_arg_names = set()
        instance._run = lambda **kw: f(**kw)
        return instance

    if func is not None:
        return decorator(func)
    return decorator
```

### bind_tools on a chat model

```python
class BaseChatModel:
    def bind_tools(self, tools: list, *, tool_choice: str | dict | None = None):
        """Return a copy of this model pre-configured with tool schemas."""
        tool_schemas = []
        for t in tools:
            if isinstance(t, BaseTool):
                tool_schemas.append(t.as_tool_schema())
            elif isinstance(t, dict):
                tool_schemas.append(t)  # already a JSON schema
            elif hasattr(t, "model_json_schema"):
                # Pydantic class → treat as structured output schema
                tool_schemas.append({
                    "type": "function",
                    "function": {
                        "name": t.__name__,
                        "description": t.__doc__ or "",
                        "parameters": t.model_json_schema()
                    }
                })

        bound_kwargs = {"tools": tool_schemas}
        if tool_choice is not None:
            bound_kwargs["tool_choice"] = tool_choice

        return self._with_config(bound_kwargs)
```

### Agent loop (create_tool_calling_agent + AgentExecutor)

```python
def create_tool_calling_agent(llm, tools: list[BaseTool], prompt) -> "Runnable":
    """
    Returns a Runnable that takes {input, chat_history, agent_scratchpad}
    and returns list[ToolCall] | "FINAL_ANSWER: ..." string.
    """
    model_with_tools = llm.bind_tools(tools)
    tool_map = {t.name: t for t in tools}

    def agent_runnable(state: dict):
        messages = prompt.format_messages(**state)
        response = model_with_tools.invoke(messages)
        return response  # AIMessage with .tool_calls or plain content

    return RunnableLambda(agent_runnable)


class AgentExecutor:
    def __init__(
        self,
        agent,                          # The agent Runnable
        tools: list[BaseTool],
        max_iterations: int = 15,
        max_execution_time: float | None = None,
        handle_parsing_errors: bool = True,
        early_stopping_method: str = "force",  # "force" | "generate"
    ):
        self.agent = agent
        self.tool_map = {t.name: t for t in tools}
        self.max_iterations = max_iterations
        self.max_execution_time = max_execution_time

    def invoke(self, inputs: dict) -> dict:
        import time
        start = time.monotonic()
        state = {
            "input": inputs["input"],
            "chat_history": inputs.get("chat_history", []),
            "agent_scratchpad": [],   # list of (AIMessage, ToolMessage) pairs
        }
        iterations = 0

        while iterations < self.max_iterations:
            if (self.max_execution_time and
                    time.monotonic() - start > self.max_execution_time):
                return self._early_stop(state)

            # Call the agent
            response = self.agent.invoke(state)  # AIMessage

            # Check if done (no tool calls = final answer)
            if not response.tool_calls:
                return {
                    "output": response.content,
                    "intermediate_steps": state["agent_scratchpad"],
                }

            # Execute all tool calls (model may request several at once)
            tool_messages = []
            for tc in response.tool_calls:
                tool = self.tool_map.get(tc["name"])
                if tool is None:
                    tool_messages.append(ToolMessage(
                        content=f"Tool '{tc['name']}' not found.",
                        tool_call_id=tc["id"],
                        name=tc["name"],
                        status="error"
                    ))
                else:
                    tool_messages.append(tool.invoke(tc))

            # Append to scratchpad (model sees its own tool calls + results)
            state["agent_scratchpad"].append((response, tool_messages))
            iterations += 1

        return self._early_stop(state)

    def _early_stop(self, state) -> dict:
        return {
            "output": "Agent stopped: max iterations or time exceeded.",
            "intermediate_steps": state["agent_scratchpad"],
        }
```

### Prompt template (messages format for the agent)

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. Use tools when needed."),
    MessagesPlaceholder("chat_history", optional=True),
    ("human", "{input}"),
    MessagesPlaceholder("agent_scratchpad"),  # tool calls + results history
])
```

### Serializing scratchpad into messages

The `agent_scratchpad` list of `(AIMessage, list[ToolMessage])` pairs must be flattened into a message list before passing to the prompt:

```python
def format_scratchpad(scratchpad: list) -> list:
    messages = []
    for ai_msg, tool_msgs in scratchpad:
        messages.append(ai_msg)         # the model's tool call request
        messages.extend(tool_msgs)      # the tool results
    return messages
```

## Data contracts

### AgentState (input to agent per cycle)

```python
{
    "input": str,                       # user's question
    "chat_history": list[BaseMessage],  # conversation history
    "agent_scratchpad": list,           # [(AIMessage, [ToolMessage]), ...]
}
```

### ToolCall (from AIMessage.tool_calls)

```python
{
    "type": "tool_call",
    "id": str,       # "call_abc123" — links tool response back
    "name": str,     # must match tool.name exactly
    "args": dict,    # already-parsed dict (not a JSON string)
}
```

### ToolMessage (fed back to model)

```python
{
    "type": "tool",
    "content": str,          # tool's return value as string
    "tool_call_id": str,     # must match the ToolCall id
    "name": str,             # tool name
    "status": "success" | "error",
}
```

### AgentExecutor output

```python
{
    "output": str,                          # final answer from model
    "intermediate_steps": list[tuple],      # [(AIMessage, [ToolMessage])]
}
```

## Dependencies & assumptions

- **pydantic v2**: `create_model`, `BaseModel`, `model_json_schema()`
- **Chat model** with tool calling support (OpenAI, Anthropic, Gemini, Groq, etc.)
- Model must return `AIMessage` with `.tool_calls: list[dict]` attribute
- The tool map (`{name: tool}`) must be consistent between `bind_tools` call and executor
- Tool function return values are coerced to `str` via `str(result)` for the ToolMessage content

## To port this, you need:

- [ ] `BaseTool` class with `name`, `description`, `args_schema`, `invoke()`, `as_tool_schema()`
- [ ] `@tool` decorator that generates `BaseTool` from a function + docstring + type hints
- [ ] `bind_tools(tools, tool_choice)` method on your chat model
- [ ] `AgentExecutor` with the while-loop, iteration cap, and scratchpad management
- [ ] `format_scratchpad()` to flatten `(AIMessage, [ToolMessage])` pairs into a flat message list
- [ ] A `MessagesPlaceholder` concept in your prompt template (or equivalent interpolation)
- [ ] `ToolMessage` class that your model accepts in the message list

## Gotchas

**Tool descriptions are the most important part.** The model uses the description to decide *which* tool to call and *when*. Vague or overlapping descriptions cause wrong tool selection. Treat descriptions like API documentation.

**Match `tool_call_id` precisely.** The model links its tool call request to the result via `id`/`tool_call_id`. A mismatch causes the model to think the result belongs to a different call. Always copy the id from `tool_calls[i]["id"]` into the ToolMessage.

**Parallel tool calls happen automatically.** Modern APIs (GPT-4o, Claude Opus) can return multiple tool calls in one response. Your executor must handle `len(response.tool_calls) > 1`. Execute all before feeding results back.

**Scratchpad grows unboundedly.** Each iteration adds one AIMessage + N ToolMessages. For long-running agents, this can hit the context window. Add a window: `state["agent_scratchpad"] = state["agent_scratchpad"][-10:]` to keep only the last 10 steps.

**AgentExecutor vs LangGraph**: For simple linear tool-use, AgentExecutor is fine. For branching (different paths based on tool results), human-in-the-loop pauses, or persistent state across sessions — use LangGraph instead. LangGraph represents the loop as a state graph with explicit edges.

**Error recovery is the model's job.** When you set `handle_tool_error=True`, a failed tool returns its error message as a `ToolMessage` with `status="error"`. Feed it back — the model can then retry with different arguments, try a different tool, or ask the user for clarification. Don't crash on tool failure.

## Origin (reference only)

- Repo: https://github.com/langchain-ai/langchain
- Agent data structures: `libs/core/langchain_core/agents.py`
- Tool base: `libs/core/langchain_core/tools/base.py`
- Agent runners: `libs/langchain/langchain/agents/` (create_tool_calling_agent, AgentExecutor)
