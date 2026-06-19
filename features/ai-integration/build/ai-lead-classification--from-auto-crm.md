# AI Lead Classification (Claude) (build spec) — distilled from auto-crm

## Summary
An optional LLM upgrade for lead grading. A lazily-constructed Anthropic client (null when no API
key → that null IS the feature flag) calls Claude Sonnet with the contact + its activity history and
asks for a strict JSON verdict `{ temperature, confidence, nextAction, reasoning }` in Spanish.
Response is parsed by scraping the first `{...}` block with a regex (robust to prose/markdown
wrapping). On *any* failure — no key, network, bad JSON — it silently falls back to the deterministic
rule-based scorer and returns a well-formed default. Both paths write the same `temperature`/`score`
back to the contact, distinguished only by a `mode: "ai" | "rules"` field.

## Core logic (inlined)

### Client module (`claude.ts`)
```ts
import Anthropic from "@anthropic-ai/sdk";

let client: Anthropic | null = null;

function getClient(): Anthropic | null {
  if (client) return client;
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) return null;             // no key => disabled
  client = new Anthropic({ apiKey });
  return client;
}

export function isAIEnabled(): boolean {
  return getClient() !== null;          // presence of key = the on/off switch
}

interface LeadClassification {
  temperature: "cold" | "warm" | "hot";
  confidence: number;        // 0..100
  nextAction: string;        // Spanish
  reasoning: string;         // Spanish
}

const FALLBACK: LeadClassification = {
  temperature: "cold",
  confidence: 25,
  nextAction: "Revisar manualmente",
  reasoning: "El análisis con IA no está disponible.",
};

export async function classifyLead(
  contact: { name: string; company?: string|null; source?: string|null; notes?: string|null },
  activities: { type: string; description: string; date: string }[],
): Promise<LeadClassification> {
  const c = getClient();
  if (!c) return FALLBACK;

  const prompt = `Eres un asistente de ventas. Clasifica este lead por temperatura.

Contacto:
- Nombre: ${contact.name}
- Empresa: ${contact.company ?? "N/D"}
- Origen: ${contact.source ?? "N/D"}
- Notas: ${contact.notes ?? "N/D"}

Historial de interacciones (${activities.length}):
${activities.map(a => `- [${a.date}] ${a.type}: ${a.description}`).join("\n") || "Sin interacciones"}

Responde SOLO con un objeto JSON con esta forma exacta:
{"temperature":"cold|warm|hot","confidence":0-100,"nextAction":"...","reasoning":"..."}
Escribe nextAction y reasoning en español.`;

  try {
    const res = await c.messages.create({
      model: "claude-sonnet-4-6-20250514",   // see Gotchas re: model id pinning
      max_tokens: 500,
      messages: [{ role: "user", content: prompt }],
    });

    const text = res.content
      .filter((b): b is { type: "text"; text: string } => b.type === "text")
      .map(b => b.text).join("");

    const match = text.match(/\{[\s\S]*\}/);   // first { ... } span
    if (!match) return FALLBACK;
    const parsed = JSON.parse(match[0]) as LeadClassification;
    return parsed;
  } catch {
    return FALLBACK;                            // total fallback, no rethrow
  }
}
```

### Route that chooses AI vs rules (`/api/classify`)
```ts
// POST { contactId }
const contact = await getContact(contactId);           // 404 if missing
const activities = await getActivities(contactId);
const deals = await getDeals(contactId);

let result;
if (isAIEnabled()) {
  try {
    const ai = await classifyLead(
      { name: contact.name, company: contact.company, source: contact.source, notes: contact.notes },
      activities.map(a => ({ type: a.type, description: a.description, date: fmtDate(a.createdAt) })),
    );
    result = { temperature: ai.temperature, score: ai.confidence, nextAction: ai.nextAction,
               reasoning: ai.reasoning, mode: "ai" };
  } catch {
    result = ruleBased(contact, activities, deals);     // mode: "rules"
  }
} else {
  result = ruleBased(contact, activities, deals);       // mode: "rules"
}

// identical write for both paths:
await db.update(contacts)
  .set({ temperature: result.temperature, score: result.score, updatedAt: new Date() })
  .where(eq(contacts.id, contactId));

return Response.json(result);
```

## Data contracts
- **Request:** `POST /api/classify { contactId: string }`.
- **Claude response (target JSON):** `{ "temperature": "cold|warm|hot", "confidence": 0-100,
  "nextAction": string, "reasoning": string }` — Spanish strings.
- **API response:**
  - AI path → `{ temperature, score, nextAction, reasoning, mode: "ai" }` (score = confidence)
  - rules path → `{ temperature, score, nextAction, reasoning, mode: "rules" }`
- **Persistence:** `contacts.temperature`, `contacts.score`, `contacts.updatedAt` — identical for
  both modes.

## Dependencies & assumptions
- `@anthropic-ai/sdk`, env var `ANTHROPIC_API_KEY`. Model: Claude Sonnet, `max_tokens: 500`.
- Requires the rule-based scorer (`calculateLeadScore`/`suggestTemperature`) as the fallback — port
  that first (see `[[rule-based-lead-scoring--from-auto-crm]]`).
- Assumes a single LLM object response small enough for one regex-extracted block.

## To port this, you need:
- [ ] Anthropic SDK + `ANTHROPIC_API_KEY` env wiring (or swap to your provider's client).
- [ ] The rule-based scorer present as the fallback path.
- [ ] A `contacts` entity with `temperature` + `score` writeable fields.
- [ ] A classify endpoint/handler that: loads contact+activities(+deals), branches on
      `isAIEnabled()`, try/catches the AI call, writes back, returns `{...mode}`.
- [ ] (Recommended) replace the magic model id with a config constant and consider the SDK's
      structured-output / tool-use mode instead of regex scraping (see Gotchas).

## Gotchas
- **Pin/verify the model id.** The original hard-codes `claude-sonnet-4-6-20250514`. Use the
  current Sonnet id for your account and centralize it; a stale id silently 404s → fallback fires
  and you "lose" AI without an error. For new builds, default to the latest capable Claude model.
- **Regex JSON extraction is greedy & assumes one object.** `\{[\s\S]*\}` grabs first `{` to last
  `}` — if the model emits two objects or stray braces it breaks. Prefer the SDK's JSON/tool-use
  mode for production; the regex is a cheap hedge, not a guarantee.
- **The fallback is total and silent.** Failures never reach the user; an expired key or wrong model
  id just degrades to rules quietly. Add server-side logging/metrics on the catch so you can *see*
  AI failing.
- **Confidence is reused as `score`.** The AI's 0–100 confidence is stored in the same `score`
  column the rule engine writes. Fine, but the two scales aren't strictly comparable — don't mix
  them in analytics without noting the `mode`.
- **Spanish-first prompt.** Output strings go straight into the UI; if you localize elsewhere,
  change the prompt's language instruction too.
- **Activity history can be large.** With `max_tokens: 500` only the *output* is capped; the input
  prompt with a long history can grow — truncate/summarize activities for very active contacts.

## Origin (reference only)
auto-crm — `src/lib/claude.ts` (`getClient`, `isAIEnabled`, `classifyLead`, fallback object);
`src/app/api/classify/route.ts` (AI-vs-rules branch, shared write).
