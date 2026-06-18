# Graph Execution Engine (build spec) — distilled from scrapegraph-ai

## Summary
Build a tiny pipeline engine where work is expressed as a list of **nodes** (single-purpose steps) wired by **edges**, traversed from an entry point while threading one shared mutable `state` dict. Each node reads the keys it needs (declared as a boolean expression over state keys), does its job, and writes results back into `state`. Add a special **conditional node** type that returns the *name* of the next node to enable branching/retry loops. Wrap every node call with timing + token/cost accounting. This is the substrate; all real logic lives in nodes. ~150 lines total.

## Core logic (inlined)

### The node contract (`BaseNode`)
Every step subclasses this. Key fields: `node_name` (unique id), `node_type` (`"node"` or `"conditional_node"`), `input` (boolean expr string of required state keys), `output` (list of keys it writes), `min_input_len`, `node_config` (dict of per-node settings, incl. `llm_model`, `schema`, etc.). `update_config(params, overwrite)` lets the graph push common params (the LLM instance, headless flag, timeout…) into every node after construction.

```python
from abc import ABC, abstractmethod

class BaseNode(ABC):
    def __init__(self, node_name, node_type, input, output, min_input_len=1, node_config=None):
        if node_type not in ("node", "conditional_node"):
            raise ValueError(f"node_type must be 'node' or 'conditional_node', got '{node_type}'")
        self.node_name = node_name
        self.node_type = node_type
        self.input = input              # e.g. "user_prompt & (relevant_chunks | parsed_doc | doc)"
        self.output = output            # e.g. ["answer"]
        self.min_input_len = min_input_len
        self.node_config = node_config or {}

    @abstractmethod
    def execute(self, state: dict) -> dict:   # mutate & return state
        ...

    def update_config(self, params: dict, overwrite=False):
        for k, v in params.items():
            if hasattr(self, k) and not overwrite:
                continue
            setattr(self, k, v)

    def get_input_keys(self, state: dict):
        keys = self._parse_input_keys(state, self.input)
        if len(keys) < self.min_input_len:
            raise ValueError(f"{self.node_name} requires >= {self.min_input_len} input keys, got {len(keys)}")
        return keys
```

### The input-key DSL (the load-bearing trick)
`input` is a boolean expression over state-key names. `&` = AND (need all), `|` = OR (first present group wins), parens group. Evaluation: strip spaces; validate balanced parens and no adjacent operators; resolve innermost parens first by replacing each `(...)` with the `|`-joined keys that matched inside; then evaluate the flat expression by scanning OR-segments left→right and returning the **first** AND-group whose every key exists in `state`. This is what lets a node adapt to whichever upstream nodes ran.

```python
import re

def _parse_input_keys(self, state: dict, expression: str):
    if not expression:
        raise ValueError("Empty expression.")
    expression = expression.replace(" ", "")
    if expression[0] in "&|" or expression[-1] in "&|" or any(s in expression for s in ("&&","||","&|","|&")):
        raise ValueError("Invalid operator usage.")
    if expression.count("(") != expression.count(")"):
        raise ValueError("Unbalanced parentheses.")

    def eval_simple(exp):                         # no parens: "a&b|c"
        for or_seg in exp.split("|"):
            ands = or_seg.split("&")
            if all(k.strip() in state for k in ands):
                return [k.strip() for k in ands if k.strip() in state]
        return []

    def eval_expr(exp):
        while "(" in exp:
            start = exp.rfind("("); end = exp.find(")", start)
            inner = eval_simple(exp[start+1:end])
            exp = exp[:start] + "|".join(inner) + exp[end+1:]
        return eval_simple(exp)

    result = eval_expr(expression)
    if not result:
        raise ValueError(f"No state keys matched '{expression}'. State keys: {list(state)}")
    # de-dupe, preserve order
    seen = []
    for k in result:
        if k not in seen: seen.append(k)
    return seen
```
Real expressions in use: FetchNode `"url | local_dir"`, ParseNode `"doc"`, GenerateAnswer `"user_prompt & (relevant_chunks | parsed_doc | doc)"`, conditional retry `"answer"`.

