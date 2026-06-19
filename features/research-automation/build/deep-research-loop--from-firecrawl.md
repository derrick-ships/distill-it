# Deep Research Loop (build spec) — distilled from firecrawl

## Summary

Autonomous, depth-bounded research agent: from a topic (no URLs), loop {generate queries → search+scrape
→ record sources → analyze → pick next topic} until `maxDepth` or `timeLimit`, then synthesize a report.
Async job with Redis-streamed activities + sources for live status. Reuses the search-and-scrape path.

## Core logic (inlined)

### State + LLM services (`lib/deep-research/research-manager.ts`)

```ts
class ResearchStateManager {
  private currentDepth = 0;
  private sources: DeepResearchSource[] = [];
  private nextSearchTopic = "";
  totalExpectedSteps: number;
  constructor(private researchId, ..., private readonly maxDepth, topic) {
    this.totalExpectedSteps = maxDepth * 5;     // progress estimate: 5 steps/depth
    this.nextSearchTopic = topic;
  }
  hasReachedMaxDepth() { return this.currentDepth >= this.maxDepth; }
  async addActivity(activities) { await updateDeepResearch(this.researchId, { activities }); }  // Redis stream
  async addSources(sources)     { await updateDeepResearch(this.researchId, { sources }); }
  incrementDepth()  { this.currentDepth++; }
  setNextSearchTopic(t) { this.nextSearchTopic = t; }
}
class ResearchLLMService {
  async generateSearchQueries(topic, learnings) { /* LLM -> string[] of queries */ }
  async analyzeAndPlan(/* new content, sources */) { /* LLM -> { learnings, nextTopic, shouldContinue } */ }
  async generateFinalAnalysis(topic, sources, systemPrompt) { /* LLM -> report */ }
}
```

### Loop (`lib/deep-research/deep-research-service.ts`)

```ts
export async function performDeepResearch({ researchId, teamId, timeLimit, maxUrls, maxDepth, systemPrompt, ... }) {
  const state = new ResearchStateManager(researchId, ..., maxDepth, topic);
  const llm = new ResearchLLMService(logger);
  const startedAt = Date.now();

  while (!state.hasReachedMaxDepth()) {
    if (Date.now() - startedAt > timeLimit * 1000) break;            // time-limit stop
    await state.addActivity([{ type:"search", status:"processing", ... }]);

    const queries = await llm.generateSearchQueries(state.getNextSearchTopic(), state.getLearnings());
    for (const q of queries) {
      const docs = await searchAndScrapeSearchResult(q, { teamId, maxUrls, ... });   // reuse search+scrape
      await state.addSources(docs.map(toSource));
    }
    const { learnings, nextTopic } = await llm.analyzeAndPlan(/* gathered */);        // the "deep" step
    state.setNextSearchTopic(nextTopic);
    state.incrementDepth();
  }

  const report = await llm.generateFinalAnalysis(topic, state.getSources(), systemPrompt);  // synthesize
  await updateDeepResearch(researchId, { status:"completed", finalAnalysis: report, sources: state.getSources() });
  logDeepResearch(...);
}
```

## Data contracts

- **Request:** `{ query/topic, maxDepth?, maxUrls?, timeLimit?(s), systemPrompt? }`.
- **Redis job record:** `{ id, status:"processing"|"completed"|"failed", currentDepth, activities:[{type,status,message,timestamp}], sources:[{url,title,description,...}], finalAnalysis? }`.
- **Status response (`/deep-research/{id}/status`):** the record + a progress fraction (`completedSteps/totalExpectedSteps`).
- **DeepResearchSource:** `{ url, title, description, ... }`.

## Dependencies & assumptions

- The **search+scrape** path (`searchAndScrapeSearchResult`) — see [[web-search-with-scrape--from-firecrawl]].
- An LLM for query generation, analysis/planning, and final synthesis (`generateCompletions`).
- **Redis** for async job state + activity streaming. **Env:** LLM keys, `REDIS_URL`.
- Swappable: any search backend; the loop structure is provider-agnostic.

## To port this, you need:

- [ ] An async job with Redis-streamed `activities` + `sources` and a status endpoint.
- [ ] A state manager (depth, sources, next-topic) and an LLM service (queries / analyze-plan / synthesize).
- [ ] A bounded loop with BOTH a `maxDepth` and a wall-clock `timeLimit` stop.
- [ ] Reuse of your search+scrape pipeline inside the loop.
- [ ] A final synthesis pass with its own system prompt.

## Gotchas

- **Two leashes, not one** — depth AND time; an analyze step that always says "continue" will run forever otherwise.
- **The analyze→next-topic step is the whole value** — a weak planner makes it a glorified multi-search.
- **Stream activities to Redis** or a multi-minute job looks hung.
- **Bound `maxUrls`/scrapes per round** — cost compounds fast across depths.
- **Separate gather from synthesis** — don't let the report-writer also decide what to search; keep passes distinct.

## Origin (reference only)

firecrawl/firecrawl @ `main`: `apps/api/src/lib/deep-research/deep-research-service.ts` (loop — inlined),
`.../research-manager.ts` (state + LLM service — inlined), `.../deep-research-redis.ts`,
`apps/api/src/controllers/v1/{deep-research,deep-research-status}.ts`, `controllers/v2/agent.ts` (the v2 agent variant).

**Gaps to verify (cost-capped):** exact prompts in `generateSearchQueries`/`analyzeAndPlan`/`generateFinalAnalysis`;
the `shouldContinue` signal; how v2 `agent.ts` differs from v1 deep-research; per-round URL budgeting.
