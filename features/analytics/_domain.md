# Domain: analytics

Turning stored business data into at-a-glance situational awareness — KPI scoreboards and charts
that answer "what's the shape of things right now?" without a query or an export.

## What this domain is about

Analytics here is **summarization for decisions**, not data science. A CRM (or any operational tool)
accumulates rows; the analytics layer compresses them into the handful of numbers a user opens the
app to learn: how much is in the pipeline, where it's stuck, am I converting. The win is immediacy
and visual legibility — the database becomes a decision tool the moment its state is summarized on a
dashboard.

## Pattern shared across features in this domain

Aggregate **server-side, once**, and reuse the result everywhere (web UI *and* any agent/MCP tool) so
the numbers never drift between surfaces. Derive categorical truth from **flags, not names** (e.g.
won/lost via boolean stage flags so renames don't break math). Treat color/format as **shared design
tokens** reused across board, cards, and charts for visual continuity. Keep the metrics naive and
explainable (e.g. conversion = won/total) unless a richer model is specifically needed.

## Features in this domain

- [[crm-dashboard-kpis--from-auto-crm]] — KPI cards (contacts, active deals, pipeline value,
  conversion) + Recharts breakdowns (deals-by-stage, contacts-by-temperature), built on one shared
  `getStats()` aggregation also exposed to Claude as `crm_get_stats`.
