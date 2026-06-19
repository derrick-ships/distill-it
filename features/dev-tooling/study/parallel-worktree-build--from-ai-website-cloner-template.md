# Parallel Worktree Build — from [ai-website-cloner-template](https://github.com/JCodesMore/ai-website-cloner-template)

> Domain: [[_domain]] · Source: https://github.com/JCodesMore/ai-website-cloner-template · NotebookLM:

## What it does

When building a multi-section website with multiple AI coding agents running simultaneously, this pattern uses git worktrees to give each agent its own isolated copy of the repository on a separate branch. The agents build different page sections in parallel without ever touching each other's files. Once all sections are complete, the worktrees are merged back into the main branch.

## Why it exists

Running two AI agents on the same branch simultaneously causes race conditions. Both agents might modify `src/app/globals.css` to add their component's styles, `src/components/ui/button.tsx` to customize a shared primitive, or `src/app/page.tsx` to assemble the layout — and their changes will conflict. Without isolation, you get merge conflicts, lost work, or corrupted files. Git worktrees solve this cleanly: each agent has its own working directory with its own branch, so there are no collisions mid-build.

## How it actually works

Git's worktree feature lets you check out multiple branches of the same repository simultaneously in different directories, all sharing one `.git` folder (so they stay in sync on refs and objects). The website cloning pipeline uses this during Phase 4:

The orchestrating agent (or human) looks at the component specs generated in Phase 3 and divides the sections among available agents. Sections are grouped so each agent gets a coherent, independent slice: one agent might get navbar + hero + footer, another gets features grid + pricing + CTA. The goal is to minimize cross-agent dependencies on shared files.

For each agent, a new worktree is created: `git worktree add builds/<agent-id> -b build/<agent-id>`. This creates a new directory `builds/<agent-id>/` with a fresh checkout of a new branch. The agent is given instructions referencing its component specs and told to build in that directory.

The agents work in parallel. Each one creates new component files (`src/components/Hero.tsx`, `src/components/FeaturesGrid.tsx`, etc.) and may modify the page assembly file (`src/app/page.tsx`) and global styles. Because they're on separate branches, their changes are isolated.

Once all agents complete, the orchestrator merges each worktree branch into main sequentially. If the section assignments were designed well (agents don't share the same files), merges are clean. After each merge, the worktree directory and branch are deleted.

The Docker-based development setup (Dockerfile, docker-compose.yml) ensures every agent worktree runs in an identical environment — same Node.js version, same package versions — regardless of what the host machine has installed.

## The non-obvious parts

**Section assignment is the critical design decision.** The goal is to make each agent's work completely non-overlapping. The hard constraint: `src/app/page.tsx` assembles all sections, so every agent will try to modify it. One solution is to have only one agent own `page.tsx` and import from completed components from other branches after they finish. Another is to use a component-slot pattern where `page.tsx` is written upfront with `{/* SLOT: HeroSection */}` comments, and each agent fills in their slot on their branch.

**Worktrees share the node_modules.** By default, `git worktree add` creates a worktree without a separate `node_modules/`. All worktrees reference the parent's `node_modules/`, which is correct and efficient. Running `npm install` in one worktree affects all.

**Worktrees can become stale.** If an agent crashes mid-build, the worktree and its branch remain. They need to be cleaned up manually (`git worktree remove builds/<id>`, `git branch -d build/<id>`).

**Docker makes this reproducible.** The `Dockerfile.dev` ships with the template so each agent (or each human team member) can run in a container with the exact same Node.js 24 and npm versions, preventing "it works on my machine" issues in the generated code.

## Related

- [[website-cloning-pipeline--from-ai-website-cloner-template]] — Phase 4 of the pipeline
- [[component-spec-generation--from-ai-website-cloner-template]] — the specs that drive each agent's work
- [[multi-platform-agent-sync--from-ai-website-cloner-template]] — how each agent's instructions are consistent across platforms
- [[agentic-loop--from-open-design]] — an alternative orchestration pattern for AI build pipelines (linear rather than parallel)
