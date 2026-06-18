# Generate llms.txt (build spec) — distilled from firecrawl

## Summary

Auto-generate a site's `llms.txt` (titled list of pages + one-line descriptions) and optional
`llms-full.txt` (full page markdown, delimiter-separated) by composing **map → scrape → per-page
one-line-summary LLM**. Async job, Redis status, Supabase result cache, entry/page caps.

## Core logic (inlined)

### Service (`lib/generate-llmstxt/generate-llmstxt-service.ts`)

```ts
const descriptionSchema = z.object({ description: z.string() });   // one-field summary schema
const PAGE_MARKER = /<\|firecrawl-page-\d+-lllmstxt\|>\n/;

function limitPages(fullText, maxPages) {                          // trim llms-full.txt
  const pages = fullText.split(PAGE_MARKER);
  return pages.slice(0, maxPages + 1).join("");
}
function limitLlmsTxtEntries(llmstxt, maxEntries) {                // trim llms.txt entry list
  const [header, ...entries] = splitOnHeader(llmstxt);
  return `${header}\n\n${entries.slice(0, maxEntries).join("\n")}`;
}

export async function performGenerateLlmsTxt({ url, maxUrls, showFullText, cache, teamId, generationId, ... }) {
  // (cache) try Supabase first
  if (cache) { const hit = await getCachedLlmsTxt(url); if (hit) return finish(hit); }

  // 1) MAP the site
  const links = (await getMapResults({ url, limit: maxUrls, ... })).slice(0, maxUrls);
  await updateGeneratedLlmsTxt(generationId, { status:"processing", ... });

  let llmstxt = `# ${title}\n\n`;
  let llmsFull = "";
  // 2) scrape + 3) summarize each page
  for (let i = 0; i < links.length; i++) {
    const doc = await scrapeURL(links[i], { formats:["markdown"] });
    const { extract } = await generateCompletions({ markdown: doc.markdown, schema: descriptionSchema,
      prompt: "Write a one-sentence description of this page." });
    llmstxt  += `- [${doc.metadata.title}](${links[i]}): ${extract.description}\n`;
    llmsFull += `<|firecrawl-page-${i+1}-lllmstxt|>\n${doc.markdown}\n`;
    await updateGeneratedLlmsTxt(generationId, { status:"processing", llmstxt, ...(showFullText && { llmsfulltxt: llmsFull }) });
  }

  // caps + persist
  llmstxt = limitLlmsTxtEntries(llmstxt, maxUrls);
  if (showFullText) llmsFull = limitPages(llmsFull, maxUrls);
  await saveLlmsTxtToSupabase(url, llmstxt, llmsFull);
  await updateGeneratedLlmsTxt(generationId, { status:"completed", llmstxt, llmsfulltxt: showFullText ? llmsFull : undefined });
}
```

## Data contracts

- **Request:** `{ url, maxUrls?, showFullText?:bool, cache?:bool }`.
- **Job record (Redis):** `{ id, status, llmstxt, llmsfulltxt?, expiresAt }`.
- **llms.txt format:** `# <title>\n\n- [PageTitle](url): one-line description\n...`.
- **llms-full.txt format:** each page = `<|firecrawl-page-N-lllmstxt|>\n<markdown>\n` (split on the marker to recover pages).
- **Supabase cache row:** `{ url, llmstxt, llmsfulltxt, created_at }`.

## Dependencies & assumptions

- [[site-url-map--from-firecrawl]] (`getMapResults`), [[scrape-engine-fallback-pipeline--from-firecrawl]] (`scrapeURL`), an LLM (`generateCompletions`) with structured output.
- **Redis** for status, **Supabase** (or any KV/DB) for the result cache. **Env:** LLM keys, DB creds.

## To port this, you need:

- [ ] Map → list of URLs; scrape each to markdown; per-page LLM one-line description.
- [ ] Assemble `llms.txt` (entry list) and optional `llms-full.txt` (markered full text).
- [ ] Entry/page caps; an async job with status; a result cache keyed by site URL.

## Gotchas

- **Use a delimiter in full-text** (`<|firecrawl-page-N-...|>`) so consumers can split pages back out.
- **Cap entries and pages** — big sites otherwise produce multi-MB files.
- **Cache by site URL** — it scrapes the whole site; regenerating uncached is expensive.
- **One-field summary schema** keeps descriptions uniform and the LLM cheap; don't over-prompt.
- **Stream partial results** to the job record so long runs show progress.

## Origin (reference only)

firecrawl/firecrawl @ `main`: `apps/api/src/lib/generate-llmstxt/generate-llmstxt-service.ts` (inlined),
`.../generate-llmstxt-redis.ts`, `.../generate-llmstxt-supabase.ts`,
`apps/api/src/controllers/v1/{generate-llmstxt,generate-llmstxt-status}.ts`.

**Gaps to verify (cost-capped):** exact description prompt; default `maxUrls`; the Supabase cache schema/TTL; title derivation.
