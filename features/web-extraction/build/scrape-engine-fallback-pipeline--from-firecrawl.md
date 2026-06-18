# Scrape Engine + Fallback Pipeline (build spec) — distilled from firecrawl

## Summary

URL → clean output (markdown / cleaned HTML / screenshot / links / structured JSON) via a
**capability-driven engine fallback chain** followed by a **fixed-order transformer stack**. Request
options become a set of feature flags; `buildFallbackList` orders the engines that satisfy them; a loop
tries each engine until one succeeds (or `NoEnginesLeftError`), under a hard abort timeout. Then a fixed
transformer pipeline derives every requested format from the raw HTML. A `maxAge`-based index cache can
serve a recent copy without re-fetching.

## Core logic (inlined)

### Engine roster + capability map (`scrapeURL/engines/index.ts`)

```ts
export type Engine =
  | "fire-engine;chrome-cdp" | "fire-engine(retry);chrome-cdp"
  | "fire-engine;chrome-cdp;stealth" | "fire-engine(retry);chrome-cdp;stealth"
  | "fire-engine;tlsclient" | "fire-engine;tlsclient;stealth"
  | "playwright" | "fetch" | "pdf" | "docx"
  | "index" | "index;documents" | "wikipedia" | "x-twitter";

// engine name -> implementation fn
const engineHandlers = {
  "fire-engine;chrome-cdp": scrapeURLWithFireEngineChromeCDP,   // + retry/stealth variants
  "fire-engine;tlsclient":  scrapeURLWithFireEngineTLSClient,
  playwright: scrapeURLWithPlaywright,   // self-hosted headless
  fetch:      scrapeURLWithFetch,        // plain HTTP, fastest
  pdf:        scrapeURLWithPDF, docx: scrapeURLWithDocX,
  index:      scrapeURLWithIndex,        // serve cached/indexed copy
  wikipedia:  scrapeURLWithWikipedia, "x-twitter": scrapeURLWithXTwitter,
};

// Each engine declares feature support + cost/quality weighting:
const engineOptions: Record<Engine, { features: {[F in FeatureFlag]: boolean}, quality: number }> = { ... };
// FeatureFlag examples: screenshot, "screenshot@fullScreen", actions, waitFor, stealthProxy, pdf, docx, ...
```

### Feature flags from the request, then the fallback list

```ts
// 1) request options -> required feature flags
meta.featureFlags = buildFeatureFlags(url, normalizedOptions, internalOptions); // Set<FeatureFlag>

// 2) capable engines, ordered (quality/cost), filtering out engines missing required flags
const fallbackList = await buildFallbackList(meta);   // [{engine, unsupportedFeatures:Set}, ...]

// 3) actions need fire-engine -> fail fast
if (meta.featureFlags.has("actions")) {
  if (fallbackList.length === 0 || fallbackList.every(e => e.unsupportedFeatures.has("actions")))
    throw new Error("Actions require Fire Engine to be enabled.");
}
```

### The fallback loop (`scrapeURL/index.ts: scrapeURLLoop`)

```ts
const abortController = new AbortController();
const abortHandle = options.timeout !== undefined
  ? setTimeout(() => abortController.abort(new ScrapeJobTimeoutError()), options.timeout) : undefined;

const remainingEngines = [...fallbackList];
for (const { engine } of remainingEngines) {
  meta.abort.throwIfAborted();
  try {
    const result = await scrapeURLLoopIter(meta, engine, snipeAbort);   // calls engineHandlers[engine]
    // success -> run transformers, return
    return await executeTransformers(meta, result.document);
  } catch (error) {
    if (error instanceof EngineError /* or wrapped timeout */) continue;  // try next engine
    throw error;   // non-engine error: bubble up
  }
}
throw new NoEnginesLeftError(fallbackList);
```

### Transformer stack (FIXED ORDER) (`scrapeURL/transformers/index.ts`)

```ts
const transformerStack: Transformer[] = [
  deriveHTMLFromRawHTML,     // clean/sanitize raw HTML (drop unwanted els); honors onlyMainContent
  deriveMarkdownFromHTML,    // cleaned HTML -> markdown
  deriveLinksFromHTML,       // collect links (for crawl/map)
  deriveMetadataFromRawHTML, // title, description, og:, statusCode, ...
  performLLMExtract,         // if "json" format requested -> LLM structured extract (see llm-extract doc)
  removeBase64Images,        // strip inline base64 to shrink payload
  coerceFieldsToFormats,     // keep ONLY requested formats; shape final Document
];
export async function executeTransformers(meta, document) {
  for (const t of transformerStack) document = await t(meta, document);
  return document;   // each transformer: (meta, doc) => doc
}
```

