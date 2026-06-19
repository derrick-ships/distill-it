# LLM Extract (map-reduce) (build spec) — distilled from firecrawl

## Summary

Prompt (+ optional JSON schema) + URL(s)/domain → one structured object, via an async map-reduce job.
Pipeline: optional prompt-rephrase → `analyzeSchemaAndPrompt` (decide **single-answer vs multi-entity**,
find multi-entity keys) → `processUrl` (expand+scrape sources) → fork: single-answer completion, OR
multi-entity (split schema, chunk docs ×50, concurrent `batchExtract`, null-aware merge, dedup, rerank) →
merge to final object. Redis-backed status steps throughout.

## Core logic (inlined)

### Orchestration spine (`lib/extract/extraction-service.ts`)

```ts
export async function performExtraction(extractId, { request, teamId, ... }) {
  // 1) optional prompt rephrase
  const rephrasedPrompt = request.prompt
    ? await generateBasicCompletion(buildRephraseToSerpPrompt(request.prompt)) : undefined;

  await updateExtract(extractId, { status: "processing", steps:[ExtractStep.INITIAL] });

  // 2) dereference + analyze the schema/prompt
  let reqSchema = request.schema ? await dereferenceSchema(request.schema) : undefined;
  const { isMultiEntity, multiEntityKeys, reasoning, keyIndicators } =
    await analyzeSchemaAndPrompt(request.urls, reqSchema, request.prompt);

  // 3) expand + scrape sources (map/discovery when given a domain)
  const urlResults = await Promise.all(request.urls.map(url =>
    processUrl({ url, prompt, schema, isMultiEntity, multiEntityKeys, ... },
      (msg) => updateExtract(extractId, { steps:[ExtractStep.MAP], ... }))));
  const links = urlResults.flat();

  // 4) FORK
  if (isMultiEntity && reqSchema) {
    const { singleAnswerSchema, multiEntitySchema } = await spreadSchemas(reqSchema, multiEntityKeys);

    // scrape docs for multi-entity, then chunk + concurrent batch-extract
    const chunkSize = 50;
    const chunks: Document[][] = [];
    for (let i=0;i<multyEntityDocs.length;i+=chunkSize) chunks.push(multyEntityDocs.slice(i,i+chunkSize));
    const sessionIds = chunks.map(() => "fc-" + crypto.randomUUID());

    for (let i=0;i<chunks.length;i++) {                       // sequential chunks, concurrent within chunk
      const chunkResults = await Promise.all(chunks[i].map(doc =>
        batchExtractPromise({ multiEntitySchema, prompt, doc, sessionId: sessionIds[i], ... })));
      // merge: dedup arrays + null-aware merge across pages
      multiEntityResult = mergeNullValObjs([multiEntityResult, ...chunkResults.map(r => r.extract)]);
    }

    // single-answer fields (the non-entity part of the schema), filled separately
    singleAnswerResult = (await singleAnswerCompletion({ singleAnswerSchema, docs, prompt, ... })).extract;
    finalResult = { ...singleAnswerResult, ...multiEntityResult };
  } else {
    // single-answer path: one completion against the whole schema
    singleAnswerResult = (await singleAnswerCompletion({ singleAnswerSchema: reqSchema, docs, prompt, ... })).extract;
    finalResult = singleAnswerResult;
  }

  await updateExtract(extractId, { status: "completed", data: finalResult, steps:[ExtractStep.COMPLETE] });
}
```

### Key helpers (`lib/extract/helpers/*`, `completions/*`)

- `analyzeSchemaAndPrompt(urls, schema, prompt)` → `{ isMultiEntity, multiEntityKeys, reasoning }` — the pivotal classifier (LLM call).
- `spreadSchemas(schema, multiEntityKeys)` → `{ singleAnswerSchema, multiEntitySchema }` — splits the schema by which keys are per-entity arrays.
- `batchExtractPromise({ multiEntitySchema, doc, prompt, sessionId })` — per-document structured extraction (the "map").
- `singleAnswerCompletion({ singleAnswerSchema, docs, prompt })` — one object from the relevant docs.
- `mergeNullValObjs(objs[])` — merge objects keeping non-null fields (prevents later empties clobbering earlier values); the "reduce".
- `deduplicateObjsArray` — dedup entity lists; `transformArrayToObj`, `mixSchemaObjs` — shape helpers.
- `dereferenceSchema(schema)` — resolve `$ref`s so the LLM sees a flat schema.
- `reranker.ts` — relevance-score documents/sections so the LLM budget targets the pages most likely to hold the answer.
- `generateBasicCompletion(prompt)` — utility one-shot LLM call (used for rephrase, etc.).
- `processUrl(...)` (`url-processor.ts`) — expand a URL/domain into concrete pages (map/search) and scrape them.