### The engine (`BaseGraph`)
```python
import time

class BaseGraph:
    def __init__(self, nodes, edges, entry_point, graph_name="Custom"):
        self.nodes = nodes
        self.raw_edges = edges
        self.edges = self._create_edges(set(edges))     # {from_name: to_name} for normal nodes
        self.entry_point = entry_point.node_name
        self.graph_name = graph_name
        self._set_conditional_node_edges()

    def _create_edges(self, edges):
        d = {}
        for frm, to in edges:
            if frm.node_type != "conditional_node":     # conditional routing handled separately
                d[frm.node_name] = to.node_name
        return d

    def _set_conditional_node_edges(self):
        for node in self.nodes:
            if node.node_type == "conditional_node":
                outs = [(f, t) for f, t in self.raw_edges if f.node_name == node.node_name]
                if len(outs) != 2:
                    raise ValueError(f"ConditionalNode '{node.node_name}' must have exactly two outgoing edges.")
                node.true_node_name  = outs[0][1].node_name
                node.false_node_name = outs[1][1].node_name if outs[1][1] is not None else None

    def _get_node_by_name(self, name):
        return next(n for n in self.nodes if n.node_name == name)

    def _next(self, node, result):
        if node.node_type == "conditional_node":
            names = {n.node_name for n in self.nodes}
            if result in names: return result
            if result is None:  return None
            raise ValueError(f"Conditional returned unknown node '{result}'")
        return self.edges.get(node.node_name)

    def execute(self, initial_state):
        state = initial_state
        current = self.entry_point
        exec_info = []
        while current:
            node = self._get_node_by_name(current)
            t0 = time.time()
            try:
                # wrap in a token-counting callback here (see accounting note)
                result = node.execute(state)
                exec_info.append({"node_name": node.node_name, "exec_time": time.time() - t0})
                current = self._next(node, result)
            except Exception as e:
                # log {graph_name, source, prompt, schema, model, error_node: node.node_name, exception}
                raise
        return state, exec_info
```

### Conditional node (enables retry/branch without engine-level loops)
A conditional node's `execute` returns a **node name string** (or `None`). It typically evaluates a predicate against a state key and picks `self.true_node_name` / `self.false_node_name`. Example use: after answer generation, `condition='not answer or answer=="NA"'` → if true route to a regenerate node, else `None` (stop).

## Data contracts
- **state**: untyped `dict[str, Any]`. Convention keys: `user_prompt`, `url`/`local_dir`, `doc`, `parsed_doc`, `relevant_chunks`, `urls`, `results`, `answer`, `generated_code`. Document these — nothing enforces them.
- **edge**: tuple `(from_node_instance, to_node_instance)`; `to` may be `None` to mark a conditional's terminal branch.
- **node.output**: list of state keys the node promises to write (engine doesn't verify; nodes do `state.update({self.output[0]: value})`).
- **exec_info**: `list[dict]` with per-node `{node_name, exec_time, total_tokens?, prompt_tokens?, completion_tokens?, total_cost_USD?}` + a final `"TOTAL RESULT"` aggregate row.

## Dependencies & assumptions
- Pure Python + stdlib for the engine itself. No graph library.
- Token/cost accounting in the original uses a LangChain callback manager (`get_openai_callback`-style) keyed by the LLM instance. Swappable: any per-call usage accumulator works. If you don't use LangChain, capture usage from your own LLM client's response metadata.
- Optional alt-runner: the original can delegate to "Burr" for state-machine tracing. Not required — the standard loop is the spine.

## To port this, you need:
- [ ] A `BaseNode` ABC with `execute(state)->state`, `input`/`output`/`node_config`, `update_config`, `get_input_keys`.
- [ ] The boolean input-key parser (copy `_parse_input_keys` above).
- [ ] A `BaseGraph` with `_create_edges`, conditional-edge wiring, the `execute` while-loop, `_next` routing.
- [ ] A naming convention doc for state keys your nodes share.
- [ ] (Optional) a per-node usage/cost accumulator and a structured failure logger that records the failing node name.

## Gotchas
- **Untyped shared state**: any node can overwrite any key. Bugs surface as "missing key" far downstream. Mitigate with the input-key validation and consistent naming.
- **Conditional nodes must have exactly 2 outgoing edges** or construction raises. Order matters: first edge = true target, second = false target. A `None` `to` marks "stop on this branch."
- **No cycle protection in the engine itself** — a conditional that always routes back creates an infinite loop. Retry loops rely on the predicate eventually flipping (or a max-attempts guard you add).
- **Entry point must be the first node** or you get a warning (the original only warns, doesn't fail).
- **`execute` mutates the passed-in dict** and also returns it. Don't share one state dict across concurrent runs.
- **The input DSL rejects adjacent bare keys** (two state keys with no operator) and unbalanced parens at parse time — good, but it means malformed `input` strings fail at run time, not construction.

## Origin (reference only)
Repo: https://github.com/ScrapeGraphAI/Scrapegraph-ai
- `scrapegraphai/graphs/base_graph.py` — `BaseGraph`, edge building, conditional wiring, `_execute_standard` loop, token accounting, `append_node`.
- `scrapegraphai/nodes/base_node.py` — `BaseNode`, `update_config`, `get_input_keys`, `_parse_input_keys` (the DSL).
- `scrapegraphai/nodes/conditional_node.py` — the branching node type (predicate → true/false node name).
