# SmartScraper Pipeline (build spec) — distilled from scrapegraph-ai

## Summary
Assemble a "prompt + URL → structured answer" scraper as a 3-node pipeline (Fetch → Parse → GenerateAnswer) on the [[graph-execution-engine--from-scrapegraph-ai]]. Expose it as one class: construct with `(prompt, source, config, schema?)`, `.run()` returns the answer. Make the pipeline **reshape itself** via three boolean flags (`html_mode`, `reasoning`, `reattempt`) by selecting a different (nodes, edges) entry from a lookup table over the same node instances. The `reattempt` variant adds a conditional + regenerate node for a self-healing retry loop.

## Core logic (inlined)

### The base class (provider setup + param fan-out + run)
```python
class AbstractGraph(ABC):
    def __init__(self, prompt, config, source=None, schema=None):
        self.prompt, self.source, self.config, self.schema = prompt, config, source, schema
        self.llm_model = self._create_llm(config["llm"])      # -> see provider-agnostic-model-layer spec
        self.headless = config.get("headless", True)
        self.loader_kwargs = config.get("loader_kwargs", {})
        self.timeout = config.get("timeout", 480)
        self.graph = self._create_graph()                      # subclass builds the node graph
        # push shared params into EVERY node so individual nodes stay config-light
        self.set_common_params({
            "headless": self.headless, "verbose": config.get("verbose", False),
            "loader_kwargs": self.loader_kwargs, "llm_model": self.llm_model,
            "timeout": self.timeout,
        }, overwrite=True)

    def set_common_params(self, params, overwrite=False):
        for node in self.graph.nodes:
            node.update_config(params, overwrite)

    @abstractmethod
    def _create_graph(self): ...
    @abstractmethod
    def run(self): ...
```
Note: `_create_llm` also sets `self.model_token` (the model's max input tokens) — that value sizes the parse chunks.

### The SmartScraper subclass
```python
class SmartScraperGraph(AbstractGraph):
    def __init__(self, prompt, source, config, schema=None):
        super().__init__(prompt, config, source, schema)
        self.input_key = "url" if source.startswith("http") else "local_dir"

    def _create_graph(self):
        # Escape hatch: magic model string forwards to hosted API instead of running locally
        if self.llm_model == "scrapegraphai/smart-scraper":
            from ...integrations import extract as sgai_extract
            return sgai_extract(api_key=self.config.get("api_key"),
                                url=self.source, prompt=self.prompt, schema=self.schema)

        fetch_node = FetchNode(
            input="url | local_dir", output=["doc"],
            node_config={"llm_model": self.llm_model, "force": self.config.get("force", False),
                         "cut": self.config.get("cut", True),
                         "loader_kwargs": self.config.get("loader_kwargs", {}),
                         "browser_base": self.config.get("browser_base"),
                         "scrape_do": self.config.get("scrape_do"),
                         "storage_state": self.config.get("storage_state")})

        parse_node = ParseNode(
            input="doc", output=["parsed_doc"],
            node_config={"llm_model": self.llm_model, "chunk_size": self.model_token})

        generate_answer_node = GenerateAnswerNode(
            input="user_prompt & (relevant_chunks | parsed_doc | doc)", output=["answer"],
            node_config={"llm_model": self.llm_model,
                         "additional_info": self.config.get("additional_info"),
                         "schema": self.schema})

        # retry pieces (only used when reattempt=True)
        cond_node = regen_node = None
        if self.config.get("reattempt") is True:
            cond_node = ConditionalNode(
                input="answer", output=["answer"], node_name="ConditionalNode",
                node_config={"key_name": "answer", "condition": 'not answer or answer=="NA"'})
            regen_node = GenerateAnswerNode(
                input="user_prompt & answer", output=["answer"],
                node_config={"llm_model": self.llm_model,
                             "additional_info": REGEN_ADDITIONAL_INFO, "schema": self.schema})

        reasoning_node = None
        if self.config.get("reasoning"):
            reasoning_node = ReasoningNode(
                input="user_prompt & (relevant_chunks | parsed_doc | doc)", output=["answer"],
                node_config={"llm_model": self.llm_model,
                             "additional_info": self.config.get("additional_info"), "schema": self.schema})

        # (html_mode, reasoning, reattempt) -> {nodes, edges}  -- 8 variants over the SAME node objects
        variants = {
          (False, False, False): {"nodes":[fetch_node, parse_node, generate_answer_node],
                                  "edges":[(fetch_node,parse_node),(parse_node,generate_answer_node)]},
          (True,  False, False): {"nodes":[fetch_node, generate_answer_node],
                                  "edges":[(fetch_node,generate_answer_node)]},  # html_mode skips Parse
          (False, True,  False): {"nodes":[fetch_node, parse_node, reasoning_node, generate_answer_node],
                                  "edges":[(fetch_node,parse_node),(parse_node,reasoning_node),
                                           (reasoning_node,generate_answer_node)]},
          (False, False, True):  {"nodes":[fetch_node, parse_node, generate_answer_node, cond_node, regen_node],
                                  "edges":[(fetch_node,parse_node),(parse_node,generate_answer_node),
                                           (generate_answer_node,cond_node),
                                           (cond_node,regen_node),(cond_node,None)]},  # retry loop
          # ... the remaining 4 combos follow the same pattern (see Origin)
        }
        cfg = variants.get((self.config.get("html_mode", False),
                            self.config.get("reasoning", False),
                            self.config.get("reattempt", False)))
        if cfg:
            return BaseGraph(nodes=cfg["nodes"], edges=cfg["edges"],
                             entry_point=fetch_node, graph_name=self.__class__.__name__)
        return BaseGraph(nodes=[fetch_node, parse_node, generate_answer_node],   # default
                         edges=[(fetch_node,parse_node),(parse_node,generate_answer_node)],
                         entry_point=fetch_node, graph_name=self.__class__.__name__)

    def run(self):
        inputs = {"user_prompt": self.prompt, self.input_key: self.source}
        self.final_state, self.execution_info = self.graph.execute(inputs)
        return self.final_state.get("answer", "No answer found.")
```

The retry edge `(cond_node, None)` is the conditional's "false" branch = stop. `(cond_node, regen_node)` is "true" (answer empty/NA) = regenerate. The conditional reads `key_name="answer"` and evaluates `condition` against state.

## Data contracts
- **Constructor**: `SmartScraperGraph(prompt: str, source: str, config: dict, schema: type[BaseModel] | None)`.
- **config** (dict): `{"llm": {"model": "<provider>/<model>", ...}, "headless": bool, "verbose": bool, "timeout": int, "html_mode": bool, "reasoning": bool, "reattempt": bool, "force": bool, "cut": bool, "loader_kwargs": {...}, "additional_info": str|None, "browser_base"/"scrape_do"/"storage_state": ...}`.
- **state seeded by run()**: `{"user_prompt": prompt, "url"|"local_dir": source}`.
- **state evolution**: Fetch→`doc`; Parse→`parsed_doc`; GenerateAnswer→`answer`.
- **return**: `final_state["answer"]` — a dict (matching `schema` if given) or `"No answer found."`.
- **REGEN_ADDITIONAL_INFO** (real text prepended to the retry prompt): `"You are a scraper and you have just failed to scrape the requested information from a website. I want you to try again and provide the missing informations."`

## Dependencies & assumptions
- Depends on the engine spec (`BaseGraph`/`BaseNode`/`ConditionalNode`), the fetch node, parse node, and answer node specs.
- `model_token` (model max input tokens) must be known before building Parse — it's the chunk size. Comes from the provider layer.
- Pydantic for `schema`. LangChain LLM clients in the original, but any client works if the answer node is adapted.

## To port this, you need:
- [ ] The graph engine + the three nodes (fetch/parse/generate) implemented to the node contract.
- [ ] A base class that builds the LLM, sets `model_token`, builds the graph, and fans common params into all nodes.
- [ ] A `(flags) -> (nodes, edges)` lookup so feature flags reshape the pipeline without touching node code.
- [ ] A conditional node type + a regenerate node for the `reattempt` retry loop.
- [ ] `input_key` auto-detection (http → url, else local path).

## Gotchas
- **Chunk size is implicit in the model choice.** Switching models changes `model_token` changes chunking changes cost/quality. Make this visible.
- **`html_mode=True` sends whole pages** — fine for small pages, will exceed context / cost a lot on big ones. It's a deliberate fidelity-vs-cost dial, not a default.
- **The retry loop can double your LLM spend** on hard pages (full re-run). Guard with a max-attempts notion if you generalize beyond one retry.
- **`"NA"` is a magic sentinel**: the answer prompts instruct the model to emit `"NA"` when it can't find something, and the conditional keys off it. If you change the prompt's "not found" convention, update the condition string too.
- **Variation matrix must be exhaustive** for the flag combos you support, or you silently fall back to the default 3-node pipeline (ignoring flags). The original enumerates all 8.
- **`set_common_params(overwrite=True)`** stomps node-local config with the shared LLM/timeout — intended, but means per-node overrides of those keys won't survive unless you change the overwrite policy.

## Origin (reference only)
Repo: https://github.com/ScrapeGraphAI/Scrapegraph-ai
- `scrapegraphai/graphs/smart_scraper_graph.py` — `SmartScraperGraph`, the full 8-entry `graph_variation_config`, `run`.
- `scrapegraphai/graphs/abstract_graph.py` — `AbstractGraph`, `set_common_params`, `_create_llm`, `model_token`.
- `scrapegraphai/prompts/generate_answer_node_prompts.py` — `REGEN_ADDITIONAL_INFO`.
