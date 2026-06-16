# Bulk Archiver (build spec) — distilled from inbox-zero

## Summary

Score senders into archive-confidence tiers (high/medium/low) purely from each sender's assigned category name via substring matching, returning candidates + human-readable reasons for a risk-tiered bulk-archive UI. Scoring is decoupled from execution (the actual archive runs through the provider). Assume the source repo is gone; everything needed is below.

## Core logic (inlined)

```
getArchiveCandidates(groups: EmailGroup[]) -> ArchiveCandidate[]

  HIGH   = ["marketing", "promotion", "newsletter", "sale"]
  MEDIUM = ["notification", "alert", "receipt", "update"]

  return groups.map(g => {
    cat = (g.category?.name ?? "").toLowerCase()
    if HIGH.some(k => cat.includes(k)):
        return { ...g, confidence: "high",   reason: "Marketing/newsletter category" }
    if MEDIUM.some(k => cat.includes(k)):
        return { ...g, confidence: "medium", reason: "Automated notification/receipt category" }
    return   { ...g, confidence: "low",    reason: "Other category" }
  })
```

No time windows, no volume thresholds, no sender filters in this step — category-name substring only. The UI typically offers "archive all HIGH" as the safe one-sweep action and requires per-item confirmation for medium/low.

Execution (separate): for each chosen sender, archive their messages via the provider abstraction (`provider.archiveMessage` / batch archive), and optionally mark the `Newsletter.status = AUTO_ARCHIVED` so future mail auto-archives.

## Data contracts

```ts
type EmailGroup = {
  address: string
  name?: string
  category?: { id: string; name: string }   // assigned upstream by sender categorization
}

type ArchiveCandidate = EmailGroup & {
  confidence: "high" | "medium" | "low"
  reason: string
}
```

Relevant persisted status (shared with the unsubscriber):
```prisma
enum NewsletterStatus { APPROVED  UNSUBSCRIBED  AUTO_ARCHIVED }
// Newsletter.status = AUTO_ARCHIVED marks a sender for ongoing auto-archive
```

## Dependencies & assumptions

- **An upstream sender-categorizer** that assigns category names to senders. This feature is worthless without it — the entire signal is the category name. (In inbox-zero that's an LLM categorization feature; you can substitute any categorizer or even user-assigned categories.)
- **A way to enumerate senders with their categories** (the "who's emailing you" aggregation — overlaps with email analytics).
- **The provider abstraction** to perform the archive ([[email-provider-abstraction--from-inbox-zero]]).

## To port this, you need:
- [ ] A per-sender category name available at scoring time.
- [ ] The tier keyword lists (HIGH/MEDIUM) — tune to your categories.
- [ ] A scorer returning `{ confidence, reason }` per sender (pure function, dry-runnable).
- [ ] A separate executor that archives a sender's mail via your mail backend.
- [ ] (optional) Persist `AUTO_ARCHIVED` status so future mail from the sender keeps getting archived.

## Gotchas

- **Garbage in, garbage out** — if categories are wrong/missing, every sender lands in "low". The scorer is only as good as the categorizer.
- **Keep "archive all" off the high-stakes tiers.** The whole safety model is that only HIGH is one-click; don't add a global "archive everything" button.
- **Substring matching can false-positive** (e.g. a category literally named "Sales team" matches "sale"). Keep the keyword lists tight and the reasons visible so users can sanity-check.
- **Scoring must stay pure/side-effect-free** so it can be previewed without touching the mailbox; keep execution in a separate path.
- **Confirmed from source:** the tier keywords and confidence/reason output shape (`get-archive-candidates.ts`). The execution-side archive + AUTO_ARCHIVED persistence is the documented surrounding behavior, not in this single file.

## Origin (reference only)

Repo: https://github.com/elie222/inbox-zero —
`apps/web/utils/bulk-archive/get-archive-candidates.ts` (`getArchiveCandidates`, tier keyword lists, `ArchiveCandidate`).
`NewsletterStatus` enum in `apps/web/prisma/schema.prisma`. Archive execution via the email provider layer.
