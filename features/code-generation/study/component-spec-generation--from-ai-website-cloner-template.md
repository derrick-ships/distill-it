# Component Specification Generation — from [ai-website-cloner-template](https://github.com/JCodesMore/ai-website-cloner-template)

> Domain: [[_domain]] · Source: https://github.com/JCodesMore/ai-website-cloner-template · NotebookLM:

## What it does

Phase 3 of the website cloning pipeline generates a structured Markdown specification document for each identified page section or UI component. These documents contain everything an AI coding agent needs to build the component accurately: exact computed CSS values, interaction behavior descriptions, responsive layout changes, required asset paths, and sample content. They act as a stable, human-readable interface between the reconnaissance phase and the construction phase.

## Why it exists

Without specs, AI builders hallucinate details. Given only a screenshot and the instruction "build this hero section in React," an agent will invent colors, spacing, and hover behaviors that weren't in the original. The spec document forces the reconnaissance step to capture every relevant detail in a structured, queryable format before any code is written. This also decouples the two phases: you can regenerate a component without repeating the entire browser crawl.

## How it actually works

After the reconnaissance phase collects raw design tokens and screenshots, the agent identifies the major sections on the page (hero, navbar, features grid, testimonials, pricing, footer, etc.) by analyzing the DOM's semantic structure, large visual groupings, and element hierarchy.

For each identified section, it writes a spec document to `docs/research/components/<section-name>.md` following a fixed schema:

**Layout block**: describes the overall container (max-width, padding, flexbox vs grid, column ratios, alignment). This comes from the computed display, flex, and width properties of the section's container element.

**Colors block**: lists every distinct color role in the section — background, text, accent, border, icon — with exact oklch values. These come directly from `getComputedStyle()`, not guessed from a palette.

**Typography block**: for each text element in the section, gives font-family, font-size (in px), font-weight (numeric), line-height, and letter-spacing. AI agents often get font weight wrong; the spec makes it explicit.

**Interactions block**: describes what visually changes at hover, focus, and active states — drawn from the diff between normal and interaction-state screenshots. A hover state might be "button background shifts from oklch(0.65 0.18 270) to oklch(0.55 0.20 270), scale 1.02, transition 200ms ease."

**Responsive block**: for mobile, tablet, and desktop, describes how the layout changes — column stacking, font size reduction, element hiding. This comes from the viewport-resized screenshots.

**Assets block**: lists the `public/` paths for every image, video, or icon the section needs. These paths are already downloaded by Phase 2, so they're guaranteed to exist.

**Content block**: samples of the actual text content from the live site — headlines, body text, button labels. This prevents the AI from generating placeholder "Lorem ipsum" text.

The agent writes these as plain Markdown so they're readable by humans, uploadable to NotebookLM, and easily parsed by AI agents in subsequent sessions.

## The non-obvious parts

**Specs are the intelligence bottleneck.** The quality of the generated component is proportional to the richness of the spec, not the capability of the AI builder. A detailed spec + mediocre model often beats a thin spec + powerful model.

**Section identification is heuristic-based.** The agent uses semantic landmarks (`<header>`, `<main>`, `<footer>`, `<section>`, `<article>`) plus visual block size (elements occupying >20% of the viewport height) and repeated structural patterns (grid items with identical structure) to identify component boundaries. This is not always perfect — complex layered layouts sometimes need manual section naming.

**Exact values over approximations.** The spec always uses exact computed values, not semantic descriptions. "56px, weight 700" beats "large, bold." "oklch(0.65 0.18 270)" beats "blue."

**The spec becomes the source of truth.** Once the spec is written, the builder agent references it for every decision. If the spec is wrong (e.g., a screenshot was taken before a lazy-loaded background appeared), the component will be wrong. Reviewing specs before building is the highest-ROI QA step.

## Related

- [[website-cloning-pipeline--from-ai-website-cloner-template]] — Phase 3 in the full pipeline
- [[browser-design-token-extraction--from-ai-website-cloner-template]] — feeds the raw data into specs
- [[scraper-code-generation--from-llm-scraper]] — a different approach: generating code from a schema instead of from a spec doc
- [[design-systems-library--from-open-design]] — an alternative spec format: 9-section DESIGN.md per theme
- [[interview-driven-scaffolding--from-whatsapp-agentkit]] — related pattern: using structured docs to drive AI code generation
