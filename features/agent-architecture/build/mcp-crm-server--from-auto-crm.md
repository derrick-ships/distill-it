# MCP CRM Server (build spec) — distilled from auto-crm

## Summary
A standalone Node/TypeScript MCP server (run via `npx tsx`) that exposes a local SQLite-backed CRM
to any MCP client (Claude Desktop/Web) as **10 tools**. Transport is **stdio** (newline-delimited
JSON). It opens the *same* `crm.db` the web app uses via `better-sqlite3` (synchronous, WAL,
foreign keys on), reading the path from `CRM_DB_PATH` (default `data/crm.db`) and exiting if the DB
is absent. Implements MCP `initialize` / `tools/list` / `tools/call`. Each tool is a thin wrapper
over a direct SQL query; read-tools pre-aggregate (pipeline, follow-ups, stats) so the model gets
ready-to-narrate JSON.

## Core logic (inlined)

### Server bootstrap
```ts
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import Database from "better-sqlite3";
import { existsSync } from "node:fs";
import { z } from "zod";

const DB_PATH = process.env.CRM_DB_PATH ?? "data/crm.db";
if (!existsSync(DB_PATH)) {
  console.error(`DB no encontrada en ${DB_PATH}. Ejecuta 'npm run init' primero.`);
  process.exit(1);
}
const db = new Database(DB_PATH);
db.pragma("journal_mode = WAL");      // safe-ish concurrent access with the web app
db.pragma("foreign_keys = ON");

const server = new McpServer({ name: "auto-crm", version: "1.0.0" });

// ... register tools (below) ...

await server.connect(new StdioServerTransport());   // speak MCP over stdin/stdout
```

### Tool catalog (name · input schema · behavior)

```ts
// 1. crm_list_contacts — { search?, temperature?: "cold"|"warm"|"hot", limit?: number }
//    SELECT * FROM contacts WHERE (name/email/company LIKE %search%)
//      AND (temperature = ? if given) ORDER BY score DESC LIMIT ?(default 50)

// 2. crm_get_contact — { id: string (required) }
//    contact + its deals (JOIN pipelineStages for stage name) + its activities (ORDER BY createdAt DESC)

// 3. crm_create_contact — { name* , email?, phone?, company?, source?="manual",
//                           temperature?="cold", notes? }
//    INSERT INTO contacts (...) RETURNING

// 4. crm_list_deals — { stageId? }
//    SELECT deals JOIN contacts (name,temperature) JOIN pipelineStages (name,order)
//      WHERE stageId = ? if given, ORDER BY stage.order

// 5. crm_create_deal — { title*, contactId*, value?=0, stageId?, probability?=0, notes? }
//    if no stageId -> first stage by order. INSERT INTO deals RETURNING

// 6. crm_move_deal — { dealId* , stageId* }
//    verify deal exists (else MCP error) -> UPDATE deals SET stageId=?, updatedAt=now WHERE id=?

// 7. crm_log_activity — { type*("call"|"email"|"meeting"|"note"|"followup"),
//                         description*, contactId*, dealId?, scheduledAt? }
//    INSERT INTO activities (...) RETURNING

// 8. crm_get_pipeline — {} (no args)
//    all stages ORDER BY order, each with nested deals[] (deal + contact name/temperature)

// 9. crm_get_followups — {} (no args)
//    incomplete activities (completedAt IS NULL) JOIN contacts, bucketed:
//      overdue / today / upcoming / unscheduled  (see followup-buckets build doc for exact math)

// 10. crm_get_stats — {} (no args)
//     { contactCount, byTemperature:{cold,warm,hot}, activeDeals, pipelineValue (sum of open deal values),
//       wonDeals, conversionRate (won / total deals), ... }
```

