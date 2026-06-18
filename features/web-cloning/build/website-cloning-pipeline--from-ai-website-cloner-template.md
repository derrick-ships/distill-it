# Website Cloning Pipeline (build spec) — distilled from ai-website-cloner-template

## Summary

A five-phase AI-driven pipeline that converts a target URL into a deployable Next.js 16 / React 19 application. The agent performs browser-based reconnaissance (computed styles, screenshots, asset inventory), writes a Tailwind v4 foundation, generates per-component spec documents, runs parallel AI builds in git worktrees, then merges and QA-validates the result. Triggered via a `/clone-website` slash command in Claude Code or any supported AI agent.

## Core logic (inlined)

### Phase 1 — Reconnaissance

```
visit(targetURL, browser)
  screenshots = capture([mobile(375), tablet(768), desktop(1440)])
  for each breakpoint:
    interactionScreenshots = capture(
      states=[hover, active, focus, scroll-at-25%, scroll-at-75%]
    )
  
  designTokens = page.evaluate(() => {
    elements = querySelectorAll('*')
    for each element:
      computed = getComputedStyle(element)
      record({
        selector: element,
        color: computed.color,
        backgroundColor: computed.backgroundColor,
        fontFamily: computed.fontFamily,
        fontSize: computed.fontSize,
        fontWeight: computed.fontWeight,
        lineHeight: computed.lineHeight,
        letterSpacing: computed.letterSpacing,
        padding: computed.padding,
        margin: computed.margin,
        borderRadius: computed.borderRadius,
        // ... all relevant properties
      })
  })
  
  siteMap = discoverLinks(page)
  sections = identifySections(page, screenshots)
  
  save({ screenshots, interactionScreenshots, designTokens, siteMap, sections },
       'docs/research/')
```

### Phase 2 — Foundation

```
// 1. Rewrite globals.css with extracted tokens
globals = generateTailwindV4Config(designTokens)
write('src/app/globals.css', globals)

// 2. Download all assets
for each imageURL in designTokens.images:
  download(imageURL, 'public/images/')
for each videoURL in designTokens.videos:
  download(videoURL, 'public/videos/')
download(faviconURL, 'public/seo/favicon.ico')
download(ogImageURL, 'public/seo/og.png')

// 3. Configure typography
fonts = extractFonts(designTokens)
updateNextConfig(fonts)  // next/font configuration
```

### Phase 3 — Component Specifications

```
for each section in sections:
  spec = {
    name: section.identifier,
    layout: describeLayout(section, designTokens),
    
    // Exact computed values — the key to spec-driven accuracy
    styles: {
      colors: extractColors(section, designTokens),
      typography: extractTypography(section, designTokens),
      spacing: extractSpacing(section, designTokens),
      borders: extractBorders(section, designTokens),
      shadows: extractShadows(section, designTokens),
    },
    
    // Interaction model from screenshots
    interactions: {
      hover: diff(normalScreenshot, hoverScreenshot, section.bounds),
      active: diff(normalScreenshot, activeScreenshot, section.bounds),
      focus: diff(normalScreenshot, focusScreenshot, section.bounds),
    },
    
    // Responsive behavior
    responsive: {
      mobile: extractLayout(mobileScreenshot, section),
      tablet: extractLayout(tabletScreenshot, section),
      desktop: extractLayout(desktopScreenshot, section),
    },
    
    // Asset references
    assets: findAssetsInSection(section, 'public/'),
    
    // Content examples from the live site
    content: extractTextContent(section),
  }
  
  write(`docs/research/components/${section.identifier}.md`, formatSpec(spec))
```

### Phase 4 — Parallel Build

```
// Single agent path
for each section in sections:
  component = buildComponent(spec[section], {
    framework: 'nextjs',
    uiLib: 'shadcn/ui',
    styleEngine: 'tailwind-v4',
    typescript: true,
  })
  write(`src/components/${toPascalCase(section)}.tsx`, component)

// Multi-agent path (git worktrees)
for each (agent, sections) in assignSections(agents, sections):
  worktree = createGitWorktree(`builds/${agent.id}`)
  agent.build(worktree, sections)  // parallel, no shared state

// Merge
for each worktree in worktrees:
  merge(worktree, target='main')
  deleteWorktree(worktree)
```

### Phase 5 — Assembly & QA

```
assemblePages(components, siteMap)
  -> generate src/app/page.tsx (and nested routes if multi-page)
  -> integrate navigation, footer, global layout

// Visual QA
for each page:
  currentScreenshot = screenshot(localhost:3000/page)
  originalScreenshot = screenshots.desktop[page]
  diff = visualDiff(currentScreenshot, originalScreenshot)
  if diff.score < threshold:
    flagForReview(page, diff)

// Code QA
run('npm run typecheck')   // TypeScript strict compilation
run('npm run lint')        // ESLint
run('npm run build')       // Next.js production build
```

## Data contracts

