# Agentic Loop (build spec) — distilled from open-design

## Summary

A 3-stage linear pipeline (plan → generate → critique) that runs inside a single agent conversation thread. Each stage iterates via a refinement loop until an `until` expression resolves. Critique stage uses a 5-panelist jury (Designer/Critic/Brand/A11Y/Copy) with convergence enforcement. Max iterations capped at `OD_MAX_DEVLOOP_ITERATIONS` (default 10).

## Core logic (inlined)

```
runPipeline(input: AppliedPluginSnapshot):
  for each stage in input.pipeline.stages:
    iterations = 0
    while not evaluate_until(stage.until, iterations):
      result = runStage(stage, input, conversationThread)
      iterations++
      if iterations >= OD_MAX_DEVLOOP_ITERATIONS: break
    // advance to next stage
```

**Stage execution:**
```
runStage(stage, snapshot, thread):
  systemPrompt = buildSystemPrompt(snapshot)  // skill + design system + official-system.ts rules
  userInstruction = buildStageInstruction(stage, iterations)
  // "Begin stage N: Generate" or "Refine your prior artifact based on critique"
  streamAgentConversation(thread, systemPrompt, userInstruction)
  // agent emits tool calls: file-write, live-artifact-create/update
```

**Critique Theater:**
```
panelists = [Designer, Critic, Brand, A11Y, Copy]
each panelist scores their dimension + flags must_fix items

convergence = (
  score >= threshold AND
  open_must_fix_items == 0 AND
  // Non-final rounds: at least 2 panelists must diverge on a must_fix target
  (is_final_round OR diverging_panelists >= 2)
)
```

**Handoff CLI:**
```
POST /api/projects/:id/handoff
Response: {
  prompt: string,       // synthesized context for resuming externally
  model: string,
  tokenUsage: { inputTokens: number, outputTokens: number },
  transcriptMessageCount: number
}
```

## Data contracts

**Input — AppliedPluginSnapshot:**
```typescript
{
  manifest: PluginManifest,          // resolved skill + design system bindings
  inputs: Record<string, string|number|boolean>,  // user form values
  context: Array<{ kind: 'skill'|'design-system', ref: string }>,  // resolved refs
  pipeline: {
    stages: Array<{
      name: string,
      until?: string  // expression: "iterations >= 3" or convergence signal
    }>
  }
}
```

**Conversation thread (ChatRequest):**
```typescript
{
  agentId: string,
  projectId: string,
  conversationId: string,
  message: string,
  systemPrompt: string,
  skillIds: string[],
  designSystemId: string,
  model: string,
  sessionMode: 'design' | 'chat',
  locale: string
}
```

**SSE stream events (ChatSseEvent):**
```typescript
{ type: 'start', runId, agentId, protocolVersion }
{ type: 'agent', status, text?, thinking?, liveArtifacts?, toolInvocations?, tokenUsage? }
{ type: 'stdout' | 'stderr', data: string }
{ type: 'error', message, stack? }
{ type: 'end', exitCode, signal, resumable: boolean }
```

**Critique panel output format (XML-tagged in agent response):**
```
<panel>
  <panelist role="Designer" score="7/10">
    <must_fix>Heading hierarchy collapses below 768px</must_fix>
    <nice_to_have>Increase card shadow depth</nice_to_have>
  </panelist>
  ...
</panel>
```

## Dependencies & assumptions

- **Runtime**: Node.js ~24, TypeScript, Hono HTTP framework
- **Agent**: Any of 22+ supported CLI tools (Claude Code, Cursor, Copilot, etc.) — see agent-cli-integration build spec
- **Skills**: SKILL.md format with optional `od.pipeline` declaration — see skills-system build spec
- **Design systems**: DESIGN.md with 9-section schema — see design-systems-library build spec
- **Environment**: `OD_MAX_DEVLOOP_ITERATIONS` (default 10) controls loop ceiling
- **Stage names in code**: `plan`, `generate`, `critique` — NOT "brief/references/material/editing/motion/handoff" (that's marketing copy)

## To port this, you need:

- [ ] A conversation thread abstraction that persists across stage boundaries (single context window)
- [ ] Stage runner that evaluates `until` expressions (can start with simple iteration count)
- [ ] System prompt builder that injects skill + design system context per stage
- [ ] Critique panel prompt (5 roles, scoring rubric, must_fix/nice_to_have distinction)
- [ ] Convergence checker (score threshold + zero open must_fix + panelist divergence rule)
- [ ] Iteration ceiling enforcement (env var or hard-coded max)
- [ ] SSE streaming endpoint for real-time progress to UI
- [ ] Handoff endpoint: synthesize conversation → single resumable prompt

## Gotchas

- **Stages share the same conversation thread** — context from stage 1 bleeds into stage 3. This is intentional (critique is grounded in actual output) but means your context window fills up on long runs.
- **The panelist divergence rule is load-bearing.** Without it, the system can converge trivially in round 1 by having all panelists agree. Enforce it or you'll ship bad artifacts.
- **`OD_MAX_DEVLOOP_ITERATIONS` is a quota guard, not a quality gate.** Don't rely on it for correctness — a loop can hit ceiling before actually converging. Add an explicit quality threshold check before marking done.
- **"motion" and "handoff" are not pipeline stages.** Motion is handled by specialized skills with motion-specific prompts. Handoff is a CLI command the user runs manually post-loop.

## Origin (reference only)

Repo: https://github.com/nexu-io/open-design  
Key files: `apps/daemon/src/`, `apps/daemon/src/prompts/official-system.ts`, `apps/daemon/src/prompts/panel.ts`, `apps/daemon/src/prompts/discovery.ts`
