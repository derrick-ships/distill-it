# Design Systems Library — from [open-design](https://github.com/nexu-io/open-design)

> Domain: [[_domain]] · Source: https://github.com/nexu-io/open-design · NotebookLM: 

## What it does

Open Design ships 150 brand-grade design specifications — for companies like Linear, Stripe, Apple, Notion, Figma, Slack, GitHub, Spotify, Airbnb, Tesla — stored as structured markdown files. When you pick one (or write "design this in the Linear style"), the entire spec gets injected into the AI agent's context so everything it generates matches that brand automatically.

## Why it exists

Without a design system, AI-generated UIs look like AI-generated UIs: generic, inconsistent, with random font sizes and colors. By encoding real brand systems — the actual hex values Stripe uses, the exact font weights GitHub specifies — the generated artifacts look like they came from those companies' design teams. It's the difference between "this looks like AI made it" and "this looks like it belongs."

## How it actually works

Each design system lives in a folder: `design-systems/<slug>/DESIGN.md`. That single markdown file follows a strict 9-section schema, always in the same order:

1. **Visual Theme & Atmosphere** — the mood, philosophy, key adjectives
2. **Color Palette & Roles** — actual hex values organized by role (primary, secondary, accent, surface, semantic, borders)
3. **Typography Rules** — font families with fallback stacks, OpenType features enabled, a hierarchy table (role → size/weight/line-height/letter-spacing)
4. **Component Stylings** — buttons, cards, inputs, navigation, with specific CSS values
5. **Layout Principles** — spacing system (usually 8px base unit), grid specs, border-radius scale
6. **Depth & Elevation** — shadow hierarchy in 5 levels, with rgba values and use cases for each
7. **Do's and Don'ts** — explicit prohibitions ("don't scatter multi-color accents") and mandates ("use aubergine for sidebar")
8. **Responsive Behavior** — breakpoint table, touch target sizes, how layouts collapse
9. **Agent Prompt Guide** — quick reference phrases and example prompts the AI agent should use

The daemon scans the `design-systems/` directory on startup — no registration needed. Drop a folder in, restart, and it appears in the picker.

At generation time, the selected DESIGN.md gets injected into the agent's system prompt alongside the skill instructions. The agent reads the brand spec and uses it to make every decision: which colors to pick, which font weights to use, how much shadow to add.

CSS custom properties from the design system get bound to `:root {}` blocks in generated HTML, with a `[data-theme="dark"]` override for dark mode. This means generated artifacts aren't just styled to match — they inherit a real CSS token system.

## The non-obvious parts

**The schema has exactly 9 numbered sections, in order.** The daemon's parser uses a regex matching `## [0-9].*` headers to locate sections. You can't add a section 10 or reorder them — it'll break the parser.

**You can add your own.** Drop a folder in `design-systems/your-brand/DESIGN.md` and restart. The schema is strict but it's just markdown. This is intentional: the whole library is meant to grow through community contribution.

**Skills can request only specific sections.** A skill that only does typography work might declare `design_system.sections: ["Typography Rules"]` to avoid bloating context with irrelevant brand data. This is a context efficiency pattern worth copying.

**Some real design system data is genuinely researched, not invented.** The Stripe spec mentions `sohne-var` font with `ss01` stylistic set, specific weight-300 headlines, and dual OpenType modes — that's from actual Stripe design documentation, not guessed.

## Related

- [[agentic-loop--from-open-design]] (where design systems get injected into the pipeline)
- [[skills-system--from-open-design]] (skills declare which design system sections they need)
- [[design-artifact-generation--from-open-design]] (CSS tokens from design systems appear in generated HTML)
