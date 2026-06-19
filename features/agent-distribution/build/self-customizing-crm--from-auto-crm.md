# Self-Customizing CRM via Claude Code Commands (build spec) — distilled from auto-crm

## Summary
Ship a product whose configuration/customization layer is an AI coding agent instead of a settings
UI. The repo carries `.claude/commands/*.md` — runbooks an agent executes in-repo — plus
`CLAUDE.md`/`AGENTS.md` context/guardrail files. Commands split into **structural** (change the
product: `setup`, `connect`, `customize`, `import-contacts`) and **operational** (use the product:
`add-lead`, `analyze-pipeline`, `daily-briefing`, `digest`). Customizing the schema/stages/fields
means the agent edits real code (Drizzle schema + components), not toggling settings.

## Core logic (inlined)

### Repo layout that makes it work
```
.claude/commands/
  setup.md            # initialize DB + project (npm install, npm run init)
  connect.md          # register MCP server in Claude Desktop claude_desktop_config.json
  customize.md        # edit schema/stages/fields/branding to fit the user's business
  import-contacts.md  # guided bulk import (parse CSV -> POST /api/import)
  add-lead.md         # conversational contact creation (-> crm_create_contact / POST /api/contacts)
  analyze-pipeline.md # read stats, summarize pipeline health & risks
  daily-briefing.md   # morning standup from follow-up buckets + pipeline state
  digest.md           # periodic activity summary (pairs with email digest)
CLAUDE.md / AGENTS.md # project context, conventions, guardrails for the agent
```

### Command file shape (runbook for an agent, not a shell script)
```markdown
# /customize

Goal: adapt the CRM's data model and UI to the user's business.

Steps:
1. Ask the user what they want to change (new stage? new field? rename temperature? branding?).
2. Locate the relevant source:
   - stages/fields  -> src/db/schema.ts (Drizzle table defs)
   - default stages -> scripts/init.ts (seed)
   - constants/colors/labels -> src/lib/constants.ts
   - UI             -> src/components/** (forms, cards, dashboard)
3. Make the minimal edit. If you change schema, generate/apply a migration and update any
   code that reads the changed columns (API routes, MCP server queries, exports).
4. Keep the MCP server (mcp/crm-server.ts hand-written SQL) in sync with schema changes.
5. Run the build/typecheck. Summarize what changed and how to use it.

Guardrails (see CLAUDE.md): never delete user data; back up data/crm.db before destructive
migrations; don't break the existing API/MCP contracts unless asked.
```

### Two-mechanism pairing (the thesis)
- **Operate** the CRM conversationally → MCP server (`crm_*` tools). See
  `[[mcp-crm-server--from-auto-crm]]`.
- **Reshape** the CRM conversationally → these `.claude/commands` editing code/schema.
- Both are "agent reads a live doc / tool spec and acts."

## Data contracts
- **Command file:** markdown with a Goal, ordered imperative Steps, environment branches, explicit
  user checkpoints (ask before destructive/ambiguous changes), and a definition of done.
- **Context files:** `CLAUDE.md`/`AGENTS.md` — project conventions, file map, guardrails (what NOT to
  touch, data-safety rules).
- **Operational commands** read the same aggregations as the app: stats payload (see
  `[[crm-dashboard-kpis--from-auto-crm]]`) and follow-up buckets (see
  `[[followup-buckets--from-auto-crm]]`); they narrate, not recompute.

## Dependencies & assumptions
- Target runtime is Claude Code (or any agent that reads `.claude/commands/*.md`) operating *inside
  the repo* with file-edit + shell capability.
- A coherent, well-documented codebase (Drizzle schema as the single source of truth for fields) so
  edits stay localized.
- The user trusts an agent to edit their CRM's code locally (local-first, single user).

## To port this, you need:
- [ ] A repo the agent runs inside, with a single clear source of truth for the data model (schema).
- [ ] `.claude/commands/*.md` runbooks: split structural (change product) vs operational (use product).
- [ ] `CLAUDE.md`/`AGENTS.md` with file map + guardrails (data safety, don't-break-contracts).
- [ ] Each structural command to update *every* place a changed field is read: API routes, the MCP
      server's hand-written SQL, exports, and UI — or the change half-lands.
- [ ] User checkpoints in any command that edits schema or touches data (ask before destructive ops).

## Gotchas
- **"Customize" = code edit = real risk.** Unlike a settings toggle, an agent editing the schema can
  break the build or, worse, the data. Mandate: back up `data/crm.db` before migrations, run
  typecheck/build after, and never drop columns without explicit confirmation.
- **Schema changes must propagate to the hand-written MCP SQL.** The MCP server duplicates schema
  knowledge (raw `better-sqlite3` queries). A `/customize` that adds a field but forgets the MCP
  server leaves Claude's tools blind to it. Make "sync MCP queries" a required step.
- **Runbooks are prose, so quality of CLAUDE.md is the safety net.** Thin context → drifting,
  inconsistent edits. Invest in the file map and conventions; that's what makes this shippable.
- **Don't auto-do destructive things.** Bake explicit "ask the user" checkpoints into commands that
  delete/rename/migrate — the agent shouldn't decide alone.
- **Operational commands should narrate shared aggregations, not re-derive them** — reuse the stats /
  follow-up logic so the conversational answer matches the UI.

## Origin (reference only)
auto-crm — `.claude/commands/{setup,connect,customize,import-contacts,add-lead,analyze-pipeline,
daily-briefing,digest}.md`; `CLAUDE.md`, `AGENTS.md`, `SETUP_GUIDE.md`. Schema source of truth:
`src/db/schema.ts`; seed: `scripts/init.ts`.
