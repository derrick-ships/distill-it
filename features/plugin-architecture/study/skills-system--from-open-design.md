# Skills System — from [open-design](https://github.com/nexu-io/open-design)

> Domain: [[_domain]] · Source: https://github.com/nexu-io/open-design · NotebookLM: 

## What it does

Skills are reusable design workflows that tell the AI exactly what to build and how. There are 100+ built-in skills covering everything from web prototypes to motion graphics to presentation decks. You pick a skill, pick a design system, type your brief, and the AI executes the skill's instructions with your brand applied. Anyone can add custom skills by dropping a folder into the right directory.

## Why it exists

Without skills, every request starts from scratch — you'd have to re-explain "make an HTML prototype with React, inline all CSS, use this brand system" every single time. Skills encode repeatable design workflows as reusable prompts, so the knowledge of *how* to build a good landing page, deck, or dashboard is captured once and applied everywhere.

## How it actually works

A skill is a folder with a `SKILL.md` file at the center. The SKILL.md has two parts:

**Frontmatter (metadata):** Declares the skill's identity — its name, description, what keywords trigger it, and optional Open Design extensions like which artifact mode it produces, what the preview looks like, what inputs it accepts, and whether it needs a design system injected.

**Body (instructions):** Regular markdown that tells the AI what to do. This is the actual workflow — "start by auditing the brief, then plan 3 sections, then generate the HTML, checking each section against the design system typography rules."

When you pick a skill in the UI, its SKILL.md gets injected into the agent's system prompt alongside the design system. The AI then follows those instructions with your specific brief.

**Skill types (modes):**
- `prototype` — interactive HTML/React UIs
- `deck` — presentation slides
- `template` — reference HTML implementations
- `design-system` — the system definitions themselves
- `image` — static image generation
- `video` — MP4 video via motion APIs
- `audio` — audio generation

**The trigger keyword system:** Skills can declare specific phrases in their `triggers` array. During the agent's planning phase, it looks for these keywords in your brief and auto-recommends relevant skills. Vague keywords like "create" are explicitly discouraged — triggers must be specific to work well.

**The adapter layer:** When an agent CLI (Claude Code, Cursor, etc.) encounters a skill, it goes through an adapter that converts the SKILL.md frontmatter into a `PluginManifest` object. This is a normalization step — the manifest is what the runtime actually uses, not the raw SKILL.md. The adapter handles type mapping (`"integer"` → `"number"`) and warns about fields it can't translate.

**Zero-config discovery:** Drop a skill folder into `skills/` and restart the daemon. No registration file needed.

## The non-obvious parts

**Skills are not code modules.** There's no JavaScript in a skill. It's a prompt template with metadata. The skill's entire "execution" is injecting its text into an AI agent's context.

**Digest computation makes skills reproducible.** The system hashes `manifest + inputs + resolved context refs` with SHA-256 to produce a deterministic signature. Two invocations of the same skill with the same inputs and the same design system always produce the same digest. This is used for caching and for auditing: you can prove that a given artifact was generated from a specific skill version.

**Sidecar JSON can override everything.** An `open-design.json` file next to `SKILL.md` gets highest priority in the 3-layer merge (sidecar > adapter > fallback). This is how power users customize official skills without editing the original file.

**The plugin-runtime is pure TypeScript with no Node.js imports.** This was a deliberate design choice so the runtime can run in the daemon, in a browser, and in CI without platform-specific code.

## Related

- [[plugin-ecosystem--from-open-design]] (how skills are discovered and invoked at runtime)
- [[agentic-loop--from-open-design]] (skills shape each stage of the pipeline)
- [[design-systems-library--from-open-design]] (skills bind to design systems via frontmatter)
- [[agent-cli-integration--from-open-design]] (22+ agent CLIs that execute skill instructions)
