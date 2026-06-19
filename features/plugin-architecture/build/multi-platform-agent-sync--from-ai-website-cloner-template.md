# Multi-Platform Agent Sync (build spec) — distilled from ai-website-cloner-template

## Summary

Maintain one canonical `AGENTS.md` document and two sync scripts: `sync-agent-rules.sh` propagates project instructions to 11+ platform-specific files (CLAUDE.md, GEMINI.md, .cursor/rules/, etc.) and `sync-skills.mjs` propagates skill/command definitions. Generated files carry a "do not edit" header and are committed to git. Run scripts after any AGENTS.md change.

## Core logic (inlined)

### AGENTS.md structure (source of truth)
```markdown
# Project: [Name]

## What this project does
[1-2 sentence product description]

## Tech stack
[Bullet list: Next.js 16, React 19, TypeScript, Tailwind CSS v4, shadcn/ui, ...]

## Project conventions
- File naming: kebab-case for files, PascalCase for React components
- Imports: absolute paths via `@/` alias
- Styles: Tailwind utility classes only; no inline styles; no CSS modules
- Components: shadcn/ui primitives + composition; no custom base components
- [All other enforced conventions...]

## Code quality rules
- No `any` types
- All components must be TypeScript with explicit prop interfaces
- [Other rules...]

## Skills
### /clone-website
[The full clone-website skill definition, or a reference to .claude/skills/clone-website/SKILL.md]

## Safety & ethics
- Never clone phishing sites
- Always verify permission to clone a target site
```

### sync-agent-rules.sh
```bash
#!/bin/bash
# DO NOT EDIT the generated files — edit AGENTS.md instead

AGENTS_MD="./AGENTS.md"
GENERATED_HEADER="<!-- DO NOT EDIT — generated from AGENTS.md by scripts/sync-agent-rules.sh -->\n"

# Claude Code
echo -e "${GENERATED_HEADER}" > CLAUDE.md
cat "$AGENTS_MD" >> CLAUDE.md
echo "✓ CLAUDE.md"

# Gemini CLI
echo -e "${GENERATED_HEADER}" > GEMINI.md
cat "$AGENTS_MD" >> GEMINI.md
echo "✓ GEMINI.md"

# Cursor (needs MDC frontmatter)
mkdir -p .cursor/rules
cat > .cursor/rules/project.mdc << EOF
---
alwaysApply: true
---
$(cat "$AGENTS_MD")
EOF
echo "✓ .cursor/rules/project.mdc"

# GitHub Copilot
mkdir -p .github
echo -e "${GENERATED_HEADER}" > .github/copilot-instructions.md
cat "$AGENTS_MD" >> .github/copilot-instructions.md
echo "✓ .github/copilot-instructions.md"

# Cline
echo -e "${GENERATED_HEADER}" > .clinerules
cat "$AGENTS_MD" >> .clinerules
echo "✓ .clinerules"

# Windsurf
echo -e "${GENERATED_HEADER}" > .windsurfrules
cat "$AGENTS_MD" >> .windsurfrules
echo "✓ .windsurfrules"

# Aider
echo -e "${GENERATED_HEADER}" > AIDER.md
cat "$AGENTS_MD" >> AIDER.md
echo "✓ AIDER.md"

# Amazon Q
mkdir -p .amazonq
echo -e "${GENERATED_HEADER}" > .amazonq/rules.md
cat "$AGENTS_MD" >> .amazonq/rules.md
echo "✓ .amazonq/rules.md"

echo ""
echo "All agent rule files updated from AGENTS.md"
```

### sync-skills.mjs (Node.js)
```javascript
#!/usr/bin/env node
import { readFileSync, writeFileSync, mkdirSync } from 'fs'

const SOURCE_SKILL = '.claude/skills/clone-website/SKILL.md'
const skillContent = readFileSync(SOURCE_SKILL, 'utf-8')
const HEADER = '<!-- DO NOT EDIT — generated from .claude/skills/clone-website/SKILL.md -->\n\n'

// Extract frontmatter and body
const frontmatterMatch = skillContent.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/)
const [, , skillBody] = frontmatterMatch || [null, null, skillContent]

// Cursor skill (MDC format)
mkdirSync('.cursor/rules', { recursive: true })
writeFileSync('.cursor/rules/clone-website.mdc', `---
description: Clone a website into a Next.js app
alwaysApply: false
---

