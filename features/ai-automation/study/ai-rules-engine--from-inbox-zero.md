# AI Rules Engine — from [inbox-zero](https://github.com/elie222/inbox-zero)

> Domain: [[_domain]] · Source: https://github.com/elie222/inbox-zero · NotebookLM: <link once added>

## What it does

You write rules for your inbox in plain English — "Reply to customer questions using my knowledge base", "Archive and label newsletters", "Forward all receipts to my accountant". For every incoming email, Inbox Zero figures out which rule (if any) applies and then carries out that rule's actions: archive it, label it, draft a reply, forward it, mark spam, call a webhook, and so on. It's an if-this-then-that for email where the "this" is described in natural language and judged by an LLM, but only when cheaper checks can't decide.

## Why it exists

Email rules have existed forever (Gmail filters, Outlook rules), but they're brittle: you must express everything as exact string matches on from/subject. Real intent ("anything that looks like a sales pitch") doesn't fit. The job-to-be-done is **letting a non-technical user automate their inbox by describing what they want in words**, while keeping it cheap and trustworthy enough to run automatically on every message. That last part is the whole game: an LLM on every email would be slow, expensive, and occasionally wrong, so the design is built around *not* calling the LLM unless it's actually needed, and around recording why every action fired so the user can trust (and correct) it.

## How it actually works

Think of it as a funnel that gets more expensive at each stage, designed so most emails exit early and cheap.

**1. Each rule has two halves.** A rule carries optional *static conditions* (from, to, subject, body patterns; sender groups; categories) and optional *plain-English instructions*. A per-rule operator says whether the conditions combine with **AND** or **OR**.

**2. Static matching first (free).** Before any AI, the engine tests the static conditions against the email. From/to are matched with address-anchored patterns so a spoofed `boss@company.com.evil.com` can't sneak past a `boss@company.com` rule; subject/body allow `*` wildcards. The operator decides what a static result means:
   - **OR** rule: a static hit is an immediate, confident match — no LLM needed.
   - **AND** rule: if a static condition exists and *fails*, the rule is rejected outright; if it passes, the rule becomes a *candidate* that still needs its instructions checked by AI.
   This is the cost lever: anything decidable by string/pattern logic never reaches the model. Learned patterns (senders the user has corrected before) short-circuit here too.

**3. The LLM picks the rule (only for what's left).** The remaining candidate rules — the ones whose verdict depends on their plain-English instructions — are handed to the model together with the email. Each rule is presented as a named block with its instructions, plus feedback from the user's past corrections and some account context. The model is told to prefer a *specific* rule that matches the email's actual purpose over a generic one, and to pick nothing if nothing fits. Its answer is forced into a strict schema (reasoning + chosen rule name + a "no match" flag), so the output is never free-form. There are two modes: single-rule (the default — pick exactly one) and an optional multi-rule mode where it may select one or two, marking one as primary.

**4. The LLM fills in the blanks.** Actions can contain template placeholders written in double braces — e.g. a label of `{{write a short label}}` or a draft body like `Hi {{first name}},\n\n{{write a reply}}\n\nThanks`. Once a rule is chosen, a second model call generates *only* the values for those placeholders (each becomes a field in a generated schema), and the engine stitches them back into the surrounding static text. Static text outside the braces is never touched. This keeps generated content scoped and predictable.

**5. Execution + audit trail.** The chosen rule's actions are split into immediate vs. delayed (some actions can carry a delay-in-minutes). The engine writes an `ExecutedRule` record (status starts as APPLYING), saves each action item, runs the immediate ones through the provider, and updates the status to APPLIED or ERROR. Delayed actions are scheduled for later. In **test/dry-run mode** none of this persists — it returns "here's the rule that would match and the actions it would take" so the user can preview a rule before trusting it.

**6. Conversation awareness.** There's a synthetic "conversation tracking" meta-rule the engine injects to handle thread status (needs reply / awaiting reply / FYI / resolved). If a thread was previously tracked, that tracking is automatically re-applied to later messages in the same thread so status stays coherent. Only one rule is allowed to generate a draft reply per email, and pre-written (static) drafts win over AI-generated ones.

## The non-obvious parts

- **The two-stage LLM split is deliberate.** "Which rule?" and "what content?" are separate calls with separate schemas. Conflating them would make the classification prompt huge and the output sloppy. Separating them keeps each call small and each schema tight.
- **Static-AND-then-AI is the cost moat.** The static layer isn't just a convenience; it's what makes running on *every* email economically viable. A rule with a static `from` condition and AND logic will reject 99% of mail for free and only spend a token budget on the survivors.
- **Anchored address matching is a security decision, not a nicety.** Naive substring matching on sender addresses is spoofable; they anchor the pattern to the real address boundary.
- **Everything is auditable.** The `ExecutedRule` + `ExecutedAction` records with status and reason mean the user can always see *why* an action happened and feed corrections back — which then influence future classification. The system is built to be wrong occasionally and correct itself, not to be infallible.
- **The "no match" path is first-class.** The schema has an explicit "nothing applies" flag; the model is encouraged to decline rather than force a weak match. Over-matching is treated as worse than under-matching.

## Related

- [[ai-reply-drafting--from-inbox-zero]] — the DRAFT_EMAIL/REPLY action delegates to the drafting feature.
- [[email-provider-abstraction--from-inbox-zero]] — every action executes through the unified provider interface.
- [[bulk-archiver--from-inbox-zero]] — the ARCHIVE action is the same operation the cleanup tools do in bulk.
- See also: any "natural-language automation" engine; the static-pre-filter-then-LLM pattern generalizes to support ticket routing, content moderation, lead triage.