## Data contracts

- **Scrape request (options):** `{ url, formats:["markdown"|"html"|"rawHtml"|"links"|"screenshot"|"screenshot@fullScreen"|"json"|...], onlyMainContent?:bool, waitFor?:ms, actions?:[{type:"click"|"scroll"|"write"|"wait"|...}], timeout?:ms, headers?, proxy?:"basic"|"stealth", maxAge?:ms (cache), location?:{country,languages}, includeTags?, excludeTags?, jsonOptions?:{schema,prompt,systemPrompt} }`.
- **Document (response):** `{ markdown?, html?, rawHtml?, links?:string[], screenshot?:url, json?:object, metadata:{ title, description, sourceURL, statusCode, error?, ...og fields, proxyUsed, creditsUsed } }`.
- **Engine result (internal):** raw HTML/bytes + status + (optional) screenshot, fed into the transformer stack.

## Dependencies & assumptions

- **Node/TypeScript + Express** API. **Playwright** for the self-hosted browser engine; **fire-engine**
  is firecrawl's *separate hosted browser service* (`FIRE_ENGINE_BETA_URL`) — actions/stealth need it.
- PDF/DOCX parsers; an index/cache store for `maxAge` cache hits.
- **Env:** `FIRE_ENGINE_BETA_URL` (enable hosted browser), proxy creds, `PLAYWRIGHT`/browser setup.
- Swappable: drop fire-engine and run playwright+fetch only (lose actions/stealth). Replace the
  cache/index engine with your own.

## To port this, you need:

- [ ] An **engine interface** `(meta) => {rawHtml, status, screenshot?}` with a capability/feature-flag declaration per engine.
- [ ] `buildFeatureFlags(options)` → `buildFallbackList(meta)` (ordered, capability-filtered).
- [ ] A **fallback loop** that tries engines in order, catching engine errors/timeouts and advancing, under a global AbortController timeout.
- [ ] A **fixed transformer stack** (clean HTML → markdown → links → metadata → optional LLM-extract → strip base64 → trim to requested formats).
- [ ] (optional) a `maxAge` cache/index engine to short-circuit re-fetches.

## Gotchas

- **Order the fallback by cost AND capability** — cheap `fetch` first, expensive stealth browser last; filtering by feature flags is what prevents "engine can't do screenshots" failures.
- **Engine errors continue; other errors bubble.** Misclassify a timeout and you either retry forever or kill a recoverable scrape (firecrawl special-cases fire-engine's internal timeout as an EngineError).
- **Transformer order is load-bearing** — markdown derives from cleaned HTML; LLM-extract needs markdown to exist; format-trim must be last or you leak `rawHtml` you didn't ask for.
- **`actions` only work on the hosted browser** — check up front and fail clearly; don't drop them silently.
- **`onlyMainContent`** lives in the HTML-cleaning step (readability-style); getting it wrong nukes real content or keeps nav chrome.
- **Hard abort timeout** must thread through every engine + transformer or a hung browser stalls the request.

## Origin (reference only)

firecrawl/firecrawl @ `main`:
`apps/api/src/scraper/scrapeURL/index.ts` (`scrapeURLLoop` fallback — inlined),
`apps/api/src/scraper/scrapeURL/engines/index.ts` (engine roster, feature map, `buildFallbackList` — inlined),
`apps/api/src/scraper/scrapeURL/transformers/index.ts` (`transformerStack`, `executeTransformers` — inlined),
plus `engines/{fetch,playwright,fireEngine,pdf,index}.ts` and `lib/{removeUnwantedElements,extractLinks,extractMetadata}.ts`.

**Gaps to verify (not deep-read, cost-capped):** exact `buildFeatureFlags` rules and per-engine
`quality` weighting; `coerceFieldsToFormats` field mapping; the fire-engine HTTP contract; PDF/DOCX
engine internals; how `maxAge`/index cache keys are computed.
