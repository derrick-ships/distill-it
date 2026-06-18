# CRM Dashboard KPIs & Analytics — from [auto-crm](https://github.com/Hainrixz/auto-crm)

> Domain: [[_domain]] · Source: https://github.com/Hainrixz/auto-crm (`src/components/dashboard/`, stats via MCP `crm_get_stats` / API) · NotebookLM: <add link>

## What it does
It's the home screen of the CRM: the at-a-glance scoreboard a salesperson sees first. A row of big
KPI numbers (how many contacts, how many active deals, total pipeline value, conversion rate) sits
above charts that break the business down visually — deals by stage, contacts by temperature
(cold/warm/hot), pipeline value distribution. Instead of querying or exporting to a spreadsheet, you
open the app and immediately know the shape of your funnel and where the money is.

## Why it exists
The job-to-be-done is **situational awareness in one glance**. A CRM that only stores data is a
filing cabinet; a CRM that *summarizes* it tells you what to do today. The dashboard answers the
three questions every rep and manager opens the tool to ask: How much is in the pipeline? Where is
it stuck? Am I converting? Making those answers immediate (and visual) is what turns the database
into a decision tool — and it's the natural landing surface that frames everything else (pipeline
board, contacts, follow-ups).

## How it actually works
The numbers are computed server-side and handed to the UI ready to display — the front end doesn't
fetch raw rows and do arithmetic. The core aggregation (the same logic exposed to Claude as
`crm_get_stats`) counts total contacts, breaks them down by temperature, counts active (non-terminal)
deals, sums the value of open deals into a single **pipeline value**, and computes a **conversion
rate** as won deals over total deals. Because pipeline stages carry explicit `isWon`/`isLost` flags,
"active," "won," and "lost" are unambiguous — the math keys off those flags, not off stage names.

On the front end, the KPI cards are simple: a label and a formatted number (currency formatted in
Mexican pesos, percentages for conversion). The charts use **Recharts**, a React charting library:
typically a bar chart for deals-per-stage (colored to match each stage's configured color), and a
breakdown of contacts by temperature using the product's hot/warm/cold color palette (red / orange /
slate). The visual language is consistent with the rest of the app — the same stage colors and
temperature colors used on the Kanban board reappear here, so a stage is the same color wherever you
see it.

The dashboard is a *read* surface: it reflects the current state of contacts, deals, and stages and
recomputes when the data changes. It deliberately offloads the counting to the database/aggregation
layer so the page stays fast and the same numbers can be reused by the MCP server when Claude is
asked "how's my pipeline?"

## The non-obvious parts
- **Stats are computed once, server-side, and reused two ways.** The same aggregation feeds both the
  web dashboard and the MCP `crm_get_stats` tool. Compute-once-display-anywhere keeps the web UI and
  the conversational UI showing identical numbers — no drift between "what the chart says" and "what
  Claude says."
- **Won/lost are flags, not names.** Conversion rate and "active deals" depend on `isWon`/`isLost`
  booleans on stages, so renaming or translating a stage never breaks the analytics. This is why the
  seed data sets those flags explicitly.
- **Color is a shared design token, not per-chart.** Stage colors and temperature colors are defined
  once (in constants / stage records) and reused across the board, the cards, and the charts. A deal
  in "Negotiation" is the same orange on the board and in the bar chart — visual continuity that
  makes the dashboard instantly legible.
- **Currency is locale-formatted (MXN).** Pipeline value isn't a raw integer on screen; it's run
  through Mexican-peso formatting. A porting note: the formatting locale is baked in.
- **Conversion rate is naive on purpose.** Won / total deals — it doesn't time-window or weight by
  value. Simple, explainable, good enough for a small-business CRM; not a cohort-analysis engine.

## Related
- [[kanban-pipeline-dnd--from-auto-crm]] — the dashboard reads the same stages/deals the board lets
  you edit; board is write, dashboard is read.
- [[mcp-crm-server--from-auto-crm]] — `crm_get_stats` is the conversational twin of this dashboard,
  built on the identical aggregation.
- [[rule-based-lead-scoring--from-auto-crm]] — the temperature breakdown chart is only meaningful if
  leads are actually being scored/classified.
- See also: any funnel/pipeline dashboard (HubSpot, Pipedrive insights) — same KPI vocabulary.
