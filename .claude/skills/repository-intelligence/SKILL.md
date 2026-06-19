---
name: repository-intelligence
description: Use this skill to reverse-engineer any GitHub repository feature-by-feature over the web (no cloning), store the results in one organized "repo-brain" GitHub repo, build a navigable knowledge graph of every feature studied, and later pull any distilled feature into a new build in Claude Code. Triggers on GitHub URLs, "distill this repo", "study this codebase", "add this to my repo-brain", "implement feature X from repo Y", "use this repo as a reference", feature extraction, knowledge-graph requests, or NotebookLM study-prep from a codebase.
---

# Repository Intelligence

A web-native system for turning any GitHub repository into durable, reusable knowledge — organized for **both human study and agent execution**.

This skill has **four modes**. Figure out which one the user wants from their request, then jump to that section. When unsure, ask one short question rather than guessing.

| Mode | Trigger | What it does |
|------|---------|--------------|
| **DISTILL** | "distill / study / break down this repo", a GitHub URL | Read a repo over the web, reverse-engineer it feature by feature, write the study + build layers, update the graph |
| **GRAPH** | "update the graph", "rebuild the map", after any distill | Regenerate the interactive `graph.html` from `graph.json` |
| **APPLY** | "implement feature X from repo Y", "use this repo as reference" | Pull a distilled feature's build spec into the user's current project (Claude Code) |
| **ORGANIZE** | "clean up repo-brain", "reorganize", "what do I have" | Audit/maintain the mother repo's structure |

## Core philosophy (applies to every mode)

**The goal is to understand and reuse PRODUCTS, not catalog code.** Think in features, flows, and "how would I rebuild this," not classes and functions. Code is evidence for what the product *does* and *why*.

**Two readers, two layers — always keep them separate:**
- **study layer** → written for a *human* (the user) to read and upload to NotebookLM. Plain language, deep, no code tours. Answers "how does this actually work and why."
- **build layer** → written for *Claude Code in a future build* to transplant the feature. Technical, self-contained, includes the real logic/data shapes/gotchas. Answers "how do I rebuild this in a different codebase."

**Self-contained is non-negotiable.** The user does NOT keep repos on disk. When a feature is pulled later, the original repo may be gone. Every build-layer file must carry enough — inlined logic, data contracts, dependencies, gotchas — to rebuild the feature *without* the source. Never write "see file X in the repo" as the only reference; the repo won't be there.

**Web-native by default.** The user does not clone or download. Read repos over the web (raw.githubusercontent.com, the GitHub web UI, web_fetch). If running in Claude Code with a disposable sandbox and graph/MCP tools, those *may* be used — but they are an optional accelerator, never a requirement.

## The Mother Repo: `repo-brain`

Everything lives in ONE GitHub repo the user owns, organized **feature-first**. Never create per-repo scattered repos. Structure:

```
repo-brain/
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

Produce a quick internal fingerprint: what is this product, what's the stack, what are the candidate features. **Confirm the feature list with the user before going deep** unless they named a specific feature. Distilling every feature of a large repo is expensive; let them steer.

### Step 2 — For each feature, trace it end to end
Follow the feature trajectory: **entry point (route/UI) → handler/service → data model → external calls/side effects → result**. Read only the files on that path. This is the unit of understanding — not the file, the feature.

Capture as you go: what the user gets, the actual data shapes, the dependencies, the non-obvious decisions ("ghost PRs" — why is it built this way?), edge cases, and what would be hard to rebuild.

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

### Step 6 — Update the graph
Add/update nodes and edges in `graph/graph.json` (schema below), then run GRAPH mode to regenerate `graph.html`.

### Step 7 — Deliver to GitHub (always commit + push)
The user stores everything in their `repo-brain` GitHub repo and does NOT download locally. Commit the new/changed files, then **ALWAYS push** — do NOT ask for approval. The canonical branch is `main`; push there (`git push origin main`). Every distill ends with a push. If a GitHub MCP/connector is available it may be used; otherwise push with git directly.

### Step 8 — Log it in Notion (always)
After pushing, **ALWAYS log the distill** in the user's **Distill-it database** Notion database — no need to ask:
`https://app.notion.com/p/3833935b82a6808a8433c15a5f91b804?v=3833935b82a680d0bc0c000c2f7ca9fc`
(data source `collection://3833935b-82a6-802c-b668-000b9ba02404`). Create ONE row per distilled repo via the Notion MCP `notion-create-pages` tool with these properties:
- **Repo** (title) — the repo slug (e.g. `clicky`)
- **GitHub URL** — the source repo URL
- **Domain** (multi-select) — every domain the distill touched
- **Stack** (multi-select) — the repo's primary technologies
- **Status** = `Distilled`

`Date Added` is auto-set. This logging step is a standing instruction: every distill is recorded here.

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

1. **Locate the feature.** If the user names it ("the Supabase auth from productX"), fetch its build file from `repo-brain` over the web. If vague, read `graph.json` (or grep `features/*/build/`) and present matches.
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
- Repo sprawl: one repo per product. NO. One mother `repo-brain`, feature-first.
- Collapsing study and build into one doc — they serve different readers and one pollutes the other.
- Hand-editing `graph.html` — edit `graph.json` and regenerate.
- Code tours in the study layer — explain what the code *achieves*, in plain language.
- Distilling an entire large repo without confirming the feature list with the user first.
- Assuming a local clone or graph MCP exists — they're optional accelerators, not the spine.
