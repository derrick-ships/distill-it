# Provider-Agnostic Model Layer (build spec) — distilled from scrapegraph-ai

## Summary
Build a single `_create_llm(llm_config) -> chat_model` that turns `{"model": "<provider>/<model>", ...}` into a ready client for ~19 providers (+ local + bring-your-own-instance), and resolves the model's **max input tokens** into `self.model_token` (which sizes downstream chunking). Most providers go through one factory (`init_chat_model`); a few get bespoke wrapper classes. Optional in-memory rate limiter injected here so the whole pipeline shares one API chokepoint.

## Core logic (inlined)

```python
from langchain.chat_models import init_chat_model
from langchain_core.rate_limiters import InMemoryRateLimiter

def _create_llm(self, llm_config: dict):
    llm_params = {"streaming": False, **llm_config}
    rate = llm_params.pop("rate_limit", {})
    if rate:
        if rate.get("requests_per_second") is not None:
            llm_params["rate_limiter"] = InMemoryRateLimiter(requests_per_second=rate["requests_per_second"])
        if rate.get("max_retries") is not None:
            llm_params["max_retries"] = rate["max_retries"]

    # 1) Escape hatch: caller supplied a built client
    if "model_instance" in llm_params:
        self.model_token = llm_params["model_tokens"]   # KeyError if missing -> required
        return llm_params["model_instance"]

    known = {"openai","azure_openai","google_genai","google_vertexai","ollama","oneapi","nvidia",
             "groq","anthropic","bedrock","mistralai","hugging_face","deepseek","ernie","fireworks",
             "clod","togetherai","xai","minimax"}

    # 2) Provider parsing
    if "/" in llm_params["model"]:
        provider, model = llm_params["model"].split("/", 1)
        llm_params["model_provider"], llm_params["model"] = provider, model
    else:
        # slashless: find any provider whose token table lists this model (first wins, with warning)
        candidates = [p for p, models in models_tokens.items() if llm_params["model"] in models]
        if not candidates:
            raise ValueError("Provider not supported; pass a model_instance instead.")
        llm_params["model_provider"] = candidates[0]

    if llm_params["model_provider"] not in known:
        raise ValueError(f"Provider {llm_params['model_provider']} is not supported. "
                         f"Try a model_instance instead.")

    # 3) Token-limit resolution -> sizes chunking downstream
    if llm_params.get("model_tokens") is None:
        try:
            self.model_token = models_tokens[llm_params["model_provider"]][llm_params["model"]]
        except KeyError:
            logger.warning("Max tokens for %s/%s unknown; defaulting to 8192",
                           llm_params["model_provider"], llm_params["model"])
            self.model_token = 8192
    else:
        self.model_token = llm_params["model_tokens"]

    # 4) Construction: factory for the many, bespoke for the few
    bespoke = {"oneapi","nvidia","ernie","deepseek","togetherai","clod","xai","minimax"}
    if llm_params["model_provider"] not in bespoke:
        if llm_params["model_provider"] == "bedrock":
            llm_params["model_kwargs"] = {"temperature": llm_params.pop("temperature")}  # bedrock wants it here
        return init_chat_model(**llm_params)
    else:
        p = llm_params.pop("model_provider")
        if p == "clod":      return CLoD(**llm_params)
        if p == "deepseek":  return DeepSeek(**llm_params)
        if p == "minimax":   return MiniMax(**llm_params)
        if p == "ernie":     from langchain_community.chat_models import ErnieBotChat; return ErnieBotChat(**llm_params)
        if p == "oneapi":    return OneApi(**llm_params)
        if p == "xai":       return XAI(**llm_params)
        if p == "nvidia":    return Nvidia(**llm_params)
        if p == "togetherai":
            from langchain_together import ChatTogether
            return ChatTogether(**llm_params)
```

## Data contracts
- **llm_config** (dict): `{"model": "openai/gpt-4o", "temperature": 0, "api_key": "...", "model_tokens": int?, "rate_limit": {"requests_per_second": float, "max_retries": int}?, "model_instance": <client>?}`.
- **Output**: a chat-model client (LangChain `BaseChatModel`-compatible).
- **Side effect**: sets `self.model_token: int` — consumed as the chunk size by the parse node.
- **models_tokens**: `dict[provider -> dict[model_name -> max_input_tokens]]`. Example entries: `openai: {"gpt-4o": 128000, "gpt-4o-mini": 128000, "gpt-3.5-turbo": 16385, ...}`, `anthropic: {"claude-3-5-sonnet-...": 200000, ...}`, `ollama: {"llama3": 8192, ...}`. Ship this table; it's the source of truth for chunking.

## Dependencies & assumptions
- LangChain `init_chat_model` (the one factory that builds standard providers from `model_provider` + `model` + key). If you don't use LangChain, replace with your own provider→constructor map.
- Bespoke wrapper classes for providers the factory doesn't cover (DeepSeek/MiniMax/XAI/OneApi/Nvidia/CLoD/Ernie/Together). These are thin `BaseChatModel` subclasses around OpenAI-compatible endpoints.
- `InMemoryRateLimiter` for shared rate limiting; matters because map-reduce fans out many concurrent calls.

## To port this, you need:
- [ ] A `models_tokens` table covering the models you support (provider → model → max tokens).
- [ ] A `_create_llm` that parses `<provider>/<model>`, validates against a known set, resolves token limit (with a sane default), and constructs the client.
- [ ] A factory (or provider→constructor map) for the common case + explicit branches for odd providers.
- [ ] A `model_instance` escape hatch (and require `model_tokens` alongside it).
- [ ] Optional: a rate limiter injected at construction so all calls share one limit.

## Gotchas
- **Token limit must be right** — it's the chunk size. The 8192 default is a fallback that silently degrades extraction; prefer an explicit `model_tokens` for any model not in your table.
- **Slashless model strings are ambiguous** — first matching provider wins. Encourage `provider/model` form; log when you guess.
- **Bedrock temperature lives in `model_kwargs`**, not top-level — one of several per-provider quirks you'll accumulate.
- **The "known providers" set and the token table can drift** — a model in one but not the other causes the 8192 fallback. Keep them in sync.
- **`model_instance` requires you to self-declare `model_tokens`** or it KeyErrors — by design, but easy to forget.
- **Rate limiting is opt-in**; without it, the parallel map step can trip provider rate limits on large pages.

## Origin (reference only)
Repo: https://github.com/ScrapeGraphAI/Scrapegraph-ai
- `scrapegraphai/graphs/abstract_graph.py` — `_create_llm`, the known-providers set, token resolution, `model_token`.
- `scrapegraphai/helpers/models_tokens.py` — the full provider→model→max-tokens table.
- `scrapegraphai/models/` — bespoke wrapper classes (`DeepSeek`, `MiniMax`, `XAI`, `OneApi`, `Nvidia`, `CLoD`).
