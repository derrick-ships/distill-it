# Agentic Browser Actions (smart-scrape) (build spec) — distilled from firecrawl

## Summary

An AI agent drives a real (hosted) browser to satisfy a natural-language instruction — click/scroll/
type/wait — before the page is captured, returning post-interaction HTML/markdown. Implemented as a
scrape-pipeline transformer (`performAgent`) that calls `smartScrape` (fire-engine hosted browser +
LLM action loop). Tiered models, cost-capped, soft-fail, disabled under zero-data-retention.

## Core logic (inlined)

### Transformer (`scrapeURL/transformers/agent.ts`)

```ts
export async function performAgent(meta, document) {
  if (!meta.internalOptions.v1Agent?.prompt) return document;          // only runs in agent mode
  if (meta.internalOptions.zeroDataRetention) {                        // ZDR: not supported
    document.warning = "Agent is not supported with zero data retention. " + (document.warning ?? "");
    return document;
  }
  const url = document.url || document.metadata.sourceURL;
  const prompt = meta.internalOptions.v1Agent.prompt;
  const sessionId = meta.internalOptions.v1Agent.sessionId;

  let result;
  try {
    result = await smartScrape({ url, prompt, sessionId, scrapeId: meta.id, costTracking: meta.costTracking });
  } catch (e) {
    if (e.message === "Cost limit exceeded") {                         // soft-fail on budget
      document.warning = "Smart scrape cost limit exceeded. " + (document.warning ?? "");
      return document;
    }
    throw e;
  }

  const html = result.scrapedPages[result.scrapedPages.length - 1].html;   // LAST page = final state
  if (hasFormatOfType(meta.options.formats, "markdown")) document.markdown = await parseMarkdown(html, {...});
  if (hasFormatOfType(meta.options.formats, "html"))     document.html = html;
  return document;
}
```

### smartScrape (`scrapeURL/lib/smartScrape.ts`)

```ts
const smartScrapeResultSchema = z.object({ scrapedPages: z.array(z.object({ html: z.string(), ... })), ... });
export async function smartScrape({ url, prompt, sessionId, scrapeId, costTracking }): Promise<SmartScrapeResult> {
  const response = await robustFetch({
    url: `${FIRE_ENGINE}/smart-scrape`,
    body: {
      url, prompt, sessionId,
      models: { primary:  { model: "gemini-2.5-pro" },     // tiered models
                secondary:{ model: "gemini-2.5-flash" } },
    },
    schema: smartScrapeResultSchema,                       // validate response shape
  });
  // record cost into costTracking (model "firecrawl/smart-scrape"); enforce cost cap -> throw "Cost limit exceeded"
  return response;
}
```

## Data contracts

- **Trigger:** `internalOptions.v1Agent = { prompt: string, sessionId?: string }` on a scrape request.
- **SmartScrapeResult:** `{ scrapedPages: { html: string, ... }[], tokenUsage?: {...} }` — last element is the final state.
- **Output:** the scrape `Document` with `markdown`/`html` set from the final page (+ `warning` on cost cap / ZDR).

## Dependencies & assumptions

- **fire-engine** hosted browser with a `/smart-scrape` LLM action loop (no local equivalent in this repo).
- LLM models (Gemini 2.5 pro/flash here) — swappable. `robustFetch` (retrying HTTP). HTML→markdown converter.
- A **cost-tracking** object threaded through the scrape; a cost cap. **Env:** `FIRE_ENGINE_BETA_URL`, model keys.

## To port this, you need:

- [ ] A hosted browser that accepts (url, prompt) and runs an LLM-driven click/scroll/type/wait loop, returning per-step HTML.
- [ ] A scrape transformer that triggers on an agent prompt, takes the final page, and fills requested formats.
- [ ] Cost tracking + a cap that soft-fails (warning + best-effort page), not a hard error.
- [ ] A ZDR guard that disables agent mode and warns.

## Gotchas

- **Goal-in-words ≠ scripted actions** — this is the agentic path; firecrawl also has a deterministic `actions:[...]` list. Don't conflate.
- **Take the last page** — intermediate states are noise; the final HTML is the result.
- **Fence the cost** — agentic browsing is unbounded; cap it and degrade gracefully or it can run away.
- **ZDR incompatible** — the loop needs page state; disable + warn under zero-data-retention.
- **Hosted-browser dependency** — there's no local-only agent; self-hosters need fire-engine.

## Origin (reference only)

firecrawl/firecrawl @ `main`: `apps/api/src/scraper/scrapeURL/transformers/agent.ts` (inlined verbatim),
`apps/api/src/scraper/scrapeURL/lib/smartScrape.ts` (inlined), `.../lib/extractSmartScrape.ts`,
`apps/api/src/controllers/v2/{browser,scrape-browser}.ts`.

**Gaps to verify (cost-capped):** the fire-engine `/smart-scrape` action-loop internals; exact cost-cap
threshold; `sessionId` reuse semantics; how the deterministic `actions:[]` path differs.
