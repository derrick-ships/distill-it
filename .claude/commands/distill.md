---
description: Reverse-engineer a GitHub repo feature-by-feature into your repo-brain. Usage: /distill <github-url>
argument-hint: <github-repo-url>
---

You are running the **DISTILL** pipeline from the `repository-intelligence` skill. Read that
skill now (`.claude/skills/repository-intelligence/SKILL.md`) and follow its DISTILL mode and
its repo-brain conventions exactly. This command is the deterministic trigger for that pipeline.

## Target
The user wants to distill this repo: **$ARGUMENTS**

If `$ARGUMENTS` is empty, ask for the GitHub URL and stop.

## Run this exact flow

1. **Read the repo over the web** — do NOT clone or download. Accept the plain repo URL as-is
   (strip any trailing `.git`). Read README, manifests, and entry points to understand the product.

2. **Recommend the best features — do NOT enumerate or auto-distill everything.**
   First read `https://distill-graph.vercel.app/llms.txt` to see what is already in the brain.
   Then lead with a single pick: **"Take X, Y, or Z"** plus one short paragraph on why, judged by
   what the user is building, what fills a real gap (do not re-distill what is already there), and
   what is most distinctive here. No catalog, no over-justifying. Wait for their answer (accept,
   pick others, or "all") unless they named a specific feature.

3. **Distill the chosen feature(s)** per the skill: for each, write the **study** doc (human /
   NotebookLM layer) and the **build** doc (transplant-grade agent layer) into the correct
   feature-first folders under the local `repo-brain` repo. Update `repos/<repo>.md` (origin
   index) and `features/<domain>/_domain.md`.

4. **Update the graph** — add nodes/edges to `graph/graph.json`, then regenerate `graph/graph.html`
   (GRAPH mode in the skill).

5. **Commit to repo-brain.** Stage the new/changed files and commit with a clear message
   (e.g. `distill: <feature(s)> from <repo>`). If working inside the repo-brain repo, commit there.
   If the repo-brain repo isn't the current working dir, ask the user for its path (or to `cd` into it)
   before committing.

6. **Always push.** After committing, ALWAYS push to the repo-brain remote — do NOT ask first.
   The canonical branch is `main`; push there (`git push origin main`). This is a standing
   instruction: every `/distill` run ends with a push.

7. **Always log in Notion.** After pushing, ALWAYS log the distill in the user's
   **Distill-it database** Notion database (no need to ask):
   `https://app.notion.com/p/3833935b82a6808a8433c15a5f91b804?v=3833935b82a680d0bc0c000c2f7ca9fc`
   (data source `collection://3833935b-82a6-802c-b668-000b9ba02404`). Create ONE row per distilled
   repo via the Notion MCP `notion-create-pages` tool, setting: **Repo** (title = repo slug),
   **GitHub URL** (the source URL), **Domain** (multi-select of every domain touched),
   **Stack** (multi-select of the repo's primary technologies), and **Status** = `Distilled`.

6. **Update distill-graph too (REQUIRED).** distill-it is the source; the live PWA at
   https://distill-graph.vercel.app is its published face (map + `/stats` + `/llms.txt`). After
   pushing distill-it, sync distill-graph: use the `distill-graph-sync` skill, or run
   `DISTILL_IT=/path/to/distill-it ./scripts/update-from-distill-it.sh --deploy` in the distill-graph
   repo. A distill is not done until BOTH repos are live.

## Rules
- Self-contained build docs: never write "see the repo" as the only reference — the repo may be
  gone when this is reused later. Inline the real logic, data shapes, and gotchas.
- Feature-first organization, strict naming (`<feature-slug>--from-<repo-slug>.md`), repo name is
  `repo-brain` (singular).
- One repo per product is WRONG — everything goes into the single repo-brain, organized by feature.
