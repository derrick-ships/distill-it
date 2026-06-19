# CSV Import / Export (build spec) — distilled from auto-crm

## Summary
Two endpoints for data portability. **Import** (`POST`) takes `{ contacts: [...] }` JSON (CSV→objects
parsing is client-side), bulk-inserts with defaults, requires `name` per row, and is **partial-
success**: returns `{ imported, failed, errors }` with `201` (all ok) or `207` (some failed).
**Export** (`GET ?type=contacts|deals`) builds a CSV with correct escaping (commas/quotes/newlines),
a **UTF-8 BOM** for Excel, humanized values (temperature→Spanish, currency-formatted deal value),
served as `text/csv` attachment with a dated filename.

## Core logic (inlined)

### Import (`POST /api/import`)
```ts
const body = await req.json().catch(() => null);
if (!body || !Array.isArray(body.contacts) || body.contacts.length === 0)
  return Response.json({ error: "Se requiere un array de contactos" }, { status: 400 });

let imported = 0, failed = 0;
const errors: string[] = [];

for (const [i, row] of body.contacts.entries()) {
  if (!row?.name) { failed++; errors.push(`Fila ${i + 1}: falta el nombre`); continue; }
  try {
    db.prepare(`INSERT INTO contacts (id,name,email,phone,company,source,temperature,score,notes,createdAt,updatedAt)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)`)
      .run(crypto.randomUUID(), row.name, row.email ?? null, row.phone ?? null, row.company ?? null,
           row.source ?? "import", row.temperature ?? "cold", row.score ?? 0, row.notes ?? null,
           Date.now(), Date.now());
    imported++;
  } catch (e) {
    failed++; errors.push(`Fila ${i + 1}: ${(e as Error).message}`);
  }
}

return Response.json({ imported, failed, errors }, { status: failed > 0 ? 207 : 201 });
```

### Export (`GET /api/export?type=contacts|deals`)
```ts
const escapeCSV = (v: unknown) => {
  const s = v == null ? "" : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;   // quote+double internal quotes
};

const buildCSV = (headers: string[], rows: string[][]) =>
  [headers, ...rows].map(r => r.map(escapeCSV).join(",")).join("\n");

const TEMP_ES = { hot: "Caliente", warm: "Tibio", cold: "Frío" };
const fmtMoney = (n: number) => new Intl.NumberFormat("es-MX", { style:"currency", currency:"MXN" }).format(n);
const today = new Date().toISOString().slice(0, 10);   // YYYY-MM-DD

const type = new URL(req.url).searchParams.get("type") ?? "contacts";
let csv: string, filename: string;

if (type === "contacts") {
  const rows = db.prepare("SELECT * FROM contacts ORDER BY createdAt DESC").all();
  csv = buildCSV(
    ["Nombre","Email","Teléfono","Empresa","Origen","Temperatura","Score","Notas","Creado"],
    rows.map(c => [c.name, c.email, c.phone, c.company, c.source,
                   TEMP_ES[c.temperature] ?? c.temperature, c.score, c.notes,
                   new Date(c.createdAt).toLocaleDateString("es-MX")]),
  );
  filename = `contactos-${today}.csv`;
} else if (type === "deals") {
  const rows = db.prepare(`
    SELECT d.*, c.name AS contactName, s.name AS stageName, s."order" AS stageOrder
    FROM deals d JOIN contacts c ON d.contactId=c.id JOIN pipelineStages s ON d.stageId=s.id
    ORDER BY s."order"`).all();
  csv = buildCSV(
    ["Título","Valor","Contacto","Etapa","Probabilidad","Cierre esperado","Notas","Creado"],
    rows.map(d => [d.title, fmtMoney(d.value), d.contactName, d.stageName, `${d.probability}%`,
                   d.expectedClose ? new Date(d.expectedClose).toLocaleDateString("es-MX") : "",
                   d.notes, new Date(d.createdAt).toLocaleDateString("es-MX")]),
  );
  filename = `deals-${today}.csv`;
} else {
  return Response.json({ error: "type debe ser 'contacts' o 'deals'" }, { status: 400 });
}

return new Response("﻿" + csv, {                 // ﻿ = UTF-8 BOM for Excel
  status: 200,
  headers: {
    "Content-Type": "text/csv; charset=utf-8",
    "Content-Disposition": `attachment; filename="${filename}"`,
  },
});
```

## Data contracts
- **Import req:** `POST { contacts: Array<{ name*, email?, phone?, company?, source?, temperature?,
  score?, notes? }> }`. **Resp:** `{ imported:int, failed:int, errors:string[] }`,
  status `201` (none failed) or `207` (some failed); `400` if no array.
- **Export req:** `GET ?type=contacts|deals`. **Resp:** CSV body (BOM-prefixed) with the column sets
  above; `400` on bad `type`.
- **Import defaults:** `source="import"`, `temperature="cold"`, `score=0`, timestamps=now.

## Dependencies & assumptions
- A `contacts` table (and `deals` + `pipelineStages` for deal export). `Intl.NumberFormat` for money.
- CSV file parsing is assumed to happen client-side before import (this endpoint takes JSON).
- Locale `es-MX` and Spanish headers/temperature words are baked in.

## To port this, you need:
- [ ] An import handler that loops rows, skips invalid (name required), tallies, returns 201/207.
- [ ] `escapeCSV` (quote values containing `" , \n`, double internal quotes) + `buildCSV`.
- [ ] BOM prefix + `text/csv; charset=utf-8` + `Content-Disposition: attachment` + dated filename.
- [ ] Client-side CSV→objects parsing if you want raw .csv upload (e.g. PapaParse) feeding the POST.
- [ ] A post-import re-score step if imported leads should rank (they arrive at score 0).

## Gotchas
- **Don't forget the UTF-8 BOM (`﻿`).** Without it Excel mangles accents (`Frío`→`FrÃ­o`).
- **Partial success, not all-or-nothing.** Keep per-row try/catch + the 207 status; aborting the
  whole batch on one bad row is hostile to real spreadsheets.
- **Export is humanized, so it's not a lossless round-trip.** `"hot"`→`"Caliente"` and raw value→
  formatted currency won't re-import cleanly. If you need round-tripping, add a machine-format export.
- **Server takes JSON, not a file.** A common porting mistake is POSTing a raw CSV here — parse first.
- **`escapeCSV` is the whole ballgame.** Test values with embedded commas, quotes, and newlines; this
  is the classic CSV bug.
- **Quote/escape the filename** and sanitize `type` (only allow the two known values) to avoid header
  injection / unexpected queries.

## Origin (reference only)
auto-crm — `src/app/api/import/route.ts` (partial-success bulk insert) and
`src/app/api/export/route.ts` (`buildCSV`/`escapeCSV`, BOM, dual contacts/deals). Temperature words &
currency locale in `src/lib/constants.ts`.
