# MCP CRM Server — from [auto-crm](https://github.com/Hainrixz/auto-crm)

> Domain: [[_domain]] · Source: https://github.com/Hainrixz/auto-crm (`mcp/crm-server.ts`) · NotebookLM: <add link>

## What it does
It turns the CRM into something Claude can *operate* directly. Instead of you opening the web UI to
add a contact or move a deal, you type to Claude Desktop — "add Maria from Acme as a warm lead,"
"move the Acme deal to Negotiation," "what are my overdue follow-ups?" — and Claude does it by
calling the CRM's own tools. The whole CRM is exposed as ten well-named tools (list/create
contacts, list/create/move deals, log activities, read the pipeline, get follow-ups, get stats)
that any MCP-speaking client can call. It runs as a tiny local process talking to the same SQLite
database the web app uses, so the two stay perfectly in sync.

## Why it exists
This is the product's signature bet: a CRM whose primary interface can be a conversation. The
job-to-be-done is **let the salesperson run their pipeline by talking to an AI** rather than
clicking through forms. Because the CRM is local-first and file-based (SQLite), exposing it over MCP
is cheap and natural — no auth servers, no cloud API, just a local process reading a local file. It
also reinforces the "self-customizing, AI-native" positioning: the same Claude that can rewrite the
CRM's code (via the Claude Code commands) can also *use* it day-to-day through these tools.

## How it actually works
The server is a small Node/TypeScript program run with `npx tsx`. It speaks the Model Context
Protocol over **stdio** — plain newline-delimited JSON messages on standard in/out — which is
exactly the transport Claude Desktop expects when you register a local MCP server in its config
file. You point Claude Desktop at the script and pass the database path as an environment variable
(`CRM_DB_PATH`, defaulting to `data/crm.db`); the server opens that SQLite file with `better-sqlite3`
(synchronous, WAL journaling, foreign keys on) and refuses to start if the DB doesn't exist yet —
you have to run the init script first.

It handles the three MCP lifecycle messages: `initialize` (handshake), `tools/list` (advertise the
ten tools and their input schemas), and `tools/call` (run one). Each tool is a thin wrapper around a
direct SQLite query: `crm_list_contacts` runs a filtered SELECT, `crm_create_contact` an INSERT,
`crm_move_deal` an UPDATE of a deal's stage, and so on. The richer tools do small joins/aggregations
— `crm_get_pipeline` returns every stage with its deals nested inside, `crm_get_followups` buckets
incomplete activities into overdue/today/upcoming/unscheduled, `crm_get_stats` computes counts,
active-deal totals, pipeline value, and conversion rate. Results are wrapped in MCP's content
envelope and returned; errors are caught and returned as MCP errors rather than crashing the server.

The ten tools map almost one-to-one onto the CRM's core nouns and verbs:
- **Contacts:** `crm_list_contacts` (search / temperature filter / limit), `crm_get_contact`
  (with deals + activity history), `crm_create_contact`.
- **Deals:** `crm_list_deals` (optional stage filter), `crm_create_deal`, `crm_move_deal`.
- **Activities:** `crm_log_activity` (call/email/meeting/note/follow-up, optional schedule).
- **Views:** `crm_get_pipeline`, `crm_get_followups`, `crm_get_stats`.

## The non-obvious parts
- **It shares the live database, not a copy.** The MCP server and the Next.js app both open the same
  `crm.db` file. WAL mode is what makes concurrent reads/writes from two processes safe-ish. Edit a
  contact via Claude and refresh the web UI — it's there. This is the whole point and the main
  operational risk (two writers, one file).
- **Synchronous `better-sqlite3`, not the app's Drizzle/async layer.** The MCP server bypasses the
  web app's ORM and talks to SQLite directly and synchronously. Simpler for a stdio tool, but it
  means the *schema knowledge is duplicated* — the server has to know the table shapes independently
  of the app's Drizzle schema. Keep them in sync.
- **stdio transport = local-only.** There's no network surface; the only way to reach these tools is
  a local process Claude Desktop spawns. That's the security model: if you can run the process, you
  can use the CRM. No tokens, no TLS.
- **Fails fast on a missing DB.** Rather than silently creating an empty DB, it errors and tells you
  to run `npm run init`. Prevents the confusing "why is my CRM empty" footgun.
- **The tools encode the product's vocabulary.** Naming them `crm_*` and shaping them around
  contacts/deals/activities/pipeline means Claude gets a clean, domain-true API — the model rarely
  has to guess what to call. Good tool design is mostly good naming + tight input schemas.
- **Read-tools do the aggregation server-side.** `get_stats`/`get_pipeline`/`get_followups` return
  pre-computed, ready-to-narrate structures so the model doesn't have to fetch raw rows and do math
  (which it does unreliably).

## Related
- [[ai-lead-classification--from-auto-crm]] — the inverse direction: that calls Claude *from* the
  app; this exposes the app *to* Claude.
- [[self-customizing-crm--from-auto-crm]] — the other agent-facing surface; together they make the
  CRM both AI-operable and AI-editable.
- [[followup-buckets--from-auto-crm]] — `crm_get_followups` is the MCP-exposed twin of the web
  app's follow-up bucketing endpoint (same overdue/today/upcoming/unscheduled logic).
- [[agent-output-contract--from-last30days-skill]] — same domain: shaping tool/skill surfaces so an
  LLM produces reliable, consistent results.
