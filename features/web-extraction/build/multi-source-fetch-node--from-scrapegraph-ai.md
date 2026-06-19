# Multi-Source Fetch Node (build spec) — distilled from scrapegraph-ai

## Summary
Build the pipeline's input-normalization step: one node that turns any of {live URL, local HTML string, PDF/CSV/JSON/XML/MD file, directory of those} into a list of `Document` objects in the shared state under `doc`. Dispatch on the **input key name** (resolved by the engine's input DSL), not content sniffing. For web URLs, offer four interchangeable fetch backends (plain `requests`, headless Chromium, BrowserBase, Scrape.do). For LLM-bound HTML, convert to Markdown to cut tokens. Detect blank pages and raise.

## Core logic (inlined)

```python
class FetchNode(BaseNode):
    def __init__(self, input, output, node_config=None, node_name="Fetch"):
        super().__init__(node_name, "node", input, output, 1, node_config)
        c = node_config or {}
        self.headless     = c.get("headless", True)
        self.use_soup     = c.get("use_soup", False)        # True -> plain requests path
        self.loader_kwargs= c.get("loader_kwargs", {})
        self.llm_model    = c.get("llm_model", {})
        self.force        = c.get("force", False)
        self.script_creator = c.get("script_creator", False)
        self.timeout      = c.get("timeout", 30)            # None = no timeout
        self.cut          = c.get("cut", True)
        self.browser_base = c.get("browser_base")           # {"api_key","project_id"} or None
        self.scrape_do    = c.get("scrape_do")              # {"api_key", ...} or None
        self.storage_state= c.get("storage_state")          # Playwright saved session or None

    def execute(self, state):
        keys = self.get_input_keys(state)         # DSL resolves which source key is present
        source = state[keys[0]]
        input_type = keys[0]

        file_handlers = {"pdf","csv","json","xml","md"}
        dir_handlers  = {"json_dir","xml_dir","csv_dir","pdf_dir","md_dir"}

        if input_type in dir_handlers:            # contents assumed pre-collected
            state.update({self.output[0]: [source]}); return state
        if input_type in file_handlers:
            state.update({self.output[0]: self.load_file_content(source, input_type)}); return state
        if input_type == "local_dir":             # a local HTML string
            return self.handle_local_source(state, source)
        if input_type == "url":
            return self.handle_web_source(state, source)
        raise ValueError(f"Invalid input type: {input_type}")
```

### File loaders
```python
def load_file_content(self, source, input_type):
    if input_type == "pdf":
        loader = PyPDFLoader(source)
        if self.timeout is None: return loader.load()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:   # enforce timeout on blocking load
            try: return ex.submit(loader.load).result(timeout=self.timeout)
            except concurrent.futures.TimeoutError:
                raise TimeoutError(f"PDF parsing exceeded timeout of {self.timeout}s")
    if input_type == "csv":
        import pandas as pd
        return [Document(page_content=str(pd.read_csv(source)), metadata={"source":"csv"})]
    if input_type == "json":
        with open(source, encoding="utf-8") as f:
            return [Document(page_content=str(json.load(f)), metadata={"source":"json"})]
    if input_type in ("xml","md"):
        with open(source, encoding="utf-8") as f:
            return [Document(page_content=f.read(), metadata={"source":input_type})]
```

