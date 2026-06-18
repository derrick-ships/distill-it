# CRM Dashboard KPIs & Analytics (build spec) — distilled from auto-crm

## Summary
A read-only dashboard: a row of KPI cards (contact count, active deals, pipeline value, conversion
rate) over Recharts visualizations (deals-by-stage bar, contacts-by-temperature breakdown). All
aggregation is computed **server-side once** and reused by both the web UI and the MCP `crm_get_stats`
tool, so numbers never drift between the chart and the chatbot. "Active/won/lost" keys off stage
`isWon`/`isLost` flags, not stage names. Stage colors and temperature colors are shared design tokens
reused across board, cards, and charts.

## Core logic (inlined)

### Server-side aggregation (shared by dashboard + `crm_get_stats`)
```ts
function getStats(db) {
  const contacts = db.prepare("SELECT temperature FROM contacts").all();
  const contactCount = contacts.length;
  const byTemperature = {
    cold: contacts.filter(c => c.temperature === "cold").length,
    warm: contacts.filter(c => c.temperature === "warm").length,
    hot:  contacts.filter(c => c.temperature === "hot").length,
  };

  // join deals to stages to know won/lost via flags (NOT names)
  const deals = db.prepare(`
    SELECT d.value, s.isWon, s.isLost
    FROM deals d JOIN pipelineStages s ON d.stageId = s.id`).all();

  const totalDeals = deals.length;
  const wonDeals   = deals.filter(d => d.isWon).length;
  const lostDeals  = deals.filter(d => d.isLost).length;
  const activeDeals = deals.filter(d => !d.isWon && !d.isLost).length;

  // pipeline value = sum of OPEN (non-terminal) deal values
  const pipelineValue = deals
    .filter(d => !d.isWon && !d.isLost)
    .reduce((sum, d) => sum + d.value, 0);

  const conversionRate = totalDeals > 0 ? wonDeals / totalDeals : 0;  // naive: won / total

  return { contactCount, byTemperature, totalDeals, wonDeals, lostDeals,
           activeDeals, pipelineValue, conversionRate };
}
```

### KPI cards (front end)
```tsx
<StatCard label="Contactos"        value={stats.contactCount} />
<StatCard label="Deals activos"    value={stats.activeDeals} />
<StatCard label="Valor de pipeline" value={formatCurrency(stats.pipelineValue)} />   // MXN
<StatCard label="Tasa de conversión" value={`${Math.round(stats.conversionRate * 100)}%`} />
```

### Charts (Recharts)
```tsx
// deals per stage, bars colored by each stage's own color
<BarChart data={stageData /* [{ name, count, color }] */}>
  <XAxis dataKey="name" /><YAxis /><Tooltip />
  <Bar dataKey="count">
    {stageData.map((s, i) => <Cell key={i} fill={s.color} />)}
  </Bar>
</BarChart>

// contacts by temperature, palette = shared temperature colors
const TEMP_COLORS = { hot: "#dc2626", warm: "#ea580c", cold: "#64748b" };
<PieChart>
  <Pie data={[
    { name: "Caliente", value: stats.byTemperature.hot,  fill: TEMP_COLORS.hot },
    { name: "Tibio",    value: stats.byTemperature.warm, fill: TEMP_COLORS.warm },
    { name: "Frío",     value: stats.byTemperature.cold, fill: TEMP_COLORS.cold },
  ]} dataKey="value" nameKey="name" />
</PieChart>
```

### Formatting helpers
```ts
const formatCurrency = (n: number) =>
  new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" }).format(n);
```

## Data contracts
- **Stats payload:** `{ contactCount, byTemperature:{cold,warm,hot}, totalDeals, wonDeals, lostDeals,
  activeDeals, pipelineValue, conversionRate }` (conversionRate is a 0–1 fraction).
- **Stage chart row:** `{ name, count, color }`. **Temperature row:** `{ name, value, fill }`.
- **Inputs:** `contacts.temperature`; `deals.value` + joined `pipelineStages.isWon/isLost/color`.

## Dependencies & assumptions
- `recharts`, React. `Intl.NumberFormat` for currency (locale `es-MX`/MXN — change for your market).
- Requires `pipelineStages` to carry `isWon`/`isLost`/`color`; without the flags, won/active/lost are
  ambiguous.
- Assumes the same aggregation is callable from both the web layer and any agent/MCP layer.

## To port this, you need:
- [ ] A single `getStats()` aggregation in a place both the web route and any agent tool can import.
- [ ] `pipelineStages.isWon` / `isLost` flags (seed them) so won/active math is name-independent.
- [ ] A `color` per stage and a temperature color palette, defined once as tokens.
- [ ] KPI card + Recharts (or any chart lib) components reading the stats payload.
- [ ] A currency formatter for your locale.

## Gotchas
- **Compute stats once, reuse everywhere.** If the dashboard and the agent compute independently they
  *will* diverge. Share one function.
- **Don't derive won/lost from stage names.** Names get renamed/translated; use the boolean flags.
- **`conversionRate` is naive (won/total, all-time, unweighted).** Fine for SMB; if you need
  time-windowed or value-weighted conversion, compute it separately and label it.
- **Pipeline value = open deals only.** Decide explicitly whether won deals count; here they don't
  (they've left the pipeline). Document it on the card or it'll confuse users.
- **Currency locale is baked in (MXN).** Externalize it if you support multiple markets.
- **Empty-state divide-by-zero:** guard `totalDeals > 0` before computing conversion (shown).

## Origin (reference only)
auto-crm — `src/components/dashboard/*` (KPI cards + Recharts); aggregation mirrors MCP
`crm_get_stats` in `mcp/crm-server.ts`; colors/temperature palette in `src/lib/constants.ts`;
stage flags seeded by `scripts/init.ts`.
