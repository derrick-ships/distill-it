# Agent Loop & Recovery — from [browser-use](https://github.com/browser-use/browser-use)

> Domain: [[_domain]] · Source: https://github.com/browser-use/browser-use · NotebookLM: <link once added>

## What it does

This is the engine that actually *runs* the agent — the loop that keeps going "look at the page, think, do something, look again" until the task is done or it gives up. Each turn (a "step") it builds a prompt describing the current page and the history so far, asks the LLM for its next move(s), executes them in the browser, records what happened, and loops. Around that simple core sits a surprisingly deep recovery system: it counts failures, nudges the model when it's stuck in a loop, forces a graceful "I'm done" when it's failed too many times, falls back to a second LLM if the primary one rate-limits, and survives browser disconnects.

## Why it exists

A naive "while not done: ask model, do action" loop dies the moment anything goes wrong — and on the real web, *everything* goes wrong: pages hang, models hallucinate an empty action, the agent clicks the same dead button ten times, the browser tab crashes, the API returns a 429. browser-use's loop is the accumulation of fixes for all of those. The authors describe it as "inspired by coding agents," and you can see it: a structured think/act/observe cycle, explicit history, and layered guardrails that degrade gracefully instead of crashing. The recovery machinery is what separates a demo from something that finishes long tasks unattended.

## How it actually works

**The shape of one step.** `Agent.run(max_steps)` sets up signal handling (Ctrl-C pauses/resumes), starts the browser, runs any initial actions, then enters the main loop: `while n_steps <= max_steps`. Each iteration calls `step()`, which has three phases:

1. **Prepare context** — get the current browser state (the indexed DOM list + a screenshot), then assemble the message the model sees. The message manager keeps exactly three slots: a *system* message (set once), a *state* message (rebuilt every step: the task, the formatted history, the current page, plan/todo), and zero-or-more *context* messages (ephemeral nudges, cleared every step). Crucially, the step counter and date go at the very *end* of the state message so the big stable prefix can hit the LLM provider's prompt cache.
2. **Get next action & execute** — call the model with a forced structured-output schema (`AgentOutput`), which returns its reasoning fields plus a list of actions. Execute them one at a time; stop the batch early if an action navigates, changes the URL, or finishes.
3. **Post-process** — update the plan, record action fingerprints for loop detection, adjust the failure counter, and write a history entry (with a stored screenshot).

**What the model returns each step (`AgentOutput`):** `thinking` (optional extended reasoning), `evaluation_previous_goal` ("did my last action work?"), `memory` (running notes), `next_goal`, an optional plan update, and `action` — a list of at least one action. There's a stripped-down "flash mode" that drops the reasoning fields to go faster, and the schema's required fields change accordingly.

**The recovery layers** are the interesting part:

- **Failure counting with nuance.** Only a *single-action* step that errored bumps `consecutive_failures`. A multi-action step that partially failed does *not* (it assumes some progress happened). Connection errors and interrupts never count. Any clean step resets the counter to zero.
- **Two-stage "forced done."** At `max_failures` (default 5) consecutive failures, the agent rewrites its own output schema to a *done-only* variant — the model literally cannot emit anything except "finish" — and is told "you failed 5 times, your only tool is done." That gives one last graceful turn to report a result. At `max_failures + 1` (6), the loop breaks before even calling the model.
- **Loop detection.** A detector hashes each action (normalized per type — a click by its index, a navigate by its URL) over a rolling window, and fingerprints the page (a hash of DOM text + URL + element count). If the same action repeats or the page stops changing, it injects an escalating nudge ("you seem to be repeating yourself") at thresholds like 5, 8, 12. It's a *soft* constraint — the model can still proceed.
- **Replan / explore nudges.** If failures pile up and a plan exists, it suggests replanning; if many steps pass with no plan, it nudges the model to make one.
- **Provider fallback.** On a rate-limit or provider error (401/402/429/5xx), it permanently switches to a configured `fallback_llm` for the rest of the run.
- **Browser-disconnect resilience.** A connection error while the browser is reconnecting waits for the reconnect rather than counting a failure; if the browser is truly gone, it stops cleanly.

When a step finishes, everything is captured into `AgentHistory` (model output + action results + the page state + a screenshot path + timing), so the whole run is replayable and inspectable, and the return value of `run()` is the full `AgentHistoryList`.

## The non-obvious parts

- **The loop is `while n_steps <= max_steps`, not `for`,** and the counter is incremented in the `finally`/finalize block — so even a step that times out before finalizing still manually bumps the counter to avoid spinning forever.
- **The output schema is mutable at runtime.** `self.AgentOutput` is swapped to a done-only type to force termination. Because the provider enforces structured output, this is a hard constraint, not a polite request — a clever way to make "stop now" un-ignorable.
- **Nudges don't accumulate.** All the context messages (loop nudges, budget warnings, recovery prompts) are wiped at the start of every step. They influence exactly one model call and then vanish, keeping the prompt clean.
- **`done` is only valid alone.** If the model puts `done` in the middle of a multi-action list, it's silently dropped — finishing must be a deliberate single act.
- **Failure accounting is asymmetric on purpose.** The "multi-action errors don't count" rule means a step that did three things and only the last failed is treated as progress — which mostly helps, but can mask a genuinely stuck agent.
- **Prompt-cache-aware message ordering.** Putting volatile fields (step number, timestamp) last is a deliberate cost optimization to maximize cache hits on the large, stable prefix.

## Related
- [[indexed-dom-serialization--from-browser-use]] — produces the page state that the "observe" phase feeds into the prompt each step.
- [[action-tool-registry--from-browser-use]] — supplies the action schema the model picks from and executes the chosen actions.
- [[multi-provider-llm-abstraction--from-browser-use]] — the `ainvoke(messages, output_format=AgentOutput)` call and the fallback-LLM swap both ride on it.
- See also: [[agent-output-contract--from-last30days-skill]] (constraining LLM output via an explicit contract) and [[ordered-backend-routing--from-agent-reach]] (health-gated fallback, the same instinct as the provider fallback here).
