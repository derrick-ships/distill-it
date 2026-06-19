# Domain: lead-scoring

Turning a pile of leads/contacts into a ranked, triaged queue so a salesperson knows who to work
first — via a transparent score and a coarse temperature tier.

## What this domain is about

Lead scoring is the problem of **prioritization under volume**: given hundreds of contacts with
partial information and uneven engagement, produce a single comparable number (and a human-readable
tier like cold/warm/hot) that says how promising each one is *right now*. The score must be
re-computable as the world changes — new activity raises it, silence decays it, an open deal pulls
it up. The art is choosing signals that correlate with "likely to close" and weighting them so the
output is both useful and *trusted*.

## Pattern shared across features in this domain

A scorer is a pure function: `(contact, activities, deals) -> score:int(0..100)`, followed by a
threshold map `score -> tier`. Signals are typically **additive and weighted**: a base from the
current tier, bonuses for contact completeness and engagement, a recency *penalty* for going quiet,
and a bonus for attached pipeline value — then clamped. Persistence (writing score+tier back) and
the *trigger* (when to re-score) live at the call site, not inside the function. A rule-based scorer
can be the deterministic fallback under an optional AI classifier that shares the same write
contract.

## Features in this domain

- [[rule-based-lead-scoring--from-auto-crm]] — deterministic additive scorer (temperature base +
  completeness + capped engagement − recency decay + deal-value bonus → cold/warm/hot), offline and
  trusted; doubles as the fallback for the AI classifier.
