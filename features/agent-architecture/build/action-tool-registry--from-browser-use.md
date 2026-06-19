# Action / Tool Registry (build spec) — distilled from browser-use

## Summary

A decorator-based tool registry for LLM agents. `@registry.action(desc)` turns a Python function into a tool: it derives a Pydantic param schema (from an explicit model or the function signature), stores it, builds a combined `RootModel[Union[...]]` schema for the LLM's structured output, validates the model's chosen action, injects framework-only "special" params, substitutes secrets, and dispatches — normalizing the return to an `ActionResult`. Supports per-domain action filtering.

## Core logic (inlined)

### The decorator — `Registry.action(...)`
```
def action(self, description, param_model=None, domains=None, allowed_domains=None, terminates_sequence=False):
    # domains and allowed_domains are aliases; not both
    def decorator(func):
        if func.__name__ in self.exclude_actions: return func
        normalized = _normalize_action_function_signature(func, description, param_model)
        self.registry.actions[func.__name__] = RegisteredAction(
            name=func.__name__, description=description, function=normalized,
            param_model=<derived ActionModel subclass>, terminates_sequence=terminates_sequence, domains=domains)
        return func
    return decorator
```

### Signature normalization (`_normalize_action_function_signature`)
```
# reject **kwargs functions
# Type 1: first param is a BaseModel subclass OR param_model provided -> use that model as-is
# Type 2: plain typed args -> create_model(f"{func.__name__}_Params", __base__=ActionModel, **fields_from_signature)
# validate any param whose NAME is in SpecialActionParameters against its declared type (raise on mismatch)
# produce: async def normalized_wrapper(*, params=None, **kwargs)  with __signature__ rewritten to kwargs-only
```

### Data shapes
```
class RegisteredAction(BaseModel):
    name: str
    description: str
    function: Callable            # the normalized_wrapper
    param_model: type[BaseModel]  # an ActionModel subclass
    terminates_sequence: bool = False
    domains: list[str]|None = None

class ActionModel(BaseModel):     # base of every per-action model; carries get_index()/set_index()
    ...

# the universe of framework-injected params (NOT shown to the LLM):
SpecialActionParameters = { browser_session, page_extraction_llm, file_system, context, cdp_client,
                            page_url, available_file_paths, has_sensitive_data, extraction_schema }
```

### Building the LLM schema — `Registry.create_action_model(page_url=None)`
```
# Filter:
#   page_url is None -> include actions where domains is None        (for the base system prompt)
#   page_url set     -> include all actions where _match_domains(domains, url) is True (None matches all)
# Per included action, make a single-field model:
individual = create_model(f"{Name}ActionModel", __base__=ActionModel,
                          **{name: (action.param_model, Field(description=action.description))})
# 1 action  -> return it directly
# >=2        -> RootModel subclass over Union[*individual_models], renamed "ActionModel",
#               delegating get_index/set_index/model_dump to self.root   <-- avoids bare-union anyOf schema issues
```
Wire into the agent output:
```
self.ActionModel = create_action_model(page_url=...)
self.AgentOutput = AgentOutput.type_with_custom_actions(self.ActionModel)
#   -> create_model('AgentOutput', __base__=AgentOutput, action=(list[ActionModel], Field(..., min_items=1)))
# Called once at init (no url) and again each step in _update_action_models_for_page(url).
```

### Dispatch — `Tools.act(action, browser_session, ...)`
```
for action_name, params in action.model_dump(exclude_unset=True).items():   # exactly one pair
    if params is None: continue
    result = await wait_for(
        registry.execute_action(action_name, params, browser_session=..., page_extraction_llm=...,
                                file_system=..., available_file_paths=..., extraction_schema=..., sensitive_data=...),
        timeout=timeout_s)   # default 180s, env BROWSER_USE_ACTION_TIMEOUT_S
# normalize result: str -> ActionResult(extracted_content=result); None -> ActionResult(); ActionResult -> passthrough
# BrowserError -> ActionResult(error=handle_browser_error(e)); TimeoutError -> ActionResult(error="... timed out");
# other Exception -> ActionResult(error=str(e))
```

### `Registry.execute_action`
```
action = registry.actions[action_name]
validated = action.param_model(**params)                      # Pydantic validation of LLM-supplied args
if sensitive_data: validated = _replace_sensitive_data(validated, sensitive_data, current_url)
special = { browser_session, page_extraction_llm, available_file_paths,
            has_sensitive_data = (action_name=='input' and bool(sensitive_data)),
            file_system, extraction_schema,
            page_url = await browser_session.get_current_page_url(),
            cdp_client = browser_session.cdp_client }
return await action.function(params=validated, **special)     # normalized_wrapper unpacks to original call
```