### Design Token Shape (stored in docs/research/)
```typescript
interface DesignToken {
  selector: string           // CSS selector path
  color: string              // computed color (oklch or rgb)
  backgroundColor: string
  fontFamily: string
  fontSize: string           // px value
  fontWeight: string         // numeric e.g. "600"
  lineHeight: string         // e.g. "1.5" or "24px"
  letterSpacing: string      // e.g. "0.02em"
  padding: string            // shorthand computed
  margin: string
  borderRadius: string
  display: string
  flexDirection?: string
  gap?: string
  // ... all relevant computed properties
}
```

### Component Spec Doc Format (docs/research/components/*.md)
```markdown
# Component: HeroSection

## Layout
- Full-width container, max-width 1280px, centered, px-6 padding
- Flexbox row at desktop, column at mobile
- Two columns: 55% content / 45% image

## Colors
- Background: oklch(0.12 0.02 240)
- Heading: oklch(0.98 0.01 240)
- Body text: oklch(0.75 0.01 240)
- CTA button bg: oklch(0.65 0.18 270)
- CTA button text: white

## Typography
- H1: font-family Inter, 56px/1.1, weight 700, tracking -0.02em
- Body: font-family Inter, 18px/1.6, weight 400

## Interactions
- CTA button hover: background shifts to oklch(0.55 0.20 270), scale 1.02, transition 200ms ease

## Responsive
- Mobile (375px): stacked column, H1 drops to 36px, image hidden
- Tablet (768px): stacked column, H1 44px, image visible below
- Desktop (1440px): side-by-side, full layout

## Assets
- Hero image: /images/hero-background.jpg
- Logo: /images/logo.svg

## Content
- H1: [exact text from live site]
- Subtitle: [exact text]
- CTA label: [exact text]
```

### Tailwind v4 globals.css Token Output
```css
@import "tailwindcss";

:root {
  --color-brand-primary: oklch(0.65 0.18 270);
  --color-brand-secondary: oklch(0.55 0.20 270);
  --color-text-primary: oklch(0.12 0.02 240);
  --color-text-secondary: oklch(0.45 0.01 240);
  --color-background: oklch(0.98 0.005 240);
  --font-body: 'Inter', sans-serif;
  --font-heading: 'Inter', sans-serif;
}
```

## Dependencies & assumptions

- **Node.js 24+** (enforced; `.nvmrc` file ships with template)
- **Next.js 16** with App Router
- **React 19**
- **TypeScript** (strict mode)
- **Tailwind CSS v4** with oklch color tokens
- **shadcn/ui** (Radix UI primitives + Tailwind)
- **Lucide React** as default icon set (replaced by extracted SVGs during build)
- **AI agent with browser access** (Claude Code with `--chrome` flag, or equivalent)
- Target site must allow headless browser access (no bot blocking)
- AI agent must have write access to the project directory

## To port this, you need:

- [ ] A Next.js 16 project with the base file structure (src/app/, src/components/ui/, src/lib/, public/)
- [ ] `components.json` configured for shadcn/ui
- [ ] Tailwind CSS v4 with oklch-ready globals.css
- [ ] An AI agent with headless browser capability (Claude Code `--chrome`)
- [ ] `/clone-website` skill/command that encodes the 5-phase pipeline as agent instructions
- [ ] `docs/research/` directory for reconnaissance output
- [ ] `docs/research/components/` directory for component specs
- [ ] `public/images/`, `public/videos/`, `public/seo/` directories
- [ ] Git worktree support if running parallel agents
- [ ] `npm run check` script combining lint + typecheck + build

## Gotchas

**`getComputedStyle()` gives px, not rem/em.** The extraction yields pixel values everywhere. When writing Tailwind classes, you need to convert back (e.g., 16px → text-base) or use arbitrary values ([16px]).

**oklch requires Tailwind v4 and a modern browser.** Tailwind v3 doesn't support oklch natively. If your target stack is v3, convert to hex using culori's `formatHex()`.

**External fonts need Next.js `next/font`** or they break on strict CSP headers. Always configure fonts through `next/font/google` rather than `<link>` tags.

**Screenshots differ across headless browsers.** Chrome/Chromium renders antialiasing differently than Firefox. Always use the same browser (Chromium) for both reconnaissance and QA comparison screenshots.

**Worktree merges need manual conflict resolution for shared UI files.** If two agents both modify `src/components/ui/button.tsx` (e.g., to add a custom variant), you'll get a merge conflict. Design section assignments to avoid shared primitive modifications.

**Asset URLs may be relative or CDN-hosted.** Resolve all asset URLs against the page's base URL before downloading. Some sites use protocol-relative URLs (`//cdn.example.com/image.jpg`) that browsers handle silently but `fetch()` won't.

**The target site's terms of service may prohibit cloning.** The template includes an ethics note. Don't clone proprietary commercial designs without permission.

## Origin (reference only)

- Repo: https://github.com/JCodesMore/ai-website-cloner-template
- Key files: `AGENTS.md`, `.claude/skills/clone-website/SKILL.md`, `src/`, `public/`, `docs/`
- Stack: Next.js 16, React 19, TypeScript, Tailwind CSS v4, shadcn/ui
