# Bulk Archiver — from [inbox-zero](https://github.com/elie222/inbox-zero)

> Domain: [[_domain]] · Source: https://github.com/elie222/inbox-zero · NotebookLM: <link once added>

## What it does

Looks at the senders cluttering your inbox and tells you which ones are safe to archive in bulk, sorting them into confidence tiers — high (marketing, promotions, newsletters, sales), medium (notifications, alerts, receipts, updates), and low (everything else / personal) — so you can clear the obviously-junk pile in one sweep without accidentally archiving something from a real person.

## Why it exists

"Archive everything older than a month" is too blunt — it buries things you needed. "Archive nothing" leaves you drowning. The job-to-be-done is **giving the user a pre-sorted, risk-ranked pile** so the decision becomes "yes, nuke all the marketing" (zero risk) versus "let me look at these notifications" (some risk) versus "leave my personal mail alone." The confidence tier is the product: it turns an anxiety-inducing bulk delete into a series of low-stakes calls.

## How it actually works

The classifier is deliberately simple and transparent: it works off the **category name already assigned to each sender** (categories come from the app's sender-categorization feature). For each sender it lowercases the category name and does substring matching:

- **High confidence** if the category name contains "marketing", "promotion", "newsletter", or "sale" → reason: marketing-type mail, safe to archive.
- **Medium confidence** if it contains "notification", "alert", "receipt", or "update" → machine-generated, probably safe but you might want some.
- **Low confidence** for everything else → reason "Other category" → don't bulk-archive without looking.

It takes a list of senders (address, name, assigned category) and returns each one tagged with a confidence level and a short human-readable reason. There are no time windows or volume thresholds in this scoring step — it's purely category-name-driven, which keeps it predictable and explainable. The actual archiving (moving the messages) is then executed per-sender through the email provider; this feature is the *triage/scoring* half that decides what's safe.

## The non-obvious parts

- **It's intentionally dumb (substring on category name), and that's a feature.** A fancy ML classifier would be opaque; a keyword match on an already-assigned category is fully explainable ("high confidence because the category is 'Newsletters'"). Transparency matters more than precision when the action is destructive-ish.
- **The real intelligence is upstream.** The quality of this depends entirely on the sender-categorization feature that assigned the category names. This step just maps categories → risk. (That upstream categorizer is itself an LLM feature; this is the cheap deterministic consumer of it.)
- **Confidence tiers reframe the UX.** By never offering "archive all" as one button — only "archive the high-confidence ones" — it makes bulk archiving psychologically safe. The tiering *is* the safety mechanism.
- **Scoring is decoupled from execution.** This function only produces candidates + reasons; moving the mail is a separate provider call. That separation makes it dry-runnable and testable without touching the mailbox.

## Related

- [[bulk-unsubscriber--from-inbox-zero]] — sibling cleanup tool; a sender can be both unsubscribed and bulk-archived.
- [[ai-rules-engine--from-inbox-zero]] — the ARCHIVE action does the same archive op automatically per-rule.
- [[email-provider-abstraction--from-inbox-zero]] — the archive itself runs through the provider's archive method.
- See also: any risk-tiered bulk-action UX (bulk delete, bulk approve) where confidence tiers replace an all-or-nothing button.