### Sensitive-data substitution (`_replace_sensitive_data`)
```
# sensitive_data formats: {placeholder: value} (legacy, all domains) OR {domain_glob: {placeholder: value}} (scoped)
# recursively scan string fields of params for <secret>placeholder</secret> or bare placeholder names
# domain-scope via match_url_with_domain_pattern(current_url, glob)
# if placeholder endswith 'bu_2fa_code': value = pyotp.TOTP(secret).now()   # live 2FA
# return type(params).model_validate(processed)
```

### Domain matching & prompt description
```
_match_domains(domains, url): domains is None -> True; else any glob in domains matches url
                              (match_url_with_domain_pattern supports '*.google.com', 'yahoo.*')
ActionRegistry.get_prompt_description(page_url):
    url None -> describe only unfiltered (domains is None) actions   # system prompt
    url set  -> describe only domain-matched filtered actions        # appended per-step (unfiltered already in sys prompt)
```

## Data contracts
```
# What the LLM emits (one entry in AgentOutput.action list):
{ "<action_name>": { ...validated params... } }       # e.g. {"click_element": {"index": 42}}
# Return contract from every action: ActionResult (see agent-loop build) — str/None auto-normalized.
# Registration: @tools.action(desc, param_model=?, domains=?, terminates_sequence=?) on async/sync func.
```

Example registration:
```
@tools.action('Save models to storage', param_model=Models)        # Type 1 (explicit model)
async def save_models(params: Models, browser_session: BrowserSession): ...

@registry.action(description='Disco mode', domains=['google.com','*.google.com'])  # Type 2 + domain scope
async def disco_mode(browser_session: BrowserSession): ...
```

## Dependencies & assumptions
- Pydantic v2 (`create_model`, `RootModel`, `model_validate`, `model_dump(exclude_unset=True)`).
- An LLM layer that accepts a Pydantic type as `output_format` and enforces it (see [[multi-provider-llm-abstraction--from-browser-use]]).
- `pyotp` only if you want TOTP 2FA placeholder support (swappable/optional).
- The "special params" set is app-specific — define your own injected-service names.

## To port this, you need:
- [ ] A decorator that stores `{name -> RegisteredAction(function, description, param_model, flags)}`.
- [ ] Signature normalization: explicit-model OR synthesize a model from typed args; rewrite `__signature__` to kwargs-only.
- [ ] A registry of "special" param names that are injected at call time and excluded from the LLM schema.
- [ ] `create_action_model`: per-action single-field models combined into a `RootModel[Union]` (not a bare Union).
- [ ] A dispatcher: `model_dump(exclude_unset=True)` -> one pair -> validate -> inject specials -> call -> normalize to a result type.
- [ ] (Optional) domain-glob filtering and `<secret>` placeholder substitution.

## Gotchas
- **Bare `Union` breaks some LLM APIs** (produces `anyOf`) — wrap in a `RootModel` subclass and delegate `model_dump`/index helpers.
- **Rebuild the schema per page** if you use domain filtering; a once-at-init schema won't surface site-scoped tools.
- **`exclude_unset=True` is load-bearing** — it's what collapses the union dump to exactly the one chosen action.
- **Special params must be excluded from the model-facing schema**, or the LLM will try to fill in `browser_session` etc.
- **Validate before calling** — `action.param_model(**params)` is the safety boundary; skipping it lets malformed model output reach your function.
- **Secrets are domain-scoped** — a flat `{placeholder: value}` applies everywhere; prefer `{domain: {placeholder: value}}` to avoid leaking a credential to the wrong site.
- **`terminates_sequence` lives on the action but is enforced by the loop**, not the registry — wire both sides.

## Origin (reference only)
Repo: https://github.com/browser-use/browser-use (`main`). `browser_use/tools/registry/service.py`
(`Registry`, decorator, normalization, `create_action_model`, `execute_action`, `_replace_sensitive_data`),
`browser_use/tools/registry/views.py` (`RegisteredAction`, `ActionModel`, `ActionRegistry`, `SpecialActionParameters`),
`browser_use/tools/service.py` (`Tools`, built-in actions, `act()`), `browser_use/tools/views.py` (per-action param models),
`browser_use/agent/views.py` (`AgentOutput.type_with_custom_actions`), `examples/custom-functions/*`.
Gaps to verify if reachable: exact `multi_act` body and `_update_action_models_for_page` reassignment (file is ~4100 lines, truncated in fetch); exact `Tools.action` alias assignment.
