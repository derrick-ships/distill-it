# Staged Actions Confirmation Queue — from [open-carrusel](https://github.com/Hainrixz/open-carrusel)

> Domain: [[_domain]] · Source: https://github.com/Hainrixz/open-carrusel · NotebookLM: <link once added>

## What it does

When the AI agent decides to do something that changes your work — write a slide, replace a template, modify a file — it doesn't always just *do* it. It can instead drop a **staged action**: a pending, described, reviewable record that sits in a queue until it's either applied or discarded. Think of it as a "the assistant wants to do X — approve?" tray, persisted to disk so it survives reloads.

## Why it exists

The agent here has real hands: it runs Bash and writes into the app. Letting a non-deterministic model mutate the user's carousel with no checkpoint is how you get surprise overwrites. Staging turns "the agent acted" into "the agent *proposed* an action with a human-readable description," giving the user (or an auto-execute rule) a clean decision point. It's the bounded-autonomy idea: the agent is free to propose, but a confirmation layer it doesn't control governs whether the proposal lands.

Each action also carries an `autoExecute` flag — so trusted, low-risk action types can skip the prompt and apply immediately, while risky ones wait for a human. The same mechanism does both "ask first" and "just do it," chosen per action.

## How it actually works

1. **An action is staged.** `createStagedAction()` records `{ type, fileName, content, description, carouselId, autoExecute }`, stamps it with an `id`, a `createdAt`, and status `"pending"`, and appends it to a JSON file (`staged-actions.json`).
2. **It's reviewed.** `listStagedActions()` returns the queue; the UI shows the human-readable `description` and what would change. `getStagedAction(id)` fetches one.
3. **It's resolved.** `updateStagedActionStatus(id, status)` flips it from `"pending"` to a resolved state and stamps `resolvedAt` *only on the first transition out of pending* (so the resolution time is recorded once and not overwritten). Applying the action performs the real mutation (write the file/slide); discarding just marks it resolved without acting.
4. **Auto-execute** short-circuits review for action types flagged safe — they apply on creation rather than waiting in the tray.

The whole thing is a small state machine — `pending → resolved` — backed by the same atomic JSON store the rest of the app uses, so it's crash-safe and concurrent-write-safe.

## The non-obvious parts

- **It separates "the agent decided" from "the change happened."** That seam is the entire safety value. Without it, an agent with Bash is mutating your data with no undo point.
- **`description` is a first-class field, not a nicety.** A staged action is only reviewable if a human can understand it in one line; the agent is expected to author that summary when it stages.
- **`resolvedAt` is set once.** Guarding it to only stamp on the *first* exit from `pending` means re-processing or duplicate calls don't rewrite history — the audit trail stays honest.
- **`autoExecute` makes the same primitive serve trust tiers.** Rather than two code paths ("safe actions" vs "confirmable actions"), there's one queue with a flag — friction is a per-action data decision.
- **Persisted, not in-memory.** Because the queue lives in a JSON file, a pending proposal survives a server restart or page reload; the human can come back to it.

## Related

- [[cli-subprocess-agent--from-open-carrusel]] (the agent whose proposals this queue gates)
- [[json-mutex-store--from-open-carrusel]] (the atomic store that persists the queue safely)
- [[deterministic-security-hooks--from-pagokit]] (the other guardrail flavor: a hook that *blocks* bad agent output, vs. this which *stages* it for review)
