# Agentic Loop — from [open-design](https://github.com/nexu-io/open-design)

> Domain: [[_domain]] · Source: https://github.com/nexu-io/open-design · NotebookLM: 

## What it does

Open Design runs your design brief through a 3-stage automated pipeline: **Plan → Generate → Critique**. You describe what you want, the agent plans it, builds it, then a simulated panel of 5 reviewers tears it apart and sends it back for fixes — all automatically, until the result is good enough to ship.

## Why it exists

Generating a single artifact isn't hard. Generating one that's actually *good* — with proper hierarchy, brand compliance, accessibility, and copy — requires multiple passes. The agentic loop automates that iteration so users don't have to manually prompt "make it better" 10 times. It's the difference between a vending machine and a design partner.

## How it actually works

When you submit a brief, the app first surfaces a 7-question discovery form (what are we making, who's it for, what's the tone, what brand, what scope). Your answers, combined with the active skill and design system, get packaged into a snapshot and handed to the agent.

The agent runs through three stages in sequence:

**Stage 1 — Plan:** The agent generates a design plan document. This is a roadmap: what sections exist, what the visual direction will be, what components it'll use. It writes this as a file.

**Stage 2 — Generate:** Using the plan as context, the agent builds the actual artifact — an HTML prototype, an image, a deck, or a video. It streams tool calls (file writes, live-artifact updates) as it works.

**Stage 3 — Critique (Critique Theater):** Five simulated panelists review the artifact:
- **Designer** — visual hierarchy, layout
- **Critic** — overall quality judgment
- **Brand** — brand system compliance
- **A11Y** — accessibility
- **Copy** — text and tone

Each panelist scores their dimension and flags must-fix issues. The agent sees these critiques and fixes them, then the panel reviews again. This loops until: score ≥ threshold AND zero open must-fix items. At least two panelists must disagree on a must-fix item each non-final round (prevents rubber-stamping).

The whole thing runs inside a **single agent conversation thread** — not three separate tasks. "Loop" means the agent reruns the same stage with "refine your prior output" instructions until the `until` expression resolves. Max iterations are capped (default 10) to prevent infinite quota burn.

## The non-obvious parts

**It's one conversation, not a pipeline of tasks.** Stages don't reset context or spawn new agents. The agent remembers everything it wrote in stage 1 when doing stage 3. This means critique feedback is always grounded in actual prior output, not a description of it.

**The "brief → references → material → editing → motion → handoff" language in the README is marketing copy, not code stages.** The real stages are plan, generate, critique. Reference gathering, brand spec extraction, and motion are handled by agent capabilities and specialized skills within those stages, not as separate pipeline steps.

**Critique Theater prevents convergence theater.** The rule that "at least two panelists must diverge" means the system can't trivially self-approve. It has to actually find a real disagreement before shipping.

**Handoff is a CLI escape hatch, not a stage.** Running `od handoff --project <id>` synthesizes the full conversation into a single prompt you can pipe to another tool or agent. It's for resuming work externally, not a step in the automated loop.

## Related

- [[design-artifact-generation--from-open-design]] (what the generate stage actually produces)
- [[agent-cli-integration--from-open-design]] (the coding agents that execute each stage)
- [[skills-system--from-open-design]] (the SKILL.md definitions that shape each stage's behavior)
- [[design-systems-library--from-open-design]] (the brand context injected into every stage)
