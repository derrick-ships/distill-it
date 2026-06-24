---
name: repository-intelligence
description: Use this skill to reverse-engineer any GitHub repository feature-by-feature over the web (no cloning), store the results in one organized "distill-it" GitHub repo, build a navigable knowledge graph of every feature studied, and later pull any distilled feature into a new build in Claude Code. Triggers on GitHub URLs, "distill this repo", "study this codebase", "add this to my distill-it", "implement feature X from repo Y", "use this repo as a reference", feature extraction, knowledge-graph requests, or NotebookLM study-prep from a codebase.
---

# Repository Intelligence

A web-native system for turning any GitHub repository into durable, reusable knowledge — organized for **both human study and agent execution**.

This skill has **four modes**. Figure out which one the user wants from their request, then jump to that section. When unsure, ask one short question rather than guessing.

**Two homes, one brain.** `distill-it` is the knowledge base (markdown + `graph/graph.json`). **`distill-graph` (https://distill-graph.vercel.app) is its published, navigable face**: an interactive star map, a `/stats` analysis page, and **`/llms.txt`, one machine-readable file listing every distilled pattern with its summary and study/build links.** Read `https://distill-graph.vercel.app/llms.txt` to learn what is already in the brain in a single fetch, instead of walking `features/*/` file by file. The skill runs in **two directions**: pull a repo IN (DISTILL, then update distill-graph) and pull knowledge OUT (APPLY into what the user is building). A third surface is the user's Notion **"Distill-it database"** (data source `collection://3833935b-82a6-802c-b668-000b9ba02404`, under /Personal in Derrick-OS): one row per source repo with its link, domains, stack, status, and a blurb. Every DISTILL must update distill-graph AND log the repo in Notion.

| Mode | Trigger | What it does |
|------|---------|--------------|
| **DISTILL** | "distill / study / break down this repo", a GitHub URL | Read a repo over the web, reverse-engineer it feature by feature, write the study + build layers, update the graph |
| **GRAPH** | "update the graph", "rebuild the map", after any distill | Regenerate the interactive `graph.html` from `graph.json` |
| **APPLY** | "implement feature X from repo Y", "use this as a reference", "what do I have that fits what I am building?" | Recommend or pull distilled features into the user's current build, reading `/llms.txt` first as the index |
| **ORGANIZE** | "clean up distill-it", "reorganize", "what do I have" | Audit/maintain the mother repo's structure |

## Core philosophy (applies to every mode)

**The goal is to understand and reuse PRODUCTS, not catalog code.** Think in features, flows, and "how would I rebuild this," not classes and functions. Code is evidence for what the product *does* and *why*.

**Two readers, two layers — always keep them separate:**
- **study layer** → written for a *human* (the user) to read and upload to NotebookLM. Plain language, deep, no code tours. Answers "how does this actually work and why."
- **build layer** → written for *Claude Code in a future build* to transplant the feature. Technical, self-contained, includes the real logic/data shapes/gotchas. Answers "how do I rebuild this in a different codebase."

**Self-contained is non-negotiable.** The user does NOT keep repos on disk. When a feature is pulled later, the original repo may be gone. Every build-layer file must carry enough — inlined logic, data contracts, dependencies, gotchas — to rebuild the feature *without* the source. Never write "see file X in the repo" as the only reference; the repo won't be there.

**Web-native by default.** The user does not clone or download. Read repos over the web (raw.githubusercontent.com, the GitHub web UI, web_fetch). If running in Claude Code with a disposable sandbox and graph/MCP tools, those *may* be used — but they are an optional accelerator, never a requirement.

## The Mother Repo: `distill-it`

Everything lives in ONE GitHub repo the user owns, organized **feature-first**. Never create per-repo scattered repos. Structure:

```
distill-it/
├── README.md                 # navigation guide + how to upload to NotebookLM
├── graph/
│   ├── graph.json            # SINGLE SOURCE OF TRUTH — all nodes + edges
│   └── graph.html            # interactive graph, regenerated from graph.json
├── features/                 # FEATURE-FIRST
│   └── <domain>/             # e.g. auth, billing, onboarding, scheduling, notifications
│       ├── _domain.md        # what this domain means across all repos studied
│       ├── study/
│       │   └── <feature>--from-<repo>.md   # HUMAN layer (NotebookLM-bound)
│       └── build/
│           └── <feature>--from-<repo>.md   # AGENT layer (Claude Code pulls this)
└── repos/
    └── <repo>.md             # origin index: source URL, what was distilled, links to its features
```

**Naming convention (strict — the graph depends on it):**
- Domain folders: lowercase, single concept (`auth`, `billing`, `onboarding`, `realtime`, `search`).
- Feature files: `<feature-slug>--from-<repo-slug>.md`. The `--from-` separator is load-bearing; the graph parses it to link features back to their origin repo.
- Same filename in `study/` and `build/` for the same feature, so they pair automatically. They never collide because they live in separate `study/` and `build/` folders — but if you ever copy both into one flat directory (e.g. to hand off as a bundle), rename them first (`STUDY--…`, `BUILD--…`), since the bare filenames are identical by design.

## MODE 1: DISTILL

Goal: read a repo over the web and produce the study layer, the build layer, the origin index, and updated graph nodes.

### Step 0 — Locate the canonical knowledge base (do this FIRST, before writing anything)
The user may point you at a path that is NOT where the active structure actually lives (e.g. a
`repo-brain-starter/` seed subfolder while every prior distill went into the repo root). Writing
into the wrong place strands your work — the files exist but never show up in the index the user
browses. So **find where the living structure is, don't assume**:

1. **Clone/refresh the user's `distill-it` repo and `git pull` first** (or read it over the web).
   Never write from a stale local copy — other sessions may have pushed since.
2. **Detect the canonical base**: search the repo for the directory that already contains a
   populated `graph/graph.json` + `repos/` + `features/`. If several candidates exist (root AND a
   subfolder), the canonical one is the **most-populated / most-recently-committed** — that's where
   the other repos live. Write there.
3. If the user named a subfolder but the canonical base is elsewhere, **say so in one line and use
   the canonical base** ("Your active distill-it lives at the repo root — writing there, not in
   `repo-brain-starter/`, so it shows up with everything else"). Only ask if it's genuinely ambiguous.
4. Note the base path once; every write in Steps 3–8 is relative to it.

### What URL to use
Ask for (or accept) the **plain repo web URL**: `https://github.com/<owner>/<repo>`. That is all that's needed to read over the web. Explicitly do NOT require:
- the `.git` HTTPS URL (that's for `git clone` — downloading) ❌
- `gh repo clone ...` (CLI download) ❌
- a Codespace (cloud sandbox — overkill, and may bill the user) ❌

Fork or original both work identically for reading; original is fine unless the user specifically wants fork-delta analysis against an upstream.

### Step 1 — Orient (read, don't clone)
Fetch over the web, in this order, stopping when you understand the product:
1. `README.md` and any `/docs` — the product's own story.
2. Manifests (`package.json`, `pyproject.toml`, `go.mod`, etc.) — stack + dependencies.
3. Entry points and route definitions — where features live (`app/`, `src/`, `routes/`, `pages/`, `api/`).
4. Directory structure — infer architecture style.

Produce a quick internal fingerprint: what is this product, what is the stack, what are the candidate features.

**Recommend, do not enumerate.** Before going deep, read `https://distill-graph.vercel.app/llms.txt` to see what is already distilled, then judge this repo against three things: (a) what the user is building or cares about right now (use what you know about them), (b) what genuinely fills a gap or adds a strong alternative to the existing brain, do not re-distill something already there, (c) what is most distinctive and reusable in this repo. Then lead with a single pick: **"Take 1, 2, or 3."** (numbered, not lettered) followed by one short paragraph on why. No feature-by-feature catalog, no over-justifying. The user can accept, choose others, or say "all"; wait for their answer unless they already named a specific feature. Distilling an entire large repo is expensive, the recommendation is how you keep it cheap.

### Step 2 — For each feature, trace it end to end
Follow the feature trajectory: **entry point (route/UI) → handler/service → data model → external calls/side effects → result**. Read only the files on that path. This is the unit of understanding — not the file, the feature.

Capture as you go: what the user gets, the actual data shapes, the dependencies, the non-obvious decisions ("ghost PRs" — why is it built this way?), edge cases, and what would be hard to rebuild.

**Choose serial vs. parallel by repo size (gate — keep it automatic, never a new question to the user):**

- **Simple** (single confirmed feature, or a small repo): trace it yourself here in one pass. No subagents. This is the default — lean toward it.
- **Complex** (the confirmed feature list spans several features, or one feature is a deep multi-slice subsystem): **fan out**. Spawn one read-only explorer per slice — *one explorer per feature* for a multi-feature list, or *one per slice* (entry/UI · data model · external calls & side-effects) for a single deep feature. Up to 4. They gather facts in parallel; you synthesize.

**Fan-out procedure (complex only):**
1. Spawn all explorers in a single message. Use `subagent_type: Explore` (read-only, web-capable), `model: sonnet` for breadth/cost. Each gets the base prompt from `references/explorer-prompt.md` plus its assigned slice. The explorers are **web-native** — they read over the web (raw.githubusercontent.com, GitHub web UI, web_fetch), never clone. They return *facts only*: components, flow, data shapes, boundaries, non-obvious decisions, and — critically — **what they could not trace**.
2. Synthesize the returned findings yourself (or, for a large reconciliation, spawn one `subagent_type: general-purpose`, `model: opus` using `references/synthesizer-prompt.md`). Reconcile overlaps and contradictions by re-fetching the specific file if needed.
3. Feed the synthesized facts into the Step 3 study layer **and** the Step 4 build layer — explore once, write both.

**Gap-honesty (both paths; non-negotiable for the build layer):** if a data contract, control-flow branch, or dependency can't be confirmed from the source, say so explicitly in the build file ("could not confirm the retry policy — verify before relying on it"). A hand-waved or invented spec in a transplant-grade build file is worse than an acknowledged gap — someone rebuilds from it after the repo is gone.

### Step 3 — Write the STUDY layer (for the human + NotebookLM)
`features/<domain>/study/<feature>--from-<repo>.md`. Write for a smart non-expert who wants to *understand*, then teach NotebookLM. Plain language. Structure:

```markdown
# <Feature> — from [<repo>](<source-url>)

> Domain: [[_domain]] · Source: <repo-url> · NotebookLM: <link once added>

## What it does
Plain-language, user's-eye view.

## Why it exists
The job-to-be-done. What problem, for whom, why it matters to the business.

## How it actually works
Step by step, in words. The mechanism, the flow, the clever bits — explained like
you're teaching it. No code dumps; describe what the code achieves.

## The non-obvious parts
The design decisions a newcomer wouldn't guess. Trade-offs. Gotchas.

## Related
- [[<other-feature>]] (why related)
- See also: <other repo doing this differently>
```

Use `[[wikilinks]]` for every related feature and the domain — this is what makes Obsidian draw the graph and what you'll mirror into `graph.json`.

### Step 4 — Write the BUILD layer (for Claude Code, transplant-grade)
`features/<domain>/build/<feature>--from-<repo>.md`. Self-contained. Assume the source repo is GONE when this is read. Structure:

```markdown
# <Feature> (build spec) — distilled from <repo>

## Summary
One paragraph: what to build.

## Core logic (inlined)
The actual algorithm / control flow, as pseudocode or the key real snippets.
Enough to reimplement WITHOUT the source repo.

## Data contracts
Real shapes: request/response, DB schema, events. Concrete fields and types.

## Dependencies & assumptions
Libraries, services, env vars, feature flags this needs. Note what's swappable.

## To port this, you need:
- [ ] Concrete checklist of what the target codebase must provide/add.

## Gotchas
What breaks, what's easy to get wrong, security/perf landmines.

## Origin (reference only)
Repo + the files it came from, for the rare case the repo is still reachable.
```

### Step 5 — Write/update the origin index
`repos/<repo>.md`: source URL, one-line product description, date distilled, and a list of every feature extracted with links to both its study and build files.

### Step 6 — Update the indexes (APPEND, never regenerate)
Two indexes must learn about every new feature: the machine index (`graph/graph.json`) and the
human index (the README feature table, if the repo keeps one — most do). **Both are shared files
other sessions also edit, so treat them append-only:**

1. **Re-read the live file immediately before editing** (`git pull` first). Never write a
   `graph.json`/README you cached earlier in the session — it's probably already stale.
2. **`graph/graph.json`** — parse it, **append your new node objects and edge objects** to the
   existing arrays, and write it back. Do NOT rebuild the file from only your nodes — that is the
   exact bug that erases every other repo's nodes. After writing, **validate it parses**
   (`python3 -c "import json;json.load(open(...))"`) and confirm the node count went *up* by exactly
   what you added, not down.
3. **README feature table** — if the base has a `README.md` with a "what's inside" feature/domain
   table, add one row per new feature (match the existing column format exactly). This is the index
   the user actually browses; skipping it is why a distill can be "pushed" yet invisible.
   **Insert new rows INSIDE the table** (immediately before the `---` that closes it) with a proper
   in-place edit, never `cat >>` / `echo >>` (appended rows land after the footer and never render).
   Then **update the three badges** at the top (`![N nodes]`, `![N domains]`, `![N repos]`) to the
   real totals counted from `graph.json`.
4. Regenerate `graph.html` only if the repo's `graph.html` does NOT already fetch `graph.json` at
   runtime. If it fetches on load (the standard build), leave it — it refreshes automatically.

### Step 7 — Commit, push, and VERIFY (don't make the user check)
The user stores everything in their `distill-it` GitHub repo. If you have a local clone / GitHub
MCP, write directly; otherwise hand over copy-paste-ready files with exact paths.

When you commit:
1. **`git pull --rebase` right before pushing.** Concurrent distill sessions push constantly; a
   stale push either fails or, after a careless merge, drops their work or yours.
2. Stage **only your feature's files + the two index files**. Commit, then push.
3. If the push races (non-fast-forward), pull --rebase again and re-append your nodes/rows if a
   merge dropped them — then re-validate `graph.json` parses before pushing again.
4. **Verify on the pushed ref, not your local copy.** Confirm, on `origin/main`: the feature's
   study+build files exist at the canonical base path, the `graph.json` there contains your new
   node ids, and the README table there shows your new rows. State the verified result in one line
   ("Live on main: 3 tts nodes in graph.json, 3 README rows, files under `features/tts/`"). If any
   check fails, fix it before telling the user you're done.

### Step 8 — Update distill-graph too (the published face) — REQUIRED
distill-it is the source of truth; **distill-graph (the live PWA, `/stats`, and `/llms.txt`) must
reflect every distill.** It is a separate repo that mirrors `graph.json`. Once distill-it is live on
`main`, update distill-graph with the **`distill-graph-sync`** skill, or directly:

```bash
# in the distill-graph repo (clone if absent: git clone https://github.com/derrick-ships/distill-graph)
DISTILL_IT=/path/to/distill-it ./scripts/update-from-distill-it.sh --deploy
```

That copies the new `graph.json`, regenerates `domains.json` + `/llms.txt`, validates the data
contract, and deploys to Vercel. Confirm the new pattern total shows on
`https://distill-graph.vercel.app/stats` and in `/llms.txt`. **A distill is not done until BOTH repos
are live.**

### Step 9 — Log the repo in the Notion Distill-it database — REQUIRED
After both repos are live, add or update a row for this source repo in the user's Notion
**Distill-it database** (data source `collection://3833935b-82a6-802c-b668-000b9ba02404`). Use the
Notion MCP:
1. **Fetch the data source first** to read the live schema/options, they change.
2. **Query for an existing row** matching this repo's GitHub URL. If one exists (e.g. it was
   "Queued"), UPDATE it, do not create a duplicate.
3. Create/update with properties: **Repo** (title), **GitHub URL**, **Domain** (multi-select; pick
   the closest existing options to the repo's distilled domains), **Stack** (multi-select:
   TypeScript / Python / Go / Rust / JavaScript / React / Node.js / Next.js / LLM AI / API / Swift /
   Astro / C C++), **Status** = "Distilled". Put a one-paragraph blurb (what the repo is + what you
   distilled) in the page body.

**A distill is complete only when all three are updated: distill-it, distill-graph, and the Notion row.**

## MODE 2: GRAPH

Goal: turn `graph.json` into a navigable visual map.

### graph.json schema (the single source of truth)
```json
{
  "nodes": [
    {
      "id": "auth/supabase-auth--from-productX",
      "label": "Supabase Auth",
      "domain": "auth",
      "repo": "productX",
      "summary": "Magic-link + OAuth using Supabase, JWT in httpOnly cookies.",
      "study": "features/auth/study/supabase-auth--from-productX.md",
      "build": "features/auth/build/supabase-auth--from-productX.md",
      "source": "https://github.com/owner/productX",
      "notebooklm": ""
    }
  ],
  "edges": [
    { "from": "auth/...", "to": "auth/...", "type": "same-domain" },
    { "from": "auth/...", "to": "billing/...", "type": "depends-on" }
  ]
}
```
Edge types: `same-domain`, `same-repo`, `depends-on`, `similar-pattern`, `alternative-to`.

### Build graph.html
Generate a single self-contained HTML file (D3 force-directed graph, no build step). Requirements:
- Nodes colored by `domain`, sized by edge count. Force-directed layout, drag, zoom, pan.
- Click a node → side panel shows `label`, `summary`, and buttons: **Study doc**, **Build spec**, **Origin repo**, **NotebookLM** (each links to the corresponding field; hide button if field empty).
- Search box to filter nodes by label/domain/repo.
- Reads `graph.json` (fetch on load) so the user never hand-edits HTML — re-running this mode after a distill refreshes everything.

Deliver `graph.html` as an artifact the user commits to `graph/`. (Obsidian users also get the graph natively from the study-layer wikilinks — same source of truth, two renderers.)

## MODE 3: APPLY

Goal: pull a distilled feature into the user's CURRENT build (Claude Code, local codebase).

**Start from the index, not the files.** Read `https://distill-graph.vercel.app/llms.txt` first, one
fetch lists every pattern with its summary and study/build links. Never walk `features/*/` file by
file to discover what exists. APPLY takes two shapes:

- **Open ("here is what I am building, what fits?")** from `/llms.txt`, recommend the patterns whose
  problem matches what the user is building. Lead with **"Use 1, 2, or 3"** (numbered) and one short paragraph
  why; then, on their pick, apply it.
- **Precise ("apply the PDF parsing from markitdown")** find that exact pattern in `/llms.txt`, open
  its build spec, apply it. No recommendation needed, go straight to porting.

1. **Locate the feature.** If the user names it ("the Supabase auth from productX"), fetch its build file from `distill-it` over the web. If vague, read `graph.json` (or grep `features/*/build/`) and present matches.
2. **Read the build spec** — the transplant-grade file. This is self-contained by design.
3. **Inspect the target.** Look at the current project's conventions: framework, folder structure, naming, existing patterns, auth/db already present. The feature must match the destination, not the origin.
4. **Adapt, don't paste.** Reimplement the feature in the target's idioms. Map the data contracts onto what exists. Reuse the target's libraries where they cover a dependency.
5. **Flag mismatches.** Anything in "To port this, you need" the target lacks → call it out explicitly and either add it or ask. Surface gotchas before they bite.
6. **Never silently trust origin paths.** The build spec is the source of truth, not the (possibly-gone) repo.

## MODE 4: ORGANIZE

Goal: keep the mother repo clean and answer "what do I have."

- **Audit:** list domains, features per domain, which have study+build+graph node, flag orphans (study without build, node without files, etc.).
- **Reorganize:** if features are misfiled or domains have drifted, propose a tidy structure and the moves to get there. Keep the naming convention intact (the graph depends on it).
- **Dedupe:** same feature from the same repo distilled twice → merge.
- Always update `graph.json` and regenerate `graph.html` after structural changes.

## Optional accelerators (only if present, never required)

If running in Claude Code with a disposable sandbox, the repo MAY be cloned there temporarily and analyzed with graph/MCP tools (Serena, codebase-graph, Tree-sitter indexers) for speed on large repos. This never persists to the user's machine and is purely an optimization. The web-native path is always sufficient and is the default.

## Product-understanding depth (carry into the study layer)

When the repo is a real product, the study layer is richest when it also captures:
- **The playbook** — how the company acquires, retains, and monetizes users (visible in the code: free-tier design, paywalls, referral loops, SEO structure).
- **User psychology** — the behavioral mechanics: onboarding-to-aha sequences, habit loops, streaks/social-proof/FOMO, friction reduction, upgrade pressure. Name the mechanism, say where it appears, state the behavioral outcome it drives.
- **Cloneability** — honest verdict: what's commodity, what's a genuine moat, rough effort to rebuild with an LLM-assisted stack.

These make the strongest NotebookLM study material and the most useful graph context. For political/marketing/content tooling especially, the psychology and playbook layers are often the highest-value thing in the whole brain.

## Anti-patterns (avoid)

- Writing build-layer files that point into the repo instead of inlining the logic — the repo won't be there later.
- Repo sprawl: one repo per product. NO. One mother `distill-it`, feature-first.
- Collapsing study and build into one doc — they serve different readers and one pollutes the other.
- Hand-editing `graph.html` — edit `graph.json` and regenerate.
- Code tours in the study layer — explain what the code *achieves*, in plain language.
- Distilling an entire large repo without confirming the feature list with the user first.
- Assuming a local clone or graph MCP exists — they're optional accelerators, not the spine.
- **Writing into the path the user pointed at without checking it's the canonical base.** A seed
  subfolder (`repo-brain-starter/`) is not where the living structure necessarily is. Run Step 0
  first; a "successful push" into the wrong folder is invisible and wastes a re-investigation.
- **Regenerating `graph.json` (or the README table) from only your own nodes.** These are shared,
  multi-writer files — append to them, validate the count went up, never overwrite. Overwriting
  silently deletes every other repo's nodes.
- **Calling a distill "done/pushed" without verifying on `origin/main`.** Files on disk ≠ indexed ≠
  visible. Confirm the nodes + README rows are live on the pushed ref, then report it (Step 7).