### Web path — four backends + Markdown conversion
```python
def handle_web_source(self, state, source):
    if self.use_soup:                                            # 1) plain requests
        resp = requests.get(source, timeout=self.timeout) if self.timeout else requests.get(source)
        if resp.status_code == 200:
            if not resp.text.strip(): raise ValueError("No HTML body content found in the response.")
            parsed = cleanup_html(resp, source) if not self.cut else resp.text
            if isinstance(self.llm_model, (ChatOpenAI, AzureChatOpenAI)) and not self.script_creator:
                parsed = convert_to_md(source, parsed)
            document = [Document(page_content=parsed)]
    else:
        loader_kwargs = dict(self.loader_kwargs)
        if "timeout" not in loader_kwargs and self.timeout is not None:
            loader_kwargs["timeout"] = self.timeout
        if self.browser_base:                                   # 2) hosted headless browser
            from ...docloaders.browser_base import browser_base_fetch
            data = browser_base_fetch(self.browser_base["api_key"], self.browser_base["project_id"], [source])
            document = [Document(page_content=c, metadata={"source": source}) for c in data]
        elif self.scrape_do:                                    # 3) proxy/scraping API
            from ...docloaders.scrape_do import scrape_do_fetch
            data = scrape_do_fetch(self.scrape_do["api_key"], source, ...)   # optional use_proxy/geoCode/super_proxy
            document = [Document(page_content=data, metadata={"source": source})]
        else:                                                   # 4) default: real Chromium (Playwright)
            loader = ChromiumLoader([source], headless=self.headless,
                                    storage_state=self.storage_state, **loader_kwargs)
            document = loader.load()

        if not document or not document[0].page_content.strip():
            raise ValueError("No HTML body content found in the document fetched by ChromiumLoader.")
        parsed = document[0].page_content
        if isinstance(self.llm_model, (ChatOpenAI, AzureChatOpenAI)) and not self.script_creator:
            parsed = convert_to_md(document[0].page_content, parsed)

    compressed = [Document(page_content=parsed, metadata={"source":"html file"})]
    state["doc"] = document                  # raw fetched
    state.update({self.output[0]: compressed})   # cleaned/markdown
    return state
```

## Data contracts
- **Input**: `input="url | local_dir"` (or any of the file/dir keys). Output: `["doc"]`.
- **state in**: one of `url|local_dir|pdf|csv|json|xml|md|*_dir` → a path/string/URL.
- **state out**: `state["doc"]` = list[Document] (raw); `state[output[0]]` = list[Document] (cleaned/markdown). Often the same key name (`doc`) — the cleaned one wins for `output[0]`, raw is also kept under `"doc"` on the web path.
- **Document**: LangChain `Document(page_content: str, metadata: dict)`. Any `{content, metadata}` shape works.
- **Markdown conversion gate**: only when `llm_model` is OpenAI/Azure-OpenAI family AND not `script_creator` (also influenced by `force`, `openai_md_enabled`).

## Dependencies & assumptions
- `requests` (soup path), Playwright/Chromium (default path), `pypdf`/PyPDFLoader, `pandas` (CSV, lazy import).
- Optional commercial services: BrowserBase (`pip install browserbase`), Scrape.do (API key) for anti-bot/proxy.
- `convert_to_md(url_or_html, html?)` — HTML→Markdown; `cleanup_html(resp, source)` — strip noise. Swap for any HTML→MD (e.g. markdownify/Readability) — see [[html-cleanup--from-llm-scraper]].
- `storage_state` = a Playwright `storage_state` (cookies + localStorage JSON) for authenticated scraping.

## To port this, you need:
- [ ] A `Document`-like `{page_content, metadata}` type and a node that writes `doc` to shared state.
- [ ] Dispatch keyed on the resolved input-key name (relies on the engine's input DSL).
- [ ] At least one web backend; add Chromium/Playwright for JS sites, and a proxy service only if you hit bot protection.
- [ ] An HTML→Markdown converter and a blank-page guard (raise on empty/whitespace).
- [ ] File loaders for whatever local formats you support (PDF/CSV/JSON/XML/MD).

## Gotchas
- **Blank pages from JS sites**: Chromium may return before content renders. The empty-check raises — keep it; consider a wait-for-selector in `loader_kwargs`.
- **Timeout on PDF parsing is enforced via a thread** because `PyPDFLoader.load()` is blocking and ignores timeouts otherwise.
- **Markdown gate is model-family-specific** — non-OpenAI models get raw HTML by default, which can balloon tokens. Decide deliberately for your models.
- **Two representations in state** can confuse downstream nodes; the input DSL (`relevant_chunks | parsed_doc | doc`) exists precisely to pick the best available — preserve that fallback ordering.
- **`use_soup` path skips JS** entirely — fine for static pages, useless for SPAs.
- **Auth via `storage_state`**: sessions expire; refresh the saved state or scrapes silently fall back to logged-out content.

## Origin (reference only)
Repo: https://github.com/ScrapeGraphAI/Scrapegraph-ai
- `scrapegraphai/nodes/fetch_node.py` — `FetchNode.execute`, all handlers, the four web backends, the markdown gate.
- `scrapegraphai/docloaders/chromium.py` — `ChromiumLoader` (Playwright); `.../browser_base.py`, `.../scrape_do.py` — the commercial backends.
- `scrapegraphai/utils/convert_to_md.py`, `.../cleanup_html.py` — HTML normalization.
