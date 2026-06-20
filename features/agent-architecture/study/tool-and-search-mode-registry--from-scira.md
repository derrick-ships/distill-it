# Tool & Search-Mode Registry — from [scira](https://github.com/zaidmukaddam/scira)

> Domain: [[_domain]] · Source: https://github.com/zaidmukaddam/scira · NotebookLM: <link once added>

## What it does

Scira has ~30 tools (web search, academic search, weather, stock charts, code execution, Reddit,
GitHub, Spotify, crypto, memory, MCP, etc.) and ~18 "search modes" the user can pick — Web, Academic,
X, Reddit, Code, Crypto, Extreme, Canvas, and so on. Each mode is really just a curated *bundle* of
tools plus a tailored system prompt. Choosing "Reddit mode" doesn't change the model; it changes which
tools the model can call and how it's told to behave.

## Why it exists

Giving a model all 30 tools at once is a recipe for confusion and wasted tokens — it'll pick wrong
tools and ignore the ones you want. Modes solve this by scoping: each mode exposes only the handful of
tools relevant to that job, and pairs them with a prompt written for that job (Reddit mode tells the
model to cite post titles; Stocks mode knows about charts). It's how one chat box becomes 18 focused
"apps" without 18 codepaths.

## How it actually works

The registry is two parallel maps keyed by mode id, both in `lib/search/group-config.ts`:

**1. `groupTools` — mode → tool-name list.** Each mode maps to a hardcoded array of tool *name
strings* (not the tool objects). Examples:
- `web` → `['web_search','greeting','code_interpreter','get_weather_data','retrieve',
  'text_translate','nearby_places_search','track_flight','movie_or_tv_search','trending_movies',
  'find_place_on_map','trending_tv','datetime','file_query_search']`
- `academic` → `['academic_search','code_interpreter','datetime','file_query_search']`
- `extreme` → `['extreme_search']`; `canvas` → `['extreme_search']` (same tools, different prompt)
- `x` → `['x_search','file_query_search']`; `reddit` → `['reddit_search','datetime','file_query_search']`
- `mcp` → `['']` (a single empty string — actual tools injected at runtime from the user's connected apps)
- `multi-agent` → `['xai_web_search','xai_x_search']` (server-side xAI tools, not SDK tools)

**2. `localGroupInstructions` — mode → system prompt.** Each mode maps to a big inline instruction
string: the persona, the rules, and (for search modes) the citation format. Canvas and Extreme share
the same tool (`extreme_search`) but have entirely different prompts — Canvas tells the model to emit
a dashboard `spec`, Extreme tells it to write deep-research prose.

`getGroupConfig(group, user)` ties them together: it validates auth/Pro for gated modes (memory,
connectors, mcp, canvas, multi-agent), **silently degrades to `web`** if the user isn't allowed, and
returns `{ tools, instructions }`. The search route destructures that and feeds it to `streamText`.

The tools themselves live in `lib/tools/*.ts` (re-exported from `lib/tools/index.ts`). Most are
**factory functions**, not bare objects — e.g. `webSearchTool(dataStream, searchProvider)` — because
they need to close over the live streaming writer or runtime config. A tool is the AI SDK shape: a
`description`, a Zod `inputSchema`, and an `execute` function. The route resolves the mode's tool-name
strings into actual instantiated tool objects inline (a `{ web_search: webSearchTool(...), ... }`
keyed object) before passing them to `streamText`.

Separately, `getSearchGroups()` in `lib/utils.ts` holds the **UI metadata** for each mode — id, name,
description, icon, and visibility flags (`requireAuth`, `requirePro`, `show`). That's purely for
rendering the mode picker; it carries no tool bindings.

## The non-obvious parts

- **Modes are data, not code.** Adding a mode = adding one entry to `groupTools` + one to
  `localGroupInstructions` + one UI metadata object. No new route, no new handler.
- **Tool names are strings until the last moment.** The registry stores names; the route instantiates
  them. This keeps the registry serializable and lets tools take runtime args at instantiation.
- **Same tools, different prompt = different product.** Canvas vs Extreme proves the prompt, not the
  toolset, defines the mode's behavior.
- **Graceful degradation is built in.** Ask for a Pro-only mode without Pro? You silently get `web`,
  not an error. Smooth UX, but a re-implementer must replicate the fallback or gated modes leak.
- **`mcp` mode's tools are `['']`** — a deliberate placeholder filled at runtime from the user's
  connected MCP servers. Looks like a bug; it's the dynamic-injection hook.

## Related
- [[multi-provider-model-gateway--from-scira]] (the sibling registry, for models)
- [[agentic-research-planning--from-scira]] (what the lone `extreme_search` tool actually does)
- [[mcp-tool-integration--from-bolt-diy]] (dynamic tool injection, related to mcp mode)
- [[ai-agent-tool-calling--from-asyar]] (a simpler tool-calling setup — good contrast)
- [[agent-output-contract--from-last30days-skill]] (constraining model behavior via contract/prompt)
