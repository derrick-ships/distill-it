# Tool Calling + Agent Loop — from [langchain](https://github.com/langchain-ai/langchain)

> Domain: [[_domain]] · Source: https://github.com/langchain-ai/langchain · NotebookLM:

## What it does

This is how you give an LLM the ability to use external tools — search, calculators, databases, APIs — and then loop it automatically until the task is done. The model decides which tool to call, the framework calls it, feeds the result back to the model, and the model either calls another tool or gives a final answer. This Reason-Act cycle repeats until the model says it's done (or a safety limit is hit).

## Why it exists

A bare LLM knows only what's in its training data. Give it tools and it can look things up, run code, check databases, and send messages. The key design challenge is the loop: the model's output is a *decision* (call tool X with args Y), not a final answer. Something needs to execute that decision, collect the result, and present it back. The agent loop is that something.

## How it actually works

### Part 1: Defining tools

The `@tool` decorator turns any Python function into a tool the model can call:

```python
from langchain_core.tools import tool

@tool
def get_weather(city: str) -> str:
    """Get current weather for a city. Use this when the user asks about weather."""
    return requests.get(f"https://weather.api/...?city={city}").text
```

This creates a `StructuredTool` with:
- **name** — the function name (`get_weather`)
- **description** — the docstring (used verbatim in the tool schema sent to the model; this is the LLM's "how to use me" doc)
- **args_schema** — a Pydantic model auto-generated from the function signature (`city: str`)

For complex inputs, you can also define the Pydantic schema explicitly:

```python
class SearchInput(BaseModel):
    query: str = Field(description="The search query")
    num_results: int = Field(default=5, description="Number of results to return")

@tool(args_schema=SearchInput)
def search(query: str, num_results: int = 5) -> list[str]:
    """Search the web."""
    ...
```

### Part 2: Binding tools to the model

```python
model_with_tools = llm.bind_tools([get_weather, search])
```

`bind_tools` serializes each tool's schema into an OpenAI-compatible tool definition and attaches it to every model invocation. The model can now respond with a `tool_calls` list instead of just text.

When the model decides to call a tool, the response `AIMessage` looks like:

```python
AIMessage(
    content="",
    tool_calls=[
        {
            "type": "tool_call",
            "id": "call_abc123",
            "name": "get_weather",
            "args": {"city": "Paris"}
        }
    ]
)
```

### Part 3: Executing tool calls

Each `ToolCall` in the message needs to be executed and wrapped in a `ToolMessage`:

```python
ToolMessage(
    content="Sunny, 22°C",
    tool_call_id="call_abc123",
    name="get_weather",
    status="success"
)
```

The `ToolMessage` goes back into the conversation alongside the `AIMessage` that triggered it. The model sees the full conversation including the tool result when generating its next response.

### Part 4: The agent loop (AgentExecutor / create_tool_calling_agent)

`create_tool_calling_agent(llm, tools, prompt)` builds an agent Runnable that:
1. Formats the current state (input + scratchpad) into messages using the prompt template
2. Calls the model
3. Returns either `AgentFinish` (done) or a list of `AgentAction` objects (more tools to call)

`AgentExecutor(agent=agent, tools=tools)` wraps this in the loop:
1. Invoke the agent Runnable with current state
2. If `AgentFinish` → return `return_values` (the final answer) and stop
3. If tool calls → execute each tool → collect `AgentStep(action, observation)` pairs → add to scratchpad
4. Go back to step 1

Safety limits prevent infinite loops:
- `max_iterations` (default 15) — stops after N cycles
- `max_execution_time` (seconds) — wall-clock timeout
- `early_stopping_method` — either `"force"` (just return whatever the last tool output was) or `"generate"` (ask the model to summarize and wrap up)

### The scratchpad format

The scratchpad is what the model sees as its "working memory" for the current task. It's serialized as a sequence of `AIMessage` + `ToolMessage` pairs. Each cycle appends the latest tool calls + results. This grows linearly with the number of tool calls, so long agent runs can hit context limits.

## The non-obvious parts

**The description IS the prompt.** The model chooses which tool to call based entirely on the `description` field. A vague description = wrong tool selection. The most common agent bug is bad tool descriptions. Write them like you're writing API docs for a junior developer who has to pick between tools.

**`tool_choice` is dangerous in a loop.** Unlike structured output, you don't want to force `tool_choice` in an agent — the model needs to be able to decide "I'm done, here's the answer" and not call a tool. Set `tool_choice="auto"` (the default).

**Injected arguments skip the schema.** `InjectedToolArg` marks parameters the framework injects at runtime (like `run_manager`, `tool_call_id`). These are filtered out of the schema sent to the model — the model never sees them, so it can't try to provide them. The agent framework fills them in before calling the function.

**AgentExecutor vs LangGraph**: `AgentExecutor` is the classic single-file loop. For production agents with complex branching, human-in-the-loop, or custom state, LangGraph is the more powerful replacement — it models the loop as an explicit state graph. `AgentExecutor` is fine for simple tool-calling tasks.

**Parallel tool calls**: modern model APIs can return multiple tool calls in one response. `AgentExecutor` handles this by executing all of them (in parallel if `return_exceptions=True`), then feeding all results back together. The model can then decide next steps with all results in context.

**Error handling**: if a tool raises an exception, `handle_tool_error=True` catches it and feeds the error message back to the model as a `ToolMessage` with `status="error"`. This lets the model recover by trying a different approach instead of crashing the whole agent.

## Related

- [[lcel-runnable-protocol--from-langchain]] (agents are LCEL Runnables; the agent itself is built as a chain)
- [[structured-output--from-langchain]] (tool schemas use the same JSON Schema conversion; bind_tools is related to with_structured_output)
- [[conversation-memory--from-whatsapp-agentkit]] (per-session memory fed into the agent's chat_history)
- [[agent-output-contract--from-last30days-skill]] (alternative approach: prose contracts instead of tool loops)
- [[ordered-backend-routing--from-agent-reach]] (capability routing at the tool-selection layer)
- [[rag-pipeline--from-langchain]] (retrieval is often wired as a tool the agent can call)