${HEADER}${skillBody}`)
console.log('✓ .cursor/rules/clone-website.mdc')

// Continue (JSON format)
mkdirSync('.continue', { recursive: true })
const continueConfig = {
  customCommands: [{
    name: 'clone-website',
    description: 'Clone a website into a Next.js app',
    prompt: skillBody,
  }]
}
writeFileSync('.continue/clone-website.json', JSON.stringify(continueConfig, null, 2))
console.log('✓ .continue/clone-website.json')

// Platforms without native skill support: append to their rules file
const noSkillPlatforms = [
  { file: 'GEMINI.md', prefix: '\n\n## Available Skills\n\n### /clone-website\n\n' },
  { file: '.clinerules', prefix: '\n\n## Available Skills\n\n### /clone-website\n\n' },
]
noSkillPlatforms.forEach(({ file, prefix }) => {
  const existing = readFileSync(file, 'utf-8')
  if (!existing.includes('/clone-website')) {
    writeFileSync(file, existing + prefix + skillBody)
    console.log(`✓ ${file} (skill appended)`)
  }
})
```

### SKILL.md canonical format (.claude/skills/clone-website/SKILL.md)
```markdown
---
name: clone-website
description: Clone any website into a production-ready Next.js app using a 5-phase AI pipeline.
---

## Usage
/clone-website <URL> [<URL2> ...]

## What I do
[Full 5-phase pipeline instructions for the AI agent...]
Phase 1 — Reconnaissance: ...
Phase 2 — Foundation: ...
Phase 3 — Component Specs: ...
Phase 4 — Parallel Build: ...
Phase 5 — Assembly & QA: ...
```

## Data contracts

### Platform file map
| Platform | File | Format |
|---|---|---|
| Claude Code | `CLAUDE.md` | Markdown |
| Gemini CLI | `GEMINI.md` | Markdown |
| Cursor | `.cursor/rules/project.mdc` | MDC (frontmatter + markdown) |
| GitHub Copilot | `.github/copilot-instructions.md` | Markdown |
| Cline | `.clinerules` | Markdown |
| Windsurf | `.windsurfrules` | Markdown |
| Aider | `AIDER.md` | Markdown |
| Amazon Q | `.amazonq/rules.md` | Markdown |
| Augment Code | `.augment/rules.md` | Markdown |
| Continue | `.continue/config.json` | JSON (`customCommands[]`) |
| Codex CLI | `CODEX.md` | Markdown |

### npm scripts to wire sync
```json
{
  "scripts": {
    "sync-rules": "bash scripts/sync-agent-rules.sh",
    "sync-skills": "node scripts/sync-skills.mjs",
    "sync": "npm run sync-rules && npm run sync-skills"
  }
}
```

## Dependencies & assumptions

- Bash 3+ for `sync-agent-rules.sh`
- Node.js 18+ for `sync-skills.mjs` (uses `fs/promises` ESM)
- All target platform directories/files must already have a base structure (the script creates missing dirs)
- SKILL.md uses YAML frontmatter (`---` delimited)

## To port this, you need:

- [ ] `AGENTS.md` as the authoritative instruction source
- [ ] `scripts/sync-agent-rules.sh` generating platform copies from AGENTS.md
- [ ] `scripts/sync-skills.mjs` propagating skill definitions
- [ ] `npm run sync` wired in package.json
- [ ] A `# DO NOT EDIT` header in every generated file
- [ ] Generated files committed to git (not gitignored)
- [ ] The canonical skill in `.claude/skills/<name>/SKILL.md`
- [ ] Platform-specific path creation (`mkdir -p`) in each script

## Gotchas

**Generated files get edited directly.** Team members unfamiliar with the pattern will edit `.cursor/rules/project.mdc` directly instead of AGENTS.md. The "DO NOT EDIT" header helps but doesn't prevent this. Consider adding a git pre-commit hook that detects edits to generated files and prompts to run the sync instead.

**Platform formats drift.** Cursor's MDC format, Continue's JSON schema, and Amazon Q's rules format change across versions. The sync scripts need maintenance when platforms update.

**AGENTS.md is not the skill — it references it.** Don't embed the full skill definition in AGENTS.md. Keep it in `.claude/skills/clone-website/SKILL.md` and have AGENTS.md say "See .claude/skills/clone-website/SKILL.md for the /clone-website command." Then sync-skills.mjs handles propagation separately.

**Some platforms have character limits.** GitHub Copilot instructions have a documented length limit. If AGENTS.md is very long, truncation may silently cut off rules. Keep AGENTS.md under 4000 tokens (roughly 16000 characters).

## Origin (reference only)

- Repo: https://github.com/JCodesMore/ai-website-cloner-template
- Key files: `AGENTS.md`, `scripts/sync-agent-rules.sh`, `scripts/sync-skills.mjs`, `.claude/skills/clone-website/SKILL.md`
- Platform configs: `.cursor/`, `.continue/`, `.github/copilot-instructions.md`, `.amazonq/`, etc.
