# AI Reply Drafting — from [inbox-zero](https://github.com/elie222/inbox-zero)

> Domain: [[_domain]] · Source: https://github.com/elie222/inbox-zero · NotebookLM: <link once added>

## What it does

When an email needs a response, Inbox Zero writes a draft reply *in your voice* and drops it into your drafts folder, ready to review and send. It doesn't just generate generic text — it pulls in the thread history, your background info, a knowledge base, your calendar availability, and a learned summary of how you actually write, then produces a draft plus a confidence score (low/medium/high) so the system knows how much to trust it.

## Why it exists

The slowest part of email isn't reading — it's composing the reply. A generic AI reply is useless because it doesn't sound like you and doesn't know your context (your availability, your standard answers, your terse vs. chatty style). The job-to-be-done is **producing a draft good enough that the user just tweaks and sends**, which means it has to (a) know the relevant context, (b) match the user's voice, and (c) be honest about when it's guessing so low-confidence drafts can be withheld or flagged rather than auto-sent.

## How it actually works

**Gather context.** Before writing, the system assembles everything relevant: the full thread (each message truncated to ~3000 chars so long threads don't blow the context budget), the user's profile/background, a knowledge base of custom info the user maintains, calendar availability rendered as concrete suggested time slots in the user's timezone, optional external-tool data (CRM, integrations), and the history of past drafts to this same sender for tone consistency.

**Apply the user's voice — with a priority order.** Writing style is layered:
1. An *explicit* writing-style setting the user typed wins.
2. A *learned* writing style (see below) is advisory — it complements but never overrides the explicit setting.
3. If neither exists, a default kicks in: concise, direct, friendly, "aim for 2 sentences at most."
Signature handling is explicit too: if the user has a configured signature, the model is told *not* to write any closing or sign-off, so it doesn't double up.

**Learn the voice over time.** Separately, the system watches how the user edits AI drafts. It compiles that "preference evidence" and periodically asks the model to *summarize the user's learned writing style* into a compact (≤1500 char) style guide — a handful of concrete, operational rules (sentence count, greeting/sign-off habits, how many questions to include) plus 2-3 before/after examples showing how the user tends to compress. Crucially, that summary is scrubbed of any names, addresses, companies, dates, or links — it captures *style*, not content. That summary is then fed into future drafting prompts as a ready-made style guide.

**Generate with a confidence score.** The draft is produced via a structured call returning `{ reply, confidence }` where confidence is LOW/MEDIUM/HIGH. The system writes the draft in the same language as the latest message in the thread.

**Clean up the output.** Generated text is normalized: line endings standardized, trailing whitespace stripped, collapsed paragraphs repaired by detecting sentence boundaries, single line breaks promoted to double breaks when most lines end in punctuation (so it reads as proper paragraphs). A safety check rejects degenerate output (a character repeated 50+ times) and retries.

## The non-obvious parts

- **Learned style is a *summary*, not raw examples.** Rather than stuffing dozens of past emails into every prompt (expensive, leaky), they distill the user's style once into a tiny operational guide. This is cheaper per draft and privacy-preserving — the style guide deliberately contains no PII.
- **Explicit beats learned beats default.** The hierarchy prevents the learned model from fighting an explicit instruction. The user is always in control.
- **Confidence is a product feature, not telemetry.** The LOW/MEDIUM/HIGH score gates behavior — an account setting (`draftReplyConfidence`) can restrict auto-drafting to only high-confidence cases. Honesty about uncertainty is what makes auto-drafting safe.
- **Calendar slots are pre-computed into the prompt.** Rather than giving the model raw calendar data and hoping it does timezone math, the system renders concrete available slots in the user's timezone and hands those over.
- **Per-message truncation, not whole-thread truncation.** Capping each message (~3000 chars) instead of the whole thread keeps recent and old messages both represented.
- **Output normalization is load-bearing.** LLMs produce inconsistent whitespace/paragraphing; without the repair pass, drafts look broken in the compose window. The degenerate-output guard catches the rare repetition-loop failure mode.

## Related

- [[ai-rules-engine--from-inbox-zero]] — drafting is invoked as the DRAFT_EMAIL/REPLY action of a matched rule.
- [[email-provider-abstraction--from-inbox-zero]] — the finished draft is written to the mailbox via the provider's draft method.
- See also: any "write in my voice" feature; the learn-a-style-summary-from-edits loop generalizes to any personalized generation.
