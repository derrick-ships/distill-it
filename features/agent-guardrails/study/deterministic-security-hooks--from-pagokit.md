# Deterministic Security Hooks (executable guardrails, not markdown) — from [PagoKit](https://github.com/Hainrixz/agente-pagokit)

> Domain: [[_domain]] · Source: https://github.com/Hainrixz/agente-pagokit · NotebookLM:

## What it does

When you let PagoKit generate payment code, it doesn't just *tell* Claude "remember to verify webhook signatures and don't hardcode keys." It installs a set of small programs that watch every file the agent writes, inspect the content, and **physically block the write** if it breaks a security rule. If Claude tries to save a webhook handler with no signature check, the save is rejected with a precise, bilingual error ("Webhook handler does not verify request signature… add `stripe.webhooks.constructEvent(...)`") and the agent has to fix it before it can proceed. The rules live as Node.js scripts, run locally with no network calls, and fail *open* on their own bugs (a crash in a check never blocks you) but *closed* on a real violation.

## Why it exists

Markdown guidelines are advisory. An LLM reads "always verify the signature," generally complies, and then — under a long context, an unusual framework, or a confident wrong turn — quietly skips it. For most code that's a bug you catch later. For payment code it's an unsigned webhook anyone on the internet can forge to mark orders as paid, or a live `sk_live_…` key committed to a public repo. The job-to-be-done is to make the five things that *must never* ship insecure literally unshippable by the agent, regardless of what the model decides in the moment. The author's framing: these "aren't text in a markdown, they're Node.js scripts that block insecure writes."

## How it actually works

The whole system is wired through Claude Code's **hook** mechanism. A `hooks.json` registers three lifecycle hooks — `PreToolUse`, `PostToolUse`, and `Stop` — all matched to the `Write|Edit|MultiEdit` tools, and all pointing at one dispatcher script run with a different phase argument:

```
node $CLAUDE_PLUGIN_ROOT/hooks/pagokit-validate.js pre   # before a write
node $CLAUDE_PLUGIN_ROOT/hooks/pagokit-validate.js post  # after a write
node $CLAUDE_PLUGIN_ROOT/hooks/pagokit-validate.js stop   # end of the agent's turn
```

Claude Code pipes a JSON description of the tool call into the script on stdin (which tool, the target file path, and the content being written). The dispatcher reads it, figures out the file path and the new content, and decides whether to run.

**It filters first.** Non-source files and allowlisted paths — anything under `__tests__/`, `*.test.ts`, `__fixtures__/`, the plugin's own integration-builder templates, `node_modules` — are skipped, so the rules don't fire on test fixtures that *intentionally* contain fake keys.

**It runs the rules for that phase.** Each rule is a separate module in a `checks/` folder exporting a `run(ctx)` function that gets `{ filePath, content }` and returns either `null` (pass) or a structured finding `{ rule, level, code, message_en, message_es, suggested_fix }`. The phases assign different rules: the *pre* phase runs cheap pre-write checks (does a webhook already exist? is `.gitignore` set up?), the *post* phase runs the heavy content scanners (signature present, no hardcoded keys, idempotency is a real UUID, raw body consumed before parse, no PII in logs), and the *stop* phase re-runs the three most critical scanners (signature, keys, raw body) as a final backstop in case something slipped through edits during the turn.

**It decides pass/warn/deny.** Findings have a `level`. If any finding is `deny`, the dispatcher exits with code **2**, which Claude Code treats as "block this tool call," and the structured findings are emitted to stderr so the agent sees exactly what failed and the `suggested_fix`. `warn`-level findings and clean runs exit **0** (allowed). Every denial is appended to `.pagokit/audit.log` so a human can review what the agent attempted.

**The scanners are smarter than a grep.** Before pattern-matching, a `stripCommentsAndStrings()` utility blanks out comments and string literals (character-by-character, preserving line numbers) so a rule never false-positives on example code inside a docstring or a string. File-type heuristics decide whether a file even *looks* like a webhook or a checkout endpoint before applying the relevant rule. And each rule has a documented **bypass**: an inline `// pagokit-ignore: <rule-id> -- <reason>` comment (or `# …` for Python) turns the rule off for that file, with the reason left in the code as a record. Webhook verification additionally honors a `// @pagokit:signature-verified` tag for teams using a custom verifier wrapper the regex can't recognize.

So the flow for one risky write is: agent calls Write → Claude Code pipes the JSON to `pagokit-validate.js post` → dispatcher strips comments, runs the content scanners → a scanner returns `level: "deny"` → exit 2 + bilingual message on stderr → Claude Code blocks the write and shows the agent the error → agent reads `suggested_fix`, adds the verifier, retries → scanner now passes → exit 0 → write lands.

## The non-obvious parts

- **Fail open on bugs, fail closed on violations.** A 2-second stdin timeout and a try/catch around every check mean the validator *never* hangs or blocks the agent because of its own internal error — it just allows the write. It only ever blocks when a check *positively confirms* a violation. This asymmetry is deliberate: a guardrail that breaks the agent when it itself is buggy gets disabled within a day.
- **The test allowlist is load-bearing.** The single most likely way to ship a broken guardrail is to have it fire on your own test fixtures (which contain deliberately-fake keys and deliberately-insecure handlers). Skipping `__tests__`/`__fixtures__`/templates at the dispatcher level is what lets the rules be aggressive in real code.
- **Strip comments/strings before matching.** Without this, a code sample in a comment ("don't do `request.json()` here") trips the very rule it's documenting. The scanner blanks those regions first.
- **Three phases for one set of rules.** Re-running the critical scanners at `Stop` catches the case where the file passed when first written but a later `Edit` in the same turn removed the signature check. The pre-phase, by contrast, is for cheap "should this even exist yet" checks.
- **Bilingual, fix-first error messages.** Every finding carries `message_en`, `message_es`, and a concrete `suggested_fix` with the exact API call to add. The error is written to be *actionable by the agent*, not just descriptive — it's effectively a repair instruction.
- **Bypass-with-reason beats no bypass.** A hard gate with no escape hatch gets ripped out the first time it's wrong. The `pagokit-ignore` tag keeps the gate while leaving a grep-able trail of every deliberate override.
- **This is enforcement, not generation.** The same model still writes the code; the hooks only constrain the *result*. That separation means the guardrails work no matter how the code was produced — even hand-edited — and could be lifted out of PagoKit to police any payment code in any Claude Code project.

## The playbook (how this drives adoption / trust)

- **Security as a credible promise, not a hope.** "We deterministically block insecure writes" is a far stronger trust signal for a payments tool than "our prompt reminds the model to be careful." It's the product's main differentiator versus a plain prompt-library.
- **The audit log is the enterprise hook.** A reviewable `.pagokit/audit.log` of every blocked attempt is exactly what a security team wants before approving an agent to touch payment code.
- **Cloneability:** the *mechanism* (Claude Code hook → dispatcher → check modules → exit 2) is trivial to copy. The moat is the curated rule set and the false-positive engineering (comment stripping, file heuristics, the allowlist) that makes it usable day-to-day rather than a nag.

## Related
- [[secure-payment-webhook--from-pagokit]] — the secure pattern these hooks *enforce*; the rules are the cop, that doc is the law.
- [[payment-provider-advisor--from-pagokit]] — sibling PagoKit feature; the advisor picks the provider, the hooks police the code generated for it.
- [[agent-driven-install--from-agent-reach]] — the prose cousin: a "Boundaries" DO-NOT list in a runbook vs. executable deny rules here.
- [[byok-proxy--from-open-design]] — another "do the secure thing structurally so the agent can't get it wrong" pattern.
