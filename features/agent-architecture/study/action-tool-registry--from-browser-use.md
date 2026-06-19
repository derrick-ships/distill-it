# Action / Tool Registry — from [browser-use](https://github.com/browser-use/browser-use)

> Domain: [[_domain]] · Source: https://github.com/browser-use/browser-use · NotebookLM: <link once added>

## What it does

This is the system that defines *what the agent is allowed to do* and turns that set of capabilities into a menu the LLM can pick from. A developer writes a plain Python function, slaps a `@tools.action("description")` decorator on it, and it instantly becomes a tool the agent can call — `click_element`, `input_text`, `go_to_url`, or anything custom like `save_to_airtable`. The registry collects all these actions, builds a strict schema from each one's parameters, hands that schema to the LLM as its structured-output format, and when the model picks an action, validates the arguments and calls the real function.

## Why it exists

An LLM agent is only as capable as its action space, and that action space needs three things at once: it has to be *easy for developers to extend* (add a tool in three lines), *safe* (the model can't pass garbage arguments), and *legible to the model* (the LLM has to understand exactly what each tool does and what it expects). The decorator-plus-Pydantic registry hits all three. The decorator is the ergonomics; Pydantic validation is the safety; and the auto-generated JSON schema is the legibility. It also lets you scope tools to specific websites, inject framework services (the browser, an extraction LLM) without exposing them to the model, and safely substitute secrets — all without the action author thinking about any of it.

## How it actually works

**Registering an action.** `@registry.action(description, ...)` wraps a function. At registration it does something clever: it inspects the function's signature and figures out the parameter schema two ways. If the first argument is a Pydantic model (or you pass `param_model=`), it uses that model directly. Otherwise it reads the plain typed arguments and *synthesizes* a Pydantic model from them on the fly. Either way the result is an `ActionModel` subclass describing exactly what the LLM must provide. The function, its description, its param model, and flags get stored as a `RegisteredAction` in a dictionary keyed by name.

**The special-parameter trick.** Real action functions need things the model should never supply — the browser session, a page-extraction LLM, the file system, the current URL. The registry knows a fixed set of "special" parameter names (`browser_session`, `page_extraction_llm`, `file_system`, `cdp_client`, `page_url`, `available_file_paths`, etc.). Any parameter with one of those names is recognized as *framework-injected* and stripped out of the schema the model sees. So the model only ever picks the "real" arguments; the plumbing is filled in at call time.

**Building the menu for the LLM.** Each step, the registry builds the action schema. For every available action it makes a one-field Pydantic model (`{action_name: ParamModel}`), then combines them. If there's only one action, it's used directly; if there are many, they're wrapped in a `Union` — but, importantly, inside a Pydantic `RootModel` rather than a bare union, because a raw union produces an `anyOf` schema that confuses some LLM APIs. This union *is* the type passed to the model as `output_format`. The agent's whole output model embeds it: `AgentOutput.action` is a `list` of these.

**Dispatching the chosen action.** When the model returns, say, `{"click_element": {"index": 42}}`, the executor does `model_dump(exclude_unset=True)` which yields exactly one `{name: params}` pair. It looks up the `RegisteredAction` by name, validates the params against that action's Pydantic model, assembles the special-context dict (browser session, current URL, extraction LLM, etc.), and calls the function — wrapped in a timeout. Whatever the function returns is normalized into an `ActionResult` (a bare string becomes `extracted_content`; `None` becomes an empty success; an `ActionResult` passes through). Errors become `ActionResult(error=…)` rather than exceptions.

**Two power features layered on top.** *Domain filtering*: an action can declare `domains=['*.google.com']`, and it only appears in the menu when the current page matches — so site-specific tools don't clutter the general action space. *Sensitive-data substitution*: before calling a function, the registry scans string arguments for `<secret>placeholder</secret>` tags and swaps in real values (domain-scoped), so the model can say "type my password here" by name without ever seeing the actual secret — and it even generates live TOTP 2FA codes for placeholders ending in `bu_2fa_code`.

## The non-obvious parts

- **The union is a `RootModel`, not a plain `Union`.** This is a deliberate workaround: Pydantic's bare `Union` serializes to `anyOf`, which several LLM structured-output APIs handle badly. Wrapping it in a `RootModel` subclass (and re-exposing `get_index`/`set_index`/`model_dump` by delegation) produces a cleaner schema and nicer debug output.
- **The action schema is rebuilt every single step**, parameterized by the current URL — once at init with no URL (for the base system prompt), then again per page so domain-scoped actions appear/disappear as the agent navigates.
- **Function signatures get rewritten.** The registry replaces each action's `__signature__` with a uniform keyword-only `(*, params=None, **kwargs)` so the executor can call any action the same way without knowing its original parameters.
- **`terminates_sequence`** is a flag on the action (used by `search`, `navigate`, etc.) that the agent loop checks to abort the rest of a multi-action batch after a page-changing move — the registry stores it, the loop enforces it.
- **Secrets never reach the model.** The placeholder-substitution pass means the prompt can reference credentials by name; the real values are injected only at execution, domain-scoped, with TOTP generation built in.
- **`context` is an untyped escape hatch.** The registry is generic over a `Context` type the user passes to the agent; that one special parameter isn't type-validated, so you can thread arbitrary app state into your custom actions.

## Related
- [[agent-loop-recovery--from-browser-use]] — calls `tools.act(action)` each step and consumes the `ActionResult`; relies on `terminates_sequence`.
- [[multi-provider-llm-abstraction--from-browser-use]] — the generated action union becomes the `output_format` schema sent to the model.
- [[indexed-dom-serialization--from-browser-use]] — action params like `index` reference the elements that layer numbers.
- See also: [[mcp-crm-server--from-auto-crm]] (exposing a product to an LLM as a set of typed tools) and [[mcp-sidecar-auto-detection--from-asyar]] (tool registration/namespacing), kindred "give the model a validated tool surface" patterns.