### Tool registration shape (repeat per tool)
```ts
server.tool(
  "crm_create_contact",
  "Crear un nuevo contacto/lead en el CRM.",
  {
    name: z.string(),
    email: z.string().optional(),
    phone: z.string().optional(),
    company: z.string().optional(),
    source: z.string().default("manual"),
    temperature: z.enum(["cold","warm","hot"]).default("cold"),
    notes: z.string().optional(),
  },
  async (args) => {
    try {
      const id = crypto.randomUUID();
      db.prepare(`INSERT INTO contacts (id,name,email,phone,company,source,temperature,score,notes,createdAt,updatedAt)
                  VALUES (?,?,?,?,?,?,?,0,?,?,?)`)
        .run(id, args.name, args.email ?? null, args.phone ?? null, args.company ?? null,
             args.source, args.temperature, args.notes ?? null, Date.now(), Date.now());
      const row = db.prepare("SELECT * FROM contacts WHERE id = ?").get(id);
      return { content: [{ type: "text", text: JSON.stringify(row, null, 2) }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${(e as Error).message}` }], isError: true };
    }
  },
);
```

## Data contracts
- **Transport:** stdio, MCP JSON-RPC. Methods handled: `initialize`, `tools/list`, `tools/call`.
- **DB:** shared SQLite file (`contacts`, `pipelineStages`, `deals`, `activities`, `crmSettings`).
  Tables (key fields): contacts(id,name,email,phone,company,source,temperature,score,notes,ts);
  deals(id,title,value,stageId→pipelineStages,contactId→contacts,expectedClose,probability,notes,ts);
  activities(id,type,description,contactId→contacts,dealId?→deals,scheduledAt?,completedAt?,createdAt);
  pipelineStages(id,name,order,color,isWon,isLost).
- **Tool output:** MCP `{ content: [{ type:"text", text }], isError? }`. Text is JSON-stringified rows
  or pre-aggregated structures.
- **Config (Claude Desktop `claude_desktop_config.json`):**
  ```json
  { "mcpServers": { "auto-crm": {
      "command": "npx", "args": ["tsx", "/abs/path/mcp/crm-server.ts"],
      "env": { "CRM_DB_PATH": "/abs/path/data/crm.db" } } } }
  ```

## Dependencies & assumptions
- `@modelcontextprotocol/sdk`, `better-sqlite3`, `zod`, `tsx`. Node 18+.
- The DB must already exist & be migrated (separate init step). Server exits if not.
- Assumes single-machine, local trust model — **no auth on the tools** (stdio = whoever spawns it).
- Schema is duplicated from the web app's ORM; the server hand-writes SQL.

## To port this, you need:
- [ ] An MCP SDK server + stdio transport in your runtime (Node shown; Python `mcp` works the same).
- [ ] A SQLite (or other) DB with the contacts/deals/activities/stages tables.
- [ ] A tool per core verb, each: zod/JSON input schema → SQL → MCP content envelope, wrapped in
      try/catch returning `isError`.
- [ ] Pre-aggregation for the "view" tools (pipeline/follow-ups/stats) so the LLM narrates, not computes.
- [ ] Client config pointing at the script with the DB path in env; a guard that exits if DB missing.

## Gotchas
- **Two writers, one file.** App + MCP server both write `crm.db`. WAL makes it workable but not
  bulletproof — long transactions or non-WAL access can lock/corrupt. Keep writes short; consider a
  single-writer arrangement if you scale up.
- **Schema duplication drift.** Hand-written SQL in the server can fall out of sync with the app's
  migrations. When you change the schema, update both. (Or generate the server's queries from the
  same schema source.)
- **No auth.** stdio local-only is the only thing protecting the data. Never expose this over a
  network transport (SSE/HTTP) without adding auth.
- **`tools/list` must mirror reality.** If a tool's advertised input schema drifts from what the
  handler reads, the model sends args that silently no-op. Generate schemas from the same zod object
  you validate with (as shown) to avoid this.
- **Return narration-ready JSON.** Don't dump raw rows for stats/pipeline; the model does arithmetic
  poorly. Compute conversion rate, pipeline value, and buckets server-side.
- **`npx tsx` cold-start latency** on first tool call — fine for desktop, but pre-compile for speed
  if it matters.

## Origin (reference only)
auto-crm — `mcp/crm-server.ts` (10 `crm_*` tools, stdio, better-sqlite3, `CRM_DB_PATH`). Schema in
`src/db/schema.ts`; DB created by `scripts/init.ts` (`npm run init`).
