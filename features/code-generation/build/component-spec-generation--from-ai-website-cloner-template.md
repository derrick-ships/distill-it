# Component Specification Generation (build spec) — distilled from ai-website-cloner-template

## Summary

After browser-based design token extraction, identify all major page sections from DOM semantic structure + visual block analysis, then for each section write a structured Markdown spec to `docs/research/components/<name>.md`. The spec contains: exact computed CSS values (colors in oklch, sizes in px), interaction state diffs, responsive behavior, `public/` asset paths, and sample content. AI builders read specs verbatim; spec quality determines component quality.

## Core logic (inlined)

### Section identification
```typescript
interface Section {
  name: string
  element: ElementHandle
  bounds: { x: number; y: number; width: number; height: number }
  children: Section[]
}

async function identifySections(page: Page): Promise<Section[]> {
  return page.evaluate(() => {
    const sections: Array<{ name: string; bounds: DOMRect }> = []
    const viewportHeight = window.innerHeight
    
    // Priority 1: semantic landmarks
    const landmarks = [
      'header', 'nav', 'main', 'footer', 'aside',
      'section', 'article',
    ]
    landmarks.forEach(tag => {
      document.querySelectorAll(tag).forEach((el, i) => {
        const rect = el.getBoundingClientRect()
        if (rect.height > viewportHeight * 0.15) {  // >15% viewport height
          sections.push({
            name: `${tag}-${i}`,
            bounds: rect.toJSON(),
          })
        }
      })
    })
    
    // Priority 2: large divs with distinctive classes
    document.querySelectorAll('[class*="section"], [class*="hero"], [class*="feature"], [class*="pricing"]')
      .forEach((el) => {
        const rect = el.getBoundingClientRect()
        if (rect.height > viewportHeight * 0.15) {
          const name = [...el.classList].find(c => 
            ['hero', 'feature', 'pricing', 'testimonial', 'cta', 'section'].some(k => c.includes(k))
          ) ?? 'div-section'
          sections.push({ name, bounds: rect.toJSON() })
        }
      })
    
    return sections
  })
}
```

### Spec document generation
```typescript
function generateComponentSpec(params: {
  name: string
  tokens: DesignTokens
  sectionBounds: DOMRect
  screenshots: { normal: Buffer; hover: Buffer; mobile: Buffer; tablet: Buffer; desktop: Buffer }
  content: string[]
  assets: string[]
}): string {
  const { name, tokens, sectionBounds, content, assets } = params
  
  // Filter tokens to those visible in this section's bounds
  const sectionTokens = filterTokensToSection(tokens, sectionBounds)
  
  return `# Component: ${toTitleCase(name)}

## Layout
${describeLayout(sectionTokens.layout)}

## Colors
${sectionTokens.colors.map(c => `- ${c.role}: ${c.value}`).join('\n')}

## Typography
${sectionTokens.typography.map(t =>
  `- ${t.element}: font-family ${t.fontFamily}, ${t.fontSize}, weight ${t.fontWeight}, line-height ${t.lineHeight}`
).join('\n')}

## Interactions
${describeInteractionDiff(params.screenshots.normal, params.screenshots.hover, sectionBounds)}

## Responsive
- **Mobile (375px)**: ${describeLayout(filterTokensToSection(tokens, sectionBounds, 375).layout)}
- **Tablet (768px)**: ${describeLayout(filterTokensToSection(tokens, sectionBounds, 768).layout)}
- **Desktop (1440px)**: ${describeLayout(filterTokensToSection(tokens, sectionBounds, 1440).layout)}

## Assets
${assets.map(a => `- ${a}`).join('\n') || '- (no external assets)'}

## Content
${content.map(c => `- ${c}`).join('\n')}
`
}
```

### Interaction diff description
```typescript
function describeInteractionDiff(
  normalScreenshot: Buffer,
  hoverScreenshot: Buffer,
  bounds: DOMRect
): string {
  // Pixel diff the cropped section region between states
  // In practice: use an LLM with vision to describe the visual difference
  // Or: use Playwright's CDP to read style changes on hover events
  
  // Cheapest reliable approach: compare computed styles in both states
  // (requires running getComputedStyle twice with/without hover applied)
  return `[Describe what changes on hover/focus/active from visual diff]`
}
```

## Data contracts

