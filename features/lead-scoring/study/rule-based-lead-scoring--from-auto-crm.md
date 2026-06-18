# Rule-Based Lead Scoring — from [auto-crm](https://github.com/Hainrixz/auto-crm)

> Domain: [[_domain]] · Source: https://github.com/Hainrixz/auto-crm (`src/lib/scoring.ts`) · NotebookLM: <add link>

## What it does
Every contact in the CRM gets a number from 0 to 100 that says, at a glance, "how good is this
lead right now?" — and a one-word temperature (cold / warm / hot) derived from that number. The
score isn't a black box: it's a transparent, deterministic formula you can read off in your head.
A hot lead with full contact details, recent activity, and a big open deal lands near the top; a
contact you grabbed an email for three months ago and never touched sinks toward zero. It's the
default engine that powers the "temperature" filter, the sort order of the contact list, and the
fallback whenever the optional AI classifier isn't turned on.

## Why it exists
A salesperson with 400 contacts can't manually decide who to call first. The job-to-be-done is
**triage**: turn a pile of contacts into a ranked queue so the rep spends today on the leads most
likely to close. The product deliberately ships this as a *rule-based* engine (not AI-first)
because (1) it must work offline, locally, with zero API keys — the whole product's pitch is
"runs on your machine, no subscription"; (2) the rep needs to *trust and predict* the score, which
a transparent formula gives and an LLM doesn't; and (3) it's free and instant. The AI classifier
is an optional upgrade layered on top, not a dependency.

## How it actually works
The score is built up from five independent signals that are simply added together, then clamped
to the 0–100 range.

1. **Temperature base** — where the lead already sits is the biggest single lever. A lead already
   marked *hot* starts at 40 points, *warm* at 25, *cold* at 10. This makes the score sticky:
   manual judgment by the rep carries real weight and isn't washed out by the mechanical signals.

2. **Contact completeness** — the more you can actually reach them, the more real the lead. Having
   an email adds 10, a phone adds 10, a company adds 5. A lead you can't contact is worth less,
   mechanically.

3. **Engagement** — each logged activity (call, email, meeting, note, follow-up) is worth 5 points,
   but the total is capped at 20. So roughly four touches max out this component; beyond that,
   activity volume stops inflating the score. Engagement matters, but it can't dominate.

4. **Recency penalty** — this is the decay mechanism, and it's where the score earns its keep. The
   longer since the last activity, the more points come *off*: more than 7 days costs 5, more than
   14 costs 10, more than 30 costs 15. A lead that was hot last month but has gone quiet will
   visibly cool down on its own. This is what keeps the queue honest over time.

5. **Deal bonus** — money talks. Any open deal attached to the contact adds 10; a deal worth over
   $100k adds another 5; over $500k adds a further 5 (so a half-million-dollar deal is worth the
   full 20-point deal bonus). Pipeline value pulls a lead up regardless of how chatty they've been.

Add the five, clamp to [0, 100], and that's the score. Then a second tiny function turns the number
back into a word: **70 or above is hot, 40 to 69 is warm, below 40 is cold**. Note the asymmetry
worth understanding: the *base* tiers (40/25/10) and the *output* thresholds (70/40) are different
numbers — a contact you marked "hot" starts at 40 base, which alone only gets it to warm; it needs
the completeness/engagement/deal signals to actually re-earn the hot label. The system can therefore
*disagree* with the human's manual tag and suggest a correction.

## The non-obvious parts
- **The thresholds and the base scores deliberately don't match.** A "hot" tag is an input worth 40,
  but "hot" as an *output* needs 70. This gap is the feature: it lets the engine recommend
  re-classifying a lead whose manual tag no longer matches its behavior.
- **Engagement is capped but recency is not.** You can only earn 20 points for being active, but you
  can lose 15 for going cold — and those stack. A formerly-busy lead decays faster than a steadily-
  warm one, which is the correct sales instinct.
- **It's stateless and pure.** The function takes the contact, its activities, and its deals and
  returns a number — no DB writes inside the calculation. Persistence happens at the call site
  (the `/api/classify` route writes `score` and `temperature` back). This makes it trivially
  testable and re-runnable.
- **Currency thresholds are hard-coded in USD-ish round numbers** ($100k / $500k) even though the
  rest of the app formats money as Mexican pesos. A porting gotcha: the deal-bonus tiers assume a
  particular currency magnitude.
- **No time zones, no business days.** Recency is raw calendar-day deltas. "30 days" includes
  weekends and holidays.

## Related
- [[ai-lead-classification--from-auto-crm]] — the optional LLM upgrade that replaces this formula
  when an API key is present; this rule engine is its fallback.
- [[webhook-lead-ingestion--from-auto-crm]] — creates leads at score 0 / cold; they only get a real
  score once this engine runs against them.
- See also: any "RICE"/"lead grading" scheme — same idea (weighted additive signals → tier), here
  kept deliberately simple and offline.
