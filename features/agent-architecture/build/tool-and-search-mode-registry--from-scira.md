# Tool & Search-Mode Registry (build spec) — distilled from scira

## Summary

Scope an LLM's tools per "mode" instead of exposing everything at once. Two parallel maps keyed by a
mode id: `mode → tool-name[]` and `mode → systemPrompt`. A resolver validates access, degrades gated
modes to a default, and returns `{ tools, instructions }`. The route turns tool-*names* into
instantiated tool objects (factories closing over runtime config) and passes them to the model. UI
metadata for the mode picker is a third, separate map. Built on the Vercel AI SDK `tool()` shape;
the registry pattern is SDK-agnostic.

## Core logic (inlined)

**Registry — `lib/search/group-config.ts`:**

```ts
const groupTools = {
  web:         ['web_search','greeting','code_interpreter','get_weather_data','retrieve',
                'text_translate','nearby_places_search','track_flight','movie_or_tv_search',
                'trending_movies','find_place_on_map','trending_tv','datetime','file_query_search'],
  academic:    ['academic_search','code_interpreter','datetime','file_query_search'],
  youtube:     ['youtube_search','datetime','file_query_search'],
  spotify:     ['spotify_search','datetime','file_query_search'],
  code:        ['code_context','file_query_search'],
  reddit:      ['reddit_search','datetime','file_query_search'],
  github:      ['github_search','datetime','file_query_search'],
  stocks:      ['stock_chart','currency_converter','datetime','file_query_search'],
  crypto:      ['coin_data','coin_ohlc','coin_data_by_contract','datetime','file_query_search'],
  chat:        ['file_query_search'],
  extreme:     ['extreme_search'],
  x:           ['x_search','file_query_search'],
  memory:      ['datetime','search_memories','add_memory','file_query_search'],
  connectors:  ['connectors_search','datetime','file_query_search'],
  mcp:         [''],                                  // filled at runtime from user's MCP servers
  'multi-agent': ['xai_web_search','xai_x_search'],   // server-side xAI tools, not SDK tools
  buddy:       ['datetime','search_memories','add_memory','file_query_search'], // legacy alias
  prediction:  ['prediction_search','datetime','file_query_search'],
  canvas:      ['extreme_search'],
} as const;

const localGroupInstructions = {
  web: `...full system prompt incl. citation rules...`,
  extreme: `...deep research prose...`,
  canvas: `...output a dashboard spec block...`,
  // one entry per mode
};

export async function getGroupConfig(groupId = 'web', lightweightUser, fullUserPromise) {
  const gated = ['memory','buddy','connectors','mcp','canvas','multi-agent'];
  const proOnly = ['connectors','mcp','canvas','multi-agent'];
  if (gated.includes(groupId)) {
    if (!lightweightUser) { /* await fullUserPromise; if still null -> groupId='web' */ }
    else if (proOnly.includes(groupId) && !lightweightUser.isProUser) groupId = 'web'; // silent degrade
  }
  return { tools: groupTools[groupId], instructions: localGroupInstructions[groupId] };
}
```

**Tool shape — `lib/tools/*.ts` (factory closing over runtime config):**

```ts
export function webSearchTool(dataStream?, searchProvider = 'exa') {
  return tool({
    description: '...rules...',
    inputSchema: z.object({
      queries: z.array(z.string()).min(3),
      maxResults: z.array(z.number()).optional(),
      topics: z.array(z.enum(['general','news'])).optional(),
      quality: z.array(z.enum(['default','best'])).optional(),
      startDates: z.array(z.string().nullable().optional()).optional(),
    }),
    execute: async (args) => { /* provider strategy + fallback */ },
  });
}
// lib/tools/index.ts re-exports all tool factories.
```

**Resolution at request time (`app/api/search/route.ts`):**

```ts
const { tools: activeToolNames, instructions } = await getGroupConfig(group, lightweightUser, userPromise);
// names -> instantiated objects (only the ones this mode lists)
const streamTools = {
  web_search:        webSearchTool(dataStream, searchProvider),
  extreme_search:    extremeSearchTool(dataStream, contextFiles, extremeSearchModel, mcpDynamicTools),
  file_query_search: createFileQuerySearchTool(/* ... */),
  // ...one per tool name; MCP tools merged in for mcp/extreme modes when Pro
};
streamText({ model, system: instructions, tools: streamTools, activeTools: activeToolNames,
             stopWhen: stepCountIs(group === 'mcp' ? 50 : 5) });
```

**UI metadata (separate) — `lib/utils.ts`:**
```ts
// getSearchGroups(): [{ id, name, description, icon, show, requireAuth?, requirePro? }, ...]
// purely for rendering the mode picker; NO tool bindings here.
```

## Data contracts

- `SearchGroupId` (18): `web | x | academic | youtube | spotify | reddit | github | stocks | chat |
  extreme | memory | crypto | code | connectors | mcp | multi-agent | prediction | canvas`.
- `getGroupConfig` returns `{ tools: string[], instructions: string }`.
- A tool = `{ description: string, inputSchema: ZodSchema, execute: (args)=>Promise<any> }`.

## Dependencies & assumptions

- Vercel AI SDK `tool()` + `streamText` (`activeTools`, `stopWhen`, `stepCountIs`). Zod for schemas.
- A streaming writer threaded into tools that emit progress (`dataStream`).
- Auth/subscription info (`lightweightUser.isProUser`) for gating.

## To port this, you need:
- [ ] A `mode → tool-name[]` map and a parallel `mode → systemPrompt` map.
- [ ] Tool factories (so tools can close over per-request config like a stream writer or provider).
- [ ] A resolver that checks access, **degrades gated modes to a safe default**, returns `{tools,prompt}`.
- [ ] A name→object resolution step at the call site (keep the registry storing names, not objects).
- [ ] A separate UI-metadata map for the mode picker (icons, labels, visibility) — no tool bindings.
- [ ] (Optional) a dynamic-injection hook (the `['']` placeholder) for runtime tools like MCP.

## Gotchas

- **Don't store tool objects in the registry** — store names. Tools need per-request args (stream
  writer, provider), so they must be instantiated at the call site, not at module load.
- **Silent degradation must be replicated.** Gated modes fall back to `web` rather than erroring; skip
  this and either users hit errors or gated tools leak to non-Pro users.
- **Same toolset ≠ same mode.** Canvas and Extreme share `['extreme_search']` but differ entirely by
  prompt. The prompt map is not optional flavor — it's half the registry.
- **`mcp` mode's `['']`** is intentional: a placeholder replaced at runtime by the user's connected
  MCP tools. Treat empty/placeholder entries as injection points, not dead config.
- **`stopWhen` varies by mode** (mcp gets 50 steps, others 5). Step budget is part of the mode, too.
- **`multi-agent` tools aren't SDK tools** — they're xAI server-side built-ins on a different model
  call path; they won't resolve through your normal tool map.

## Origin (reference only)

- Repo: https://github.com/zaidmukaddam/scira
- `lib/search/group-config.ts` (`groupTools`, `localGroupInstructions`, `getGroupConfig`),
  `lib/tools/*.ts` + `lib/tools/index.ts` (tool factories), `lib/utils.ts` (`getSearchGroups` UI
  metadata, `SearchGroupId`), `app/api/search/route.ts` (name→object resolution, `stopWhen` per mode).
- **Verify before relying on:** the exact inline `streamTools` object that maps every name→factory in
  `route.ts` was only partially read (large file); confirm the full mapping if you need every tool.
