# Parallel Worktree Build (build spec) — distilled from ai-website-cloner-template

## Summary

Use `git worktree` to create isolated checkout directories, one per AI agent, each on its own branch. Agents build independent page sections in parallel without merge conflicts. After all agents finish, merge branches sequentially into main and delete worktrees. Section assignment is the critical design step — minimize shared file modifications across agents.

## Core logic (inlined)

### Worktree setup (orchestrator)
```bash
#!/bin/bash

# Assign sections to agents
# Agent 1: navbar, hero, footer
# Agent 2: features-grid, pricing
# Agent 3: testimonials, cta-banner, contact-form

SECTIONS_AGENT_1=("navbar" "hero" "footer")
SECTIONS_AGENT_2=("features-grid" "pricing")
SECTIONS_AGENT_3=("testimonials" "cta-banner" "contact-form")

# Create worktrees
for agent_id in 1 2 3; do
  git worktree add "builds/agent-${agent_id}" -b "build/agent-${agent_id}"
  echo "Created worktree: builds/agent-${agent_id} (branch: build/agent-${agent_id})"
done

# Each agent now builds in its worktree directory
# (trigger agents here via subprocess, MCP, or manual instruction)
echo "Worktrees ready. Trigger agent builds."
```

### Section assignment strategy
```typescript
interface Section {
  name: string
  specFile: string
  modifiesSharedFiles: string[]  // files other agents might also modify
}

function assignSections(
  sections: Section[],
  agentCount: number
): Map<number, Section[]> {
  // Rule 1: sections that touch shared files (page.tsx, globals.css)
  //         must go to the same agent, or use the slot pattern
  // Rule 2: distribute roughly equally by component count
  // Rule 3: sections that import from each other go to the same agent
  
  const sharedFileOwner = 0  // agent 0 owns page.tsx assembly
  const assignments = new Map<number, Section[]>()
  
  for (let i = 0; i < agentCount; i++) assignments.set(i, [])
  
  let agentIndex = 1  // skip 0 (reserved for shared files)
  for (const section of sections) {
    if (section.modifiesSharedFiles.includes('src/app/page.tsx')) {
      assignments.get(sharedFileOwner)!.push(section)
    } else {
      assignments.get(agentIndex % agentCount)!.push(section)
      agentIndex++
    }
  }
  
  return assignments
}
```

### Agent instruction template (per agent)
```markdown
# Build Agent ${agent_id} Instructions

You are building sections: ${sections.join(', ')}

## Your worktree directory
Work ONLY in: builds/agent-${agent_id}/

## Component specs
Read the following spec files for each section you must build:
${sections.map(s => `- docs/research/components/${s}.md`).join('\n')}

## What to build
For each section:
1. Read the spec at docs/research/components/<section>.md
2. Create src/components/<SectionName>.tsx using shadcn/ui + Tailwind v4
3. Match colors, typography, spacing, and interactions EXACTLY as specified
4. Use asset paths from public/ directory as listed in the spec

## What NOT to touch
- src/app/page.tsx (handled by Agent 1)
- src/app/globals.css (already configured in Phase 2)
- Any file not in src/components/ or src/hooks/

## When done
Run: npm run typecheck && npm run lint
Report any TypeScript errors before finishing.
```

### Merge phase (after all agents complete)
```bash
#!/bin/bash

# Merge agent branches into main sequentially
AGENT_COUNT=3

for agent_id in $(seq 1 $AGENT_COUNT); do
  echo "Merging build/agent-${agent_id}..."
  
  # Merge (should be clean if sections were non-overlapping)
  git merge "build/agent-${agent_id}" --no-ff -m "merge: agent-${agent_id} sections"
  
  if [ $? -ne 0 ]; then
    echo "ERROR: Merge conflict in agent-${agent_id}. Resolve manually."
    exit 1
  fi
  
  # Clean up
  git worktree remove "builds/agent-${agent_id}"
  git branch -d "build/agent-${agent_id}"
  
  echo "✓ agent-${agent_id} merged and cleaned up"
done

echo "All sections merged. Running QA..."
npm run check
```

