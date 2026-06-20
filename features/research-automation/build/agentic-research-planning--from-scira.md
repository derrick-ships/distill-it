# Agentic Research Planning (build spec) — distilled from scira

## Summary

A two-phase "deep research" tool you expose to an LLM as a single tool call. Phase A: a cheap model
produces a **structured research plan** (1–5 topics, each with 3–5 todos) via constrained output.
Phase B: a capable model runs as an **autonomous agent** (up to ~75 steps) with search/browse/code/
file tools, accumulating sources, until it calls a `done` tool. The whole thing runs *inside one
outer tool call*; the outer chat model then writes the cited answer from the returned sources. Built
on the Vercel AI SDK (`ai` package), but the pattern is SDK-agnostic.

## Core logic (inlined)

Outer chat call (the main endpoint), tools restricted to just `extreme_search` in this mode:

```ts
streamText({
  model: scira.languageModel(model),
  system: instructions,                 // Extreme-mode system prompt (deep research, cite inline)
  messages: processedMessages,
  tools: { extreme_search: extremeSearchTool(dataStream, contextFiles, extremeSearchModel, mcpTools) },
  activeTools: ['extreme_search'],
  stopWhen: stepCountIs(5),             // OUTER budget — small on purpose
  toolChoice: 'auto',
})
```

`extreme_search` tool implementation (the heart of it):

```ts
function extremeSearchTool(dataStream, contextFiles, modelId, mcpTools) {
  return tool({
    description: 'Autonomous deep-research tool. Plans then executes multi-step research.',
    inputSchema: z.object({ prompt: z.string() }),
    execute: async ({ prompt }) => {
      // ---- PHASE A: PLAN (cheap, hardcoded model) ----
      dataStream.write({ type: 'data-extreme_search',
        data: { kind: 'plan', status: { title: 'Planning research' } } });

      const { output: { plan } } = await generateText({
        model: scira.languageModel('scira-ext-1'),     // ALWAYS this model for planning
        output: Output.object({ schema: z.object({
          plan: z.array(z.object({
            title: z.string().min(10).max(70),
            todos: z.array(z.string()).min(3).max(5),
          })).min(1).max(5),
        })}),
        prompt: `Plan out the research for: ${prompt} ...`,
      });
      dataStream.write({ type: 'data-extreme_search', data: { kind: 'plan', plan } });

      // ---- PHASE B: EXECUTE (capable model, big step budget) ----
      const allSources = []; const charts = [];
      const { text } = await generateText({
        model: scira.languageModel(modelId),          // user-chosen scira-ext-1..8
        stopWhen: stepCountIs(75),                     // INNER budget — large
        system: 'You are an autonomous deep research analyst...',
        prompt: `Research the following: ${prompt}\n\nPlan:\n${JSON.stringify(plan)}`,
        tools: {
          thinking:   tool({ /* emits data-extreme_search kind:'thinking'; returns ack */ }),
          webSearch:  tool({ /* Exa search -> Exa content; push to allSources */ }),
          browsePage: tool({ /* scrape one URL via Exa/Firecrawl/Notte; push to allSources */ }),
          xSearch:    tool({ /* X/Twitter search */ }),
          codeRunner: tool({ /* Daytona sandbox Python; push chart artifacts to charts */ }),
          fileQuery:  tool({ /* vector search over contextFiles */ }),
          done:       tool({ /* no-op signal; returns {} — ends the loop */ }),
        },
      });

      return { toolResults: [], sources: allSources, charts }; // Research object -> outer model
    },
  });
}
```

The outer model receives the `Research` object as the tool result and writes the final answer,
citing `sources[].url` inline (citation rules live in the system prompt — see grounded-retrieval doc).

## Data contracts

Plan (Phase A output, Zod-enforced):
```ts
type Plan = { plan: { title: string /*10-70*/; todos: string[] /*3-5*/ }[] /*1-5*/ };
```

`Research` (tool return → outer model):
```ts
type Research = { toolResults: any[]; sources: SearchResult[]; charts: any[] };

interface SearchResult {       // the source/citation shape
  title: string; url: string; content: string; publishedDate: string;
  favicon: string; description?: string; canonical?: string;
  ogUrl?: string; finalUrl?: string; siteName?: string | null; image?: string;
}
```

Live progress events (SSE, written via `dataStream.write`):
```ts
{ type: 'data-extreme_search',
  data: { kind: 'plan'|'thinking'|'search'|'browse'|'file_query'|'code', /* + status/results */ } }
```

## Dependencies & assumptions

- **Vercel AI SDK** (`ai`): `streamText`, `generateText`, `tool`, `Output.object`, `stepCountIs`. Any
  agent framework with constrained output + a tool loop works; the two-phase split is the real idea.
- **A planning model** (cheap) and an **execution model** (capable). Scira uses two of its own
  `scira-ext-*` aliases; swap for any models.
- Search/browse backends: Exa (`exa-js`), Firecrawl, Parallel; code: Daytona sandbox. All swappable —
  the agent just needs *some* search, *some* fetch, optionally *some* code exec.
- A streaming writer (`dataStream`) to surface plan/steps live — optional but the UX depends on it.

## To port this, you need:
- [ ] An LLM SDK that supports a multi-step tool-calling loop with a configurable max-step count.
- [ ] Constrained/structured output for the planning pass (Zod or JSON-Schema mode).
- [ ] At least one web-search tool and one page-fetch tool wired as agent tools.
- [ ] A `done`-style sentinel tool (or a natural stop condition) so the agent can end early.
- [ ] A way to accumulate sources across steps (a closure array the tools push into).
- [ ] (Optional) a streaming channel to emit per-step progress events to the UI.

## Gotchas

- **Two separate step counters.** Outer loop small (5), inner agent large (75). Don't conflate them —
  putting the big budget on the outer chat loop lets the model burn tokens looping uncontrollably.
- **Planning model hardcoded.** Keep planning cheap/standard; only let users pick the execution model.
- **The agent accumulates sources via closure side-effects**, not via return values of each tool. The
  `done` tool returns nothing useful; the real payload is the `allSources`/`charts` arrays built up
  during the loop. Easy to miss.
- **`content` is truncated** before the model sees it (Exa ~3000 chars, Parallel ~1000). Plan token
  budgets accordingly.
- **Don't forget the outer→inner handoff is synchronous**: the whole 75-step research runs to
  completion *inside* one outer tool call before the outer model continues. That single tool call can
  take a long time — make sure your streaming/timeout/keep-alive handles it (see resumable-streaming).

## Origin (reference only)

- Repo: https://github.com/zaidmukaddam/scira
- `app/api/search/route.ts` (outer `streamText`, `stopWhen: stepCountIs(5)`; note: file mislabeled
  `/app/api/chat/route.ts` in its own line-1 comment), `lib/tools/extreme-search.ts` (both phases),
  `lib/search/group-config.ts` (Extreme mode → `['extreme_search']`).
- **Verify before relying on:** the inner `webSearch/browsePage/xSearch/codeRunner/done` input schemas
  and exact return shapes were confirmed to emit `data-extreme_search` events but not read field-by-
  field; confirm against `lib/tools/extreme-search.ts` if you need them exact.
