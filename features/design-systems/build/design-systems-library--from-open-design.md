# Design Systems Library (build spec) — distilled from open-design

## Summary

150 brand-grade `DESIGN.md` files with a fixed 9-section schema. Zero-config directory scan on daemon startup. Selected system gets injected into agent system prompt + CSS custom properties in generated HTML. Skills can request specific sections only. Parser uses `## [0-9].*` heading regex to extract sections.

## Core logic (inlined)

**Discovery (on daemon startup):**
```
scan design-systems/*/DESIGN.md
for each:
  parse frontmatter: { displayName (H1), category (blockquote), summary (first line) }
  extract section list via grep /^## [0-9]/
  register in catalog for picker UI
```

**14 picker categories (from frontmatter):**
AI & LLM, Developer Tools, Productivity & SaaS, Design & Creative, Fintech & Crypto, E-Commerce & Retail, + others

**9-section schema (order is strict, parser depends on it):**
```
## 1. Visual Theme & Atmosphere
## 2. Color Palette & Roles
## 3. Typography Rules
## 4. Component Stylings
## 5. Layout Principles
## 6. Depth & Elevation
## 7. Do's and Don'ts
## 8. Responsive Behavior
## 9. Agent Prompt Guide
```

**Injection at generation time:**
```
systemPrompt = skillInstructions + "\n\n" + selectedDesignMd
// or, if skill declares sections:
filteredMd = extractSections(designMd, skill.od.design_system.sections)
systemPrompt = skillInstructions + "\n\n" + filteredMd
```

**CSS token binding in generated HTML:**
```css
:root {
  --color-primary: #0969da;   /* from Color Palette section */
  --font-body: "Inter", system-ui;
  --shadow-medium: 0 4px 12px rgba(0,0,0,0.15);
}
[data-theme="dark"] {
  --color-primary: #4493f8;
}
```

## Data contracts

**DESIGN.md frontmatter (inline, not YAML):**
```markdown
# Brand Name       ← H1 = display name in picker
> Category: Developer Tools    ← blockquote = picker grouping
One-line summary shown on hover.

## 1. Visual Theme & Atmosphere
...
## 2. Color Palette & Roles
| Role | Hex | Usage |
|------|-----|-------|
| Primary | #0969da | CTAs, links, focus rings |
...
## 3. Typography Rules
Font: Inter (system-ui fallback)
OpenType: ss01, cv05
| Role | Size | Weight | Line-Height | Letter-Spacing |
| Display | 48px | 600 | 1.1 | -0.02em |
...
## 9. Agent Prompt Guide
Quick reference: "GitHub engineering-dense layout, Primer blue CTAs, system-ui body"
Example prompt: "Design a repository settings page in the GitHub design system"
```

**Component Manifest (extracted from generated HTML):**
```typescript
ComponentsManifest = {
  groups: {
    buttons: ComponentGroup,
    inputs: ComponentGroup,
    cards: ComponentGroup,
    badges: ComponentGroup,
    links: ComponentGroup,
    keyboard: ComponentGroup,
    icons: ComponentGroup,
    typography: ComponentGroup,
    layout: ComponentGroup
  },
  tokenAnalysis: {
    declared: string[],
    referenced: string[],
    unused: string[],
    undeclared: string[]
  },
  literals: {
    colors: string[],
    pixels: string[],
    fontFamilies: string[]
  }
}
```

**Skill design-system binding (in SKILL.md frontmatter):**
```yaml
od:
  design_system:
    requires: true              # inject selected system
    sections: ["2. Color Palette & Roles", "3. Typography Rules"]  # prune to these only
```

## Dependencies & assumptions

- No npm packages — pure markdown parsing
- Parser uses regex `## [0-9].*` — sections MUST be numbered, in order 1-9
- Storage: files on disk under `design-systems/<slug>/DESIGN.md`
- Daemon restart required to pick up new systems (no hot reload confirmed)
- CSS variable names are agent-generated from color/typography values — no formal naming spec enforced

## To port this, you need:

- [ ] Directory scanner that reads `design-systems/*/DESIGN.md` on startup
- [ ] Frontmatter parser: extract H1 (display name), first blockquote (category), first paragraph (summary)
- [ ] Section extractor: split on `## [0-9].*` headings
- [ ] Picker UI with 14 category groupings
- [ ] System prompt injector: append full DESIGN.md (or filtered sections) to skill instructions
- [ ] Skill-level section filter: if skill declares `design_system.sections`, only inject those sections
- [ ] CSS token binder: agent generates `:root {}` block; dark mode via `[data-theme="dark"]`

## Gotchas

- **Section order is load-bearing.** The parser finds sections by numbered heading regex. Unnumbered or reordered sections silently break section extraction.
- **Design system prompt injection can bloat context fast.** A full DESIGN.md can be 3-5KB. Multiply by complex skill instructions and you eat into the agent's working window. Use section filtering aggressively.
- **Technical content stays in English.** Translated UI labels are fine; translated prompt instructions break agent behavior. This is explicit in the codebase.
- **Persistance of selected system is unconfirmed.** AppConfigPrefs has `designSystemId` field suggesting SQLite persistence, but the exact read/write path was not traced.

## Origin (reference only)

Repo: https://github.com/nexu-io/open-design  
Key files: `design-systems/*/DESIGN.md`, `apps/daemon/src/design-system-routes.ts`, schema parser in daemon startup, `apps/daemon/src/plugin-runtime/`