### Page assembly slot pattern (prevents page.tsx conflicts)
```tsx
// src/app/page.tsx — written by orchestrator BEFORE parallel build starts
// Each agent's section gets imported here after merge

import { Navbar } from '@/components/Navbar'
import { Hero } from '@/components/Hero'
import { FeaturesGrid } from '@/components/FeaturesGrid'
import { Pricing } from '@/components/Pricing'
import { Testimonials } from '@/components/Testimonials'
import { Footer } from '@/components/Footer'

export default function Home() {
  return (
    <main>
      <Navbar />       {/* Agent 1 */}
      <Hero />         {/* Agent 1 */}
      <FeaturesGrid /> {/* Agent 2 */}
      <Pricing />      {/* Agent 2 */}
      <Testimonials /> {/* Agent 3 */}
      <Footer />       {/* Agent 1 */}
    </main>
  )
}
```

### Docker-based environment (Dockerfile.dev)
```dockerfile
FROM node:24-alpine

WORKDIR /app

# Install dependencies first (layer caching)
COPY package*.json ./
RUN npm ci

# Copy source
COPY . .

EXPOSE 3000
CMD ["npm", "run", "dev"]
```

```yaml
# docker-compose.yml
services:
  web:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "3000:3000"
    volumes:
      - .:/app
      - /app/node_modules  # anonymous volume prevents host override
    environment:
      - NODE_ENV=development
```

## Data contracts

### Worktree state after setup
```
my-project/
├── .git/                          # single shared git object store
├── builds/
│   ├── agent-1/                   # worktree for Agent 1
│   │   ├── src/
│   │   ├── public/
│   │   └── ...                    # full working copy on branch build/agent-1
│   ├── agent-2/                   # worktree for Agent 2
│   └── agent-3/                   # worktree for Agent 3
├── src/                           # main working tree (main branch)
├── docs/research/components/      # shared read-only specs
└── public/                        # shared read-only assets
```

### Key git commands
```bash
# Create worktree
git worktree add <path> -b <branch-name>

# List active worktrees
git worktree list

# Remove worktree (after branch merged)
git worktree remove <path>

# Remove worktree even if not clean
git worktree remove --force <path>

# Prune stale worktree entries
git worktree prune
```

## Dependencies & assumptions

- Git 2.15+ (worktree stable support)
- Node.js 24 (enforced via `.nvmrc`)
- `npm ci` in each worktree shares the root `node_modules/`
- Docker + Docker Compose for environment reproducibility
- Section specs in `docs/research/components/` are complete before starting parallel build
- `src/app/page.tsx` is pre-written using the slot pattern before agents start

## To port this, you need:

- [ ] Git 2.15+
- [ ] A section assignment plan that minimizes shared file conflicts
- [ ] Pre-written `src/app/page.tsx` with import slots before agents start
- [ ] `docs/research/components/*.md` spec files for each section
- [ ] `public/` assets downloaded before agents start
- [ ] An orchestration script to create worktrees, trigger agents, merge branches, clean up
- [ ] Per-agent instruction set scoping them to their sections and their worktree directory
- [ ] A post-merge `npm run check` (lint + typecheck + build) gate

## Gotchas

**`node_modules` is shared by default.** This is correct behavior. Don't run `npm install` inside worktrees — it modifies the shared node_modules and can corrupt other worktrees' runtime.

**Branches persist if agents fail.** Always write the merge + cleanup step as an atomic operation. If the script dies mid-merge, stale worktrees and branches accumulate. Add `trap 'git worktree prune' EXIT` to cleanup scripts.

**`src/app/page.tsx` is the classic conflict hotspot.** The slot pattern (pre-writing the import list) solves this. If agents must also generate the import list dynamically, use a merge strategy that concatenates unique import lines and section JSX blocks.

**globals.css is a secondary conflict point.** If agents need to add custom CSS variables or keyframes for their components, they'll all edit globals.css. Solve by: (a) putting all CSS vars in Phase 2 (before parallel build), (b) having each agent use a component-scoped CSS module instead, or (c) using `@layer components` in a per-component `.css` file imported by the component.

**Worktrees run on the same machine.** If your machine has 8 CPU cores, 3 agent worktrees running Next.js dev servers simultaneously will fight for ports and memory. Use distinct port assignments: 3000 (main), 3001 (agent-1), 3002 (agent-2), etc. Or don't run dev servers — just write files and run the build check at the end.

## Origin (reference only)

- Repo: https://github.com/JCodesMore/ai-website-cloner-template
- Pattern described in: `AGENTS.md` (parallel build section), `.claude/skills/clone-website/SKILL.md`
- Docker files: `Dockerfile`, `Dockerfile.dev`, `docker-compose.yml`