### Spec document format (docs/research/components/*.md)
```markdown
# Component: HeroSection

## Layout
- Container: full-width, max-width 1280px, centered, padding 0 24px
- Structure: flexbox row at desktop, column at mobile
- Column ratio: 55% content / 45% image
- Vertical alignment: center

## Colors
- Background: oklch(0.08 0.015 260)
- Heading text: oklch(0.98 0.005 260)
- Body text: oklch(0.72 0.01 260)
- CTA button background: oklch(0.62 0.19 270)
- CTA button text: oklch(0.99 0 0)
- CTA button border: transparent
- Subheading accent: oklch(0.62 0.19 270)

## Typography
- H1: font-family "Inter", 56px, weight 700, line-height 1.1, letter-spacing -0.02em
- Subtitle: font-family "Inter", 20px, weight 400, line-height 1.6
- CTA button label: font-family "Inter", 16px, weight 600

## Interactions
- CTA button hover: background oklch(0.52 0.21 270) (darker), scale(1.02), transition 150ms ease-out
- CTA button active: scale(0.98), transition 80ms
- Links: text-decoration underline on hover, color shift to oklch(0.85 0.05 270)

## Responsive
- **Mobile (375px)**: column layout, H1 drops to 36px, letter-spacing -0.01em, image hidden below fold
- **Tablet (768px)**: column layout, H1 44px, image visible below text
- **Desktop (1440px)**: row layout, side-by-side, full 56px H1

## Assets
- /images/hero-background.jpg (1440x900 JPG, full-bleed background)
- /images/hero-illustration.svg (product screenshot illustration)
- /seo/logo.svg (top-left, 32px tall)

## Content
- H1: "Ship faster with AI-powered workflows"
- Subtitle: "Automate the repetitive. Focus on what matters."
- CTA label: "Start for free"
- Secondary CTA: "Watch demo →"
```

### File structure for specs output
```
docs/
└── research/
    ├── design-tokens.json         # Raw token extraction output
    ├── site-map.json              # Discovered URLs and sections
    ├── screenshots/
    │   ├── desktop-normal.png
    │   ├── desktop-hover.png
    │   ├── mobile.png
    │   └── tablet.png
    └── components/
        ├── hero.md
        ├── navbar.md
        ├── features-grid.md
        ├── pricing.md
        ├── testimonials.md
        └── footer.md
```

## Dependencies & assumptions

- Output of Phase 1 (design token extraction + screenshots) must be available in `docs/research/`
- Asset downloads (Phase 2) must be complete so `public/` paths are accurate
- An LLM with vision capability for interaction state description (or CDP-based style diffing)
- Playwright for DOM section identification

## To port this, you need:

- [ ] Section identification logic (semantic tag scan + size filter)
- [ ] A fixed spec template with the 7 sections: Layout, Colors, Typography, Interactions, Responsive, Assets, Content
- [ ] A function that maps raw `DesignTokens` records to a specific DOM region's bounds
- [ ] oklch-formatted color values (see browser-design-token-extraction build doc)
- [ ] Screenshot cropping to section bounds for visual diff
- [ ] A naming convention for component files (kebab-case matching the section identifier)
- [ ] An ordering convention (components listed in visual top-to-bottom page order)

## Gotchas

**Spec quality gates component quality.** The spec document is the AI builder's only reference. Missing an interaction state, using the wrong color value, or describing responsive behavior vaguely will produce a wrong component. Review specs before triggering builds.

**"Hero section" is ambiguous.** Semantic tag scanning finds sections, but the names are generic. The AI agent naming phase should use the section's visible heading text or landmark role to produce useful names (`hero`, `features-grid`, `social-proof`, `pricing-table`).

**Don't include the full HTML of the section.** It's tempting to include the section's raw HTML in the spec for reference. Don't — it trains the builder to copy class names from the original framework (e.g., Webflow's `w-` classes) instead of writing idiomatic Tailwind.

**Asset paths must be public/ relative.** Always write `/images/file.jpg` not `https://cdn.example.com/file.jpg`. The download step in Phase 2 must have already run.

**Content examples must be real.** Don't truncate long strings with `...`. AI builders will often reproduce the truncated text literally.

## Origin (reference only)

- Repo: https://github.com/JCodesMore/ai-website-cloner-template
- The spec generation is encoded in `.claude/skills/clone-website/SKILL.md` as agent instructions
- `docs/research/components/` directory convention is set in `AGENTS.md`
