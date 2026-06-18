# Rule-Based Lead Scoring (build spec) — distilled from auto-crm

## Summary
A pure, deterministic function that maps a contact (+ its activities + its deals) to a 0–100 score,
plus a second function that buckets the score into a `cold | warm | hot` temperature. Additive
weighted signals: temperature base + contact completeness + capped engagement − recency decay +
deal-value bonus, clamped to [0,100]. Offline, no AI, no DB writes inside the calc. Used as the
default classifier and as the fallback when the optional LLM classifier is disabled or errors.

## Core logic (inlined)

```ts
type Temperature = "cold" | "warm" | "hot";

interface ScoreInput {
  temperature: Temperature;            // current manual/derived tag
  email?: string | null;
  phone?: string | null;
  company?: string | null;
  activities: { createdAt: Date | number }[];   // all logged touches
  deals: { value: number }[];                    // open deals on this contact
  // "last activity" = most recent activities[].createdAt; if none, treat as very old / no penalty basis
  lastActivityAt?: Date | number | null;
}

function calculateLeadScore(c: ScoreInput): number {
  let score = 0;

  // 1. Temperature base
  score += c.temperature === "hot" ? 40 : c.temperature === "warm" ? 25 : 10;

  // 2. Contact completeness
  if (c.email)   score += 10;
  if (c.phone)   score += 10;
  if (c.company) score += 5;

  // 3. Engagement (5 per activity, capped at 20)
  score += Math.min(c.activities.length * 5, 20);

  // 4. Recency penalty (days since last activity)
  if (c.lastActivityAt != null) {
    const last = typeof c.lastActivityAt === "number" ? c.lastActivityAt : c.lastActivityAt.getTime();
    const days = (Date.now() - last) / 86_400_000;
    if (days > 30)      score -= 15;
    else if (days > 14) score -= 10;
    else if (days > 7)  score -= 5;
  }

  // 5. Deal bonus
  if (c.deals.length > 0) {
    score += 10;
    const maxValue = Math.max(...c.deals.map(d => d.value));
    if (maxValue > 100_000) score += 5;
    if (maxValue > 500_000) score += 5;   // stacks: a >$500k deal earns the full +20
  }

  // Clamp
  return Math.max(0, Math.min(100, score));
}

function suggestTemperature(score: number): Temperature {
  if (score >= 70) return "hot";
  if (score >= 40) return "warm";
  return "cold";
}
```

**Exact weights (the contract — keep these stable or re-tune intentionally):**

| Signal | Rule | Points |
|---|---|---|
| Temperature base | hot / warm / cold | 40 / 25 / 10 |
| Email present | — | +10 |
| Phone present | — | +10 |
| Company present | — | +5 |
| Engagement | 5 × activityCount, capped | +0…20 |
| Recency | >30d / >14d / >7d since last activity | −15 / −10 / −5 |
| Has any deal | — | +10 |
| Max deal value > $100k | — | +5 |
| Max deal value > $500k | — | +5 (stacks) |
| Clamp | final | [0, 100] |

**Output thresholds:** `>=70` hot, `>=40` warm, else cold. These intentionally differ from the
base-tier inputs so the engine can *disagree* with a stale manual tag.

## Data contracts
- **Input:** one contact row + its `activities[]` (need `createdAt` to find the most recent) +
  its open `deals[]` (need `value`). Temperature is the contact's current tag.
- **Output:** `{ score: number, temperature: Temperature }`. The score is also returned to callers
  that want to display/sort by it.
- **Persistence (at the call site, not inside the fn):** `UPDATE contacts SET score=?, temperature=?,
  updatedAt=now WHERE id=?`. In auto-crm this is the `POST /api/classify { contactId }` route:
  load contact → load its activities + deals → compute → write back → return
  `{ temperature, score, mode: "rules" }`.

## Dependencies & assumptions
- **Zero runtime deps.** Plain arithmetic + `Date.now()`. No AI, no network.
- Assumes deal `value` is an integer in a single currency whose magnitude makes $100k/$500k
  meaningful — auto-crm displays MXN but the thresholds are round USD-style numbers. **Re-tune the
  deal tiers for your currency.**
- Recency uses raw calendar days (includes weekends/holidays), no timezone handling.

## To port this, you need:
- [ ] A `contacts` table/entity with a mutable `score:int` and `temperature:enum` field.
- [ ] A way to count/fetch a contact's `activities` and read each one's timestamp.
- [ ] A way to fetch a contact's open `deals` with a numeric `value`.
- [ ] A call site (API route / job / button handler) that runs the calc and writes the two fields back.
- [ ] (Optional) a re-score trigger: on new activity, on new/updated deal, on a nightly sweep — so
      the recency decay actually takes effect over time.

## Gotchas
- **Leads created by import/webhook start at score 0 / cold** and stay there until something runs
  this calc. If you never trigger a re-score, the whole queue is meaningless. Wire a trigger.
- **Engagement cap vs. uncapped decay:** a busy lead that goes quiet loses points faster than it
  could ever gain from activity. Intended, but surprising if you expected symmetry.
- **Base tiers ≠ output thresholds.** Don't "simplify" them to match — the gap is the feature
  (lets the system recommend re-tagging).
- **`Math.max(...[])` on an empty deals array returns `-Infinity`** — guard with `deals.length > 0`
  before computing `maxValue` (the code does; keep it).
- **Currency thresholds are magic numbers.** Hoist them to config if you support multiple currencies.

## Origin (reference only)
auto-crm — `src/lib/scoring.ts` (`calculateLeadScore`, `suggestTemperature`); consumed by
`src/app/api/classify/route.ts` (rules-path) and the contact list sort/filter UI.
