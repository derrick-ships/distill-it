# Self-Customizing CRM via Claude Code Commands — from [auto-crm](https://github.com/Hainrixz/auto-crm)

> Domain: [[_domain]] · Source: https://github.com/Hainrixz/auto-crm (`.claude/commands/`, `CLAUDE.md`, `AGENTS.md`) · NotebookLM: <add link>

## What it does
The CRM ships with a set of Claude Code slash-commands baked into the repo (`.claude/commands/`),
so the way you "configure" the product is by *talking to Claude inside the codebase* rather than
clicking settings. There are commands to set the CRM up (`setup`), connect the MCP server to Claude
Desktop (`connect`), customize the CRM's fields/stages/branding to your business (`customize`), bulk-
import contacts (`import-contacts`), add a lead (`add-lead`), analyze the pipeline (`analyze-pipeline`),
produce a morning standup (`daily-briefing`), and generate an activity digest (`digest`). The pitch
is "a CRM that rewrites itself to fit you" — instead of bending your process to the software's fixed
fields, you tell Claude what you need and it edits the actual code/schema to match.

## Why it exists
Every business's sales process is a little different — different stages, different fields, different
language — and traditional CRMs solve this with sprawling, brittle settings screens (or force you to
adapt). This product makes a bolder bet: since the user is already running it locally and through
Claude, **the agent is the configuration layer.** The job-to-be-done is **fit the tool to the
business without a settings UI** — "add a 'contract signed' stage," "rename temperature to priority,"
"add an industry field" become prompts that Claude executes by editing the Drizzle schema and the
components. The commands are also a *distribution and onboarding* mechanism: `setup` and `connect`
turn a fresh clone into a working, Claude-wired CRM by having the agent run the steps, so a non-
technical user can stand it up by talking.

## How it actually works
Each command is a markdown file in `.claude/commands/` — a runbook written *for an AI agent* to
execute. When you type `/setup` or `/customize` in Claude Code inside the repo, Claude reads that
file and carries out the steps: running init scripts, editing schema files, regenerating components,
wiring the MCP config, or querying the database to produce a report. The repo also carries top-level
`CLAUDE.md` / `AGENTS.md` files that give the agent the project's context, conventions, and guardrails
so its edits stay coherent with the codebase.

The commands split into two kinds:
- **Structural / setup commands** that *change the product*: `setup` (initialize DB + project),
  `connect` (register the MCP server in Claude Desktop's config), `customize` (modify schema, stages,
  fields, branding to fit the user's business), `import-contacts` (guided bulk import).
- **Operational commands** that *use the product* day to day: `add-lead` (create a contact
  conversationally), `analyze-pipeline` (read the stats and summarize health/risks), `daily-briefing`
  (a morning standup built from today's/overdue follow-ups and pipeline state), `digest` (a periodic
  activity summary, which pairs with the optional email-digest feature).

The throughline is that natural language is the interface for *both* reshaping the CRM and running
it. The MCP server (the operational side) and these commands (the customization side) are the two
halves of the same "AI-native CRM" thesis: Claude can both *operate* the CRM (via MCP tools) and
*rewrite* it (via these commands editing the code).

## The non-obvious parts
- **The configuration layer is the agent, not a UI.** This is the whole conceptual move: there's no
  settings page for stages/fields because Claude edits the schema directly. It trades a polished
  settings UX for near-unlimited flexibility — you can ask for changes no settings screen would ever
  expose. The cost is that "customizing" means a code edit, with all the risk that implies.
- **Commands are runbooks for an LLM, not scripts.** They're prose with imperative steps and
  branches, executed by a reasoning agent — so they can adapt to the user's specific situation
  ("you're on Windows," "you already have contacts") in a way a fixed shell script can't.
- **`CLAUDE.md`/`AGENTS.md` are the guardrails.** Because the agent is editing real code, the repo
  supplies it with conventions and context up front so customizations don't drift or break the build.
  The quality of these context files is what makes agent-driven customization safe enough to ship.
- **Setup and use share one mechanism.** Installing, connecting, customizing, and daily operation are
  all "Claude reads a doc and acts" — the same pattern covers the entire lifecycle, which is the
  defining trait of this domain.
- **It doubles as onboarding for non-coders.** A user who can't write Drizzle can still get a tailored
  CRM by describing what they want; the agent does the engineering. That's the real product wedge.
- **Operational commands lean on the same data the dashboard/follow-ups use** — `analyze-pipeline`
  and `daily-briefing` are narration layers over the stats and follow-up buckets, just delivered
  conversationally.

## Related
- [[mcp-crm-server--from-auto-crm]] — the *operate* half of the AI-native thesis; these commands are
  the *reshape* half. Together they make the CRM both AI-operable and AI-editable.
- [[agent-driven-install--from-agent-reach]] — same domain, same idea: a markdown runbook executed by
  an agent as the installer/maintainer; auto-crm's `setup`/`connect` are its analog.
- [[followup-buckets--from-auto-crm]] — `daily-briefing` narrates these buckets as a standup.
- [[crm-dashboard-kpis--from-auto-crm]] — `analyze-pipeline` is the conversational twin of the
  dashboard's stats.
