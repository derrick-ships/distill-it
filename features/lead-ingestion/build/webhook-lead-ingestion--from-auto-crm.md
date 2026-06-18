# Webhook Lead Ingestion (build spec) — distilled from auto-crm

## Summary
A single public `POST` endpoint that turns arbitrary form/automation JSON into a CRM contact.
Optional shared-secret auth via `x-webhook-secret`. Normalizes incoming keys (lowercase, trim,
spaces→underscores) and flattens Typeform-style nesting, then maps multilingual field aliases
(`name`/`nombre`/`full_name`, etc.) to CRM fields. Only `name` is required. Creates the contact with
defaults `source="webhook"`, `temperature="cold"`, `score=0`. Returns 201 with the new contact. No
dedup, no scoring on ingest — both are deliberate omissions to be aware of.

## Core logic (inlined)

```ts
// POST /api/webhook
export async function POST(req: Request) {
  // 1. Optional secret auth
  const configuredSecret = await getSetting("webhook_secret");  // from crmSettings, may be null
  if (configuredSecret) {
    const provided = req.headers.get("x-webhook-secret");
    if (provided !== configuredSecret) {
      return Response.json({ error: "No autorizado" }, { status: 401 });
    }
  }

  // 2. Parse JSON
  let body: any;
  try { body = await req.json(); }
  catch { return Response.json({ error: "JSON inválido" }, { status: 400 }); }

  // 3. Flatten Typeform-style nesting + normalize keys
  const flat = flatten(body);                 // e.g. { "form_response.answers...": v } -> reachable
  const norm: Record<string, any> = {};
  for (const [k, v] of Object.entries(flat)) {
    const key = k.toLowerCase().trim().replace(/\s+/g, "_");
    norm[key] = v;
  }

  // 4. Alias-map to CRM fields (first present alias wins)
  const FIELD_ALIASES = {
    name:    ["name", "nombre", "full_name", "fullname", "nombre_completo"],
    email:   ["email", "correo", "e-mail", "e_mail", "correo_electronico"],
    phone:   ["phone", "telefono", "teléfono", "tel", "celular", "movil"],
    company: ["company", "empresa", "organizacion", "organización", "compania"],
  } as const;

  const pick = (aliases: readonly string[]) => {
    for (const a of aliases) if (norm[a] != null && norm[a] !== "") return String(norm[a]);
    return null;
  };

  const name    = pick(FIELD_ALIASES.name);
  const email   = pick(FIELD_ALIASES.email);
  const phone   = pick(FIELD_ALIASES.phone);
  const company = pick(FIELD_ALIASES.company);

  // 5. Require name; on failure, echo received keys to aid debugging
  if (!name) {
    return Response.json(
      { error: "Falta el nombre", received: Object.keys(norm),
        hint: "Incluye un campo 'name' o 'nombre' en el payload." },
      { status: 400 },
    );
  }

  // 6. Insert with defaults
  const contact = await db.insert(contacts).values({
    name, email, phone, company,
    source: "webhook",
    temperature: "cold",
    score: 0,
    // createdAt/updatedAt default to now
  }).returning().then(r => r[0]);

  return Response.json(
    { success: true, contact: { id: contact.id, name: contact.name, email: contact.email, source: contact.source } },
    { status: 201 },
  );
}
```

`flatten()` walks nested objects/arrays into reachable keys so Typeform's
`{ form_response: { answers: [...] } }` shape exposes its leaf values; the simplest version is a
recursive object walk that also lifts common Typeform answer arrays into `{label: value}` pairs.

## Data contracts
- **Request:** `POST` JSON, any shape. Optional header `x-webhook-secret`.
- **Recognized fields (post-normalization):** name* (required), email, phone, company — via the
  alias table above. Unrecognized fields are ignored.
- **Success 201:** `{ success: true, contact: { id, name, email, source } }`
- **Errors:** `401 { error }` (bad/absent secret when one is configured),
  `400 { error: "JSON inválido" }`, `400 { error, received: string[], hint }` (no name),
  `500 { error }` (insert failure).
- **Created row defaults:** `source="webhook"`, `temperature="cold"`, `score=0`, timestamps=now.

## Dependencies & assumptions
- A `contacts` table with nullable email/phone/company and defaultable source/temperature/score.
- A settings store for the optional `webhook_secret` (auto-crm uses the `crmSettings` key/value
  table). If you don't store one, the endpoint is open.
- No queue/idempotency layer — handler is synchronous insert-on-request.

## To port this, you need:
- [ ] A public unauthenticated-by-default route (`POST /api/webhook` or equivalent).
- [ ] A `contacts` entity accepting partial data with defaults.
- [ ] A settings/secret lookup for `x-webhook-secret` (recommend making a secret *mandatory* in
      production — see Gotchas).
- [ ] The key-normalization + alias-mapping helper (extend the alias lists for your locales/forms).
- [ ] (Strongly recommended, not in the original) dedup-on-email and a post-insert classify trigger.

## Gotchas
- **No dedup — every POST = a new contact.** A retrying sender or double-submit floods the table.
  Add an "upsert by email" or a recent-duplicate check before going live.
- **Open by default.** If no secret is configured the URL accepts anything from anyone. Treat a
  configured secret as required in production; consider rate-limiting too.
- **Leads land unscored (cold/0).** Nothing grades them on ingest. Fire the classifier
  (`[[rule-based-lead-scoring--from-auto-crm]]` / AI) after insert, or they're invisible in any
  temperature-sorted queue.
- **Greedy `flatten` on huge/recursive payloads** can be slow or explode key counts — bound depth.
- **Alias lists are finite.** A form using an unanticipated field name silently drops that field
  (or fails the name check). The `received` echo on 400 is your debugging lifeline — keep it.
- **No CSRF/origin checks** — it's a machine-to-machine endpoint; don't reuse the same handler for
  browser-originated requests without auth.

## Origin (reference only)
auto-crm — `src/app/api/webhook/route.ts`. Default source/temperature constants align with
`src/lib/constants.ts` (source list includes `"webhook"`).