### Status steps (`lib/extract/extract-redis.ts`)

`updateExtract(extractId, { status, steps:[ExtractStep.*], data? })` writes the async job record to
Redis; `/extract/{id}/status` reads it. Steps include INITIAL → MAP → (multi-entity/extract) → COMPLETE.

## Data contracts

- **Extract request:** `{ urls:string[], prompt?:string, schema?:JSONSchema, enableWebSearch?:bool, allowExternalLinks?:bool, includeSubdomains?:bool, scrapeOptions?:ScrapeOptions, origin? }`.
- **Async job record (Redis):** `{ id, status:"processing"|"completed"|"failed"|"cancelled", steps:[{step,startedAt,...}], data?, error?, sources? }`.
- **Status response:** `{ success, status, data, steps?, sources?, expiresAt }`.
- **Result:** one object validated against `schema` (or free-form when prompt-only).

## Dependencies & assumptions

- The scrape pipeline ([[scrape-engine-fallback-pipeline--from-firecrawl]]) for fetching sources; crawl/map for domain expansion.
- An LLM layer with **structured output** (JSON-schema constrained) — used for analyze, batch extract, single answer, rephrase.
- **Redis** for async job state. A reranker (embeddings/relevance). `$ref` schema dereferencing (e.g. `@apidevtools/json-schema-ref-parser`-style).
- **Env:** LLM provider keys, `REDIS_URL`. Swappable: any structured-output LLM; chunk size (50) is tunable.

## To port this, you need:

- [ ] An async job with Redis-backed status steps.
- [ ] A `analyzeSchemaAndPrompt` classifier → single-answer vs multi-entity + which keys are arrays.
- [ ] `spreadSchemas` to split the schema; `processUrl` to expand+scrape sources.
- [ ] Chunked (×50) concurrent per-doc extraction (`batchExtract`) for the multi-entity path.
- [ ] `mergeNullValObjs` + array dedup to reduce partial results without clobbering.
- [ ] A single-answer completion for non-entity fields; a final merge.
- [ ] (optional) a reranker to focus LLM spend on relevant pages.

## Gotchas

- **The single-vs-multi decision is the whole ballgame** — misclassification ruins the output shape; spend care on `analyzeSchemaAndPrompt`.
- **Null-aware merge, not last-write-wins** — the same entity across pages must union non-null fields, or later empty pages erase good data.
- **Split the schema** — don't run one giant completion for both "one summary" and "list of 200 items"; spread and merge.
- **Chunk to fit context** (50 docs) and run chunks' docs concurrently but chunks sequentially to bound memory/cost.
- **Dereference `$ref`s** before sending schema to the LLM, or structured output breaks.
- **It's async** — long multi-page extracts will time out as request/response; use the job+poll pattern.
- **`fire-0/` is the legacy engine** — don't port both; the non-`fire-0` path is current.

## Origin (reference only)

firecrawl/firecrawl @ `main`:
`apps/api/src/lib/extract/extraction-service.ts` (spine — inlined),
`.../completions/{analyzeSchemaAndPrompt,batchExtract,singleAnswer}.ts`,
`.../helpers/{spread-schemas,merge-null-val-objs,deduplicate-objs-array,dereference-schema,source-tracker}.ts`,
`.../url-processor.ts`, `.../reranker.ts`, `.../extract-redis.ts`, `.../build-prompts.ts`,
`apps/api/src/controllers/v2/extract.ts` + `extract-status.ts`,
`apps/api/src/scraper/scrapeURL/transformers/llmExtract.ts` (single-page `json` format).
Legacy parallel impl under `.../fire-0/`.

**Gaps to verify (cost-capped; spine grepped, completions not deep-read):** exact prompts in
`build-prompts.ts`; how `analyzeSchemaAndPrompt` decides multi-entity; the LLM provider/model + structured-output
mechanism; reranker scoring details; `processUrl` map/search expansion specifics.
