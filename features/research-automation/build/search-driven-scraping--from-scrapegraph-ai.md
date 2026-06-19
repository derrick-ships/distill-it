# Search-Driven Scraping (build spec) — distilled from scrapegraph-ai

## Summary
Build a "question → answer from the web" pipeline (no URL needed) as a 3-node graph on the [[graph-execution-engine--from-scrapegraph-ai]]: (1) LLM rewrites the prompt into a search query and runs a pluggable web search → top-N URLs; (2) a "graph iterator" node runs a full [[smart-scraper-pipeline--from-scrapegraph-ai]] on **each** URL → list of per-page answers; (3) a merge node consolidates them into one answer. Expose `get_considered_urls()` for citations. Composition is the trick: a node runs other graphs.

## Core logic (inlined)

### The SearchGraph (assembly)
```python
class SearchGraph(AbstractGraph):
    def __init__(self, prompt, config, schema=None):
        self.max_results = config.get("max_results", 3)
        self.copy_config = safe_deepcopy(config)      # sub-graphs get an independent config
        self.copy_schema = deepcopy(schema)
        self.considered_urls = []
        super().__init__(prompt, config, schema)

    def _create_graph(self):
        search_internet_node = SearchInternetNode(
            input="user_prompt", output=["urls"],
            node_config={"llm_model": self.llm_model, "max_results": self.max_results,
                         "loader_kwargs": self.loader_kwargs,
                         "search_engine": self.copy_config.get("search_engine"),     # default "duckduckgo"
                         "serper_api_key": self.copy_config.get("serper_api_key")})
        graph_iterator_node = GraphIteratorNode(
            input="user_prompt & urls", output=["results"],
            node_config={"graph_instance": SmartScraperGraph, "scraper_config": self.copy_config},
            schema=self.copy_schema)
        merge_answers_node = MergeAnswersNode(
            input="user_prompt & results", output=["answer"],
            node_config={"llm_model": self.llm_model, "schema": self.copy_schema})
        return BaseGraph(
            nodes=[search_internet_node, graph_iterator_node, merge_answers_node],
            edges=[(search_internet_node, graph_iterator_node),
                   (graph_iterator_node, merge_answers_node)],
            entry_point=search_internet_node, graph_name=self.__class__.__name__)

    def run(self):
        self.final_state, self.execution_info = self.graph.execute({"user_prompt": self.prompt})
        self.considered_urls = self.final_state.get("urls", [])
        return self.final_state.get("answer", "No answer found.")

    def get_considered_urls(self): return self.considered_urls
```

### Node 1 — query rewrite + search
```python
class SearchInternetNode(BaseNode):
    def __init__(self, input, output, node_config=None, node_name="SearchInternet"):
        super().__init__(node_name, "node", input, output, 1, node_config)
        self.llm_model = node_config["llm_model"]
        self.search_engine = node_config.get("search_engine") or "duckduckgo"
        self.serper_api_key = node_config.get("serper_api_key")
        self.max_results = node_config.get("max_results", 3)
        self.proxy = node_config.get("loader_kwargs", {}).get("proxy")

    def execute(self, state):
        user_prompt = state[self.get_input_keys(state)[0]]
        chain = (PromptTemplate(template=TEMPLATE_SEARCH_INTERNET, input_variables=["user_prompt"])
                 | self.llm_model | CommaSeparatedListOutputParser())
        search_query = chain.invoke({"user_prompt": user_prompt})[0]    # take first query
        urls = search_on_web(query=search_query, max_results=self.max_results,
                             search_engine=self.search_engine, proxy=self.proxy,
                             serper_api_key=self.serper_api_key)
        if not urls: raise ValueError("Zero results found for the search query.")
        state.update({self.output[0]: urls}); return state
```

### Node 2 — fan out SmartScraper over each URL (where parallelism lives)
```python
# GraphIteratorNode (essence): for each url, build node_config["graph_instance"](
#     prompt=state["user_prompt"], source=url, config=scraper_config, schema=schema).run()
# Collect answers into state["results"]. Runs them concurrently (asyncio/threads).
```

### Node 3 — merge per-page answers into one (same shape as the map-reduce merge, one level up).

## Data contracts
- **Constructor**: `SearchGraph(prompt: str, config: dict, schema=None)` — note: **no source**.
- **config additions**: `{"max_results": int (default 3), "search_engine": "duckduckgo"|"google"|..., "serper_api_key": str?}` + everything SmartScraper needs (it's passed through to sub-graphs).
- **state**: seeded `{"user_prompt": prompt}`; node1→`urls: list[str]`; node2→`results: list[answer]`; node3→`answer`.
- **search_on_web(query, max_results, search_engine, proxy, serper_api_key) -> list[str]** (URLs).
- **TEMPLATE_SEARCH_INTERNET** (verbatim essence): "You are a search engine and you need to generate a search query based on the user's prompt... return a query that can be used to search the internet... return only the query string without any additional sentences... e.g. for 'What is the capital of France?' return 'capital of France'... USER PROMPT: {user_prompt}".

## Dependencies & assumptions
- A web search backend: DuckDuckGo (no key, default), Serper/Google (API key), etc. `search_on_web` abstracts them.
- The full SmartScraper pipeline + its deps (this composes them).
- `safe_deepcopy`/`deepcopy` for per-sub-graph config/schema isolation.
- A concurrency primitive in the iterator node (asyncio or threads).

## To port this, you need:
- [ ] The SmartScraper pipeline working as a standalone callable `(prompt, url, config, schema) -> answer`.
- [ ] A pluggable `search_on_web` (start with DuckDuckGo for a no-key default).
- [ ] A query-rewrite node with the strict "keywords only" prompt + a list output parser.
- [ ] An iterator node that fans the scraper across URLs concurrently and collects results.
- [ ] A merge node (reuse the map-reduce merge prompt) and a `considered_urls` accessor for citations.
- [ ] Deep-copy of config/schema before handing to sub-graphs.

## Gotchas
- **Cost scales as `max_results` × (per-page scrape cost)**, and each page scrape may itself map-reduce — so a "3 results" search can be many LLM calls. Surface this.
- **Always deep-copy config/schema for sub-graphs** — sharing one mutable config across concurrent scrapes causes races/clobbering.
- **The query-rewrite output must be parseable** (first item of a comma-separated list). Keep the prompt strict; a chatty model breaks search.
- **DuckDuckGo can rate-limit / return junk**; Serper/Google is steadier but costs. Make the backend swappable.
- **Return your sources** (`considered_urls`) — it's cheap and makes the answer auditable; don't drop it.
- **Empty search results raise** — decide whether to fail or fall back to a broader query.

## Origin (reference only)
Repo: https://github.com/ScrapeGraphAI/Scrapegraph-ai
- `scrapegraphai/graphs/search_graph.py` — `SearchGraph`, the 3-node assembly, `get_considered_urls`.
- `scrapegraphai/nodes/search_internet_node.py` — query rewrite + `search_on_web`.
- `scrapegraphai/nodes/graph_iterator_node.py` — the fan-out-over-graphs node (the real parallelism).
- `scrapegraphai/nodes/merge_answers_node.py` — final consolidation.
- `scrapegraphai/prompts/search_internet_node_prompts.py` — `TEMPLATE_SEARCH_INTERNET`.
- `scrapegraphai/utils/research_web.py` — `search_on_web` (DuckDuckGo/Serper backends).
