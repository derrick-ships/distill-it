# Website Cloning Pipeline — from [ai-website-cloner-template](https://github.com/JCodesMore/ai-website-cloner-template)

> Domain: [[_domain]] · Source: https://github.com/JCodesMore/ai-website-cloner-template · NotebookLM:

## What it does

Give this system a URL and it produces a deployable Next.js 16 / React 19 application that looks and behaves like the original website. You don't manually write a single CSS rule or component — the AI does it all by following a structured pipeline of phases. The result is production-grade, typed, and organized.

## Why it exists

Recreating a website by hand is tedious and error-prone: you miss interaction states, get colors slightly off, forget responsive breakpoints. This template industrializes the process. Developers use it to rapidly prototype designs they admire, clients use it to get "a site like X," and teams use it to migrate legacy designs to a modern stack without starting from scratch.

## How it actually works

The pipeline has five phases, invoked via the `/clone-website` slash command inside Claude Code (or any supported AI agent):

**Phase 1 — Reconnaissance**
The agent opens a headless browser and visits the target URL. It takes screenshots at multiple viewport widths (mobile / tablet / desktop) and at interaction states (hover, focus, active, scroll). It reads the page's computed styles using the browser's `getComputedStyle()` API — which returns the *final rendered values* after all cascade, inheritance, and custom-property resolution. It also captures every link and maps the site's section structure. Everything gets stored in `docs/research/`.

**Phase 2 — Foundation**
Before any components are built, the global scaffolding is locked in: Tailwind CSS v4 `globals.css` is rewritten with the extracted color tokens (in oklch format) and typography tokens. Fonts matching the original are configured. All images, videos, and favicon files from the target site are downloaded into `public/images/`, `public/videos/`, and `public/seo/`. This ensures the build phase has real assets to reference, not placeholder text.

**Phase 3 — Component Specifications**
For each identified section or component, the agent writes a detailed spec document in `docs/research/components/`. These specs contain: exact computed CSS values (px sizes, hex/oklch colors, font families and weights), the interaction behavior model (what changes on hover, click, scroll), responsive variants (what shifts at each breakpoint), content variations (primary, secondary, with/without optional fields), and the asset paths the component needs. This is the intelligence layer — it turns raw reconnaissance data into a structured build brief.

**Phase 4 — Parallel Build**
The actual component code is written by one or more AI agents working from the specs. If multiple agents are available, they each get a separate git worktree (an isolated copy of the repo on its own branch) and build different page sections in parallel. Each agent reads its assigned spec and produces a React component using shadcn/ui primitives and Tailwind classes. They never touch the same files, so there are no merge conflicts.

**Phase 5 — Assembly & QA**
All worktree branches are merged back into the main branch. The assembled application is cross-referenced against the original screenshots for visual accuracy. TypeScript compilation (`npm run typecheck`) and ESLint (`npm run lint`) run as a final gate. Any drift from the original is corrected.

## The non-obvious parts

**Computed styles beat source stylesheets.** The agent uses `getComputedStyle()` instead of reading CSS files. This works even when the source site uses a CDN-hosted framework, obfuscated class names, or CSS-in-JS — the browser already resolved everything.

**Specs decouple reconnaissance from construction.** The spec documents act as a stable interface between the "what does it look like" phase and the "build it" phase. This means you can regenerate components without re-running reconnaissance, or hand off specs to a human developer.

**Worktrees prevent race conditions.** When two AI agents build different components concurrently on the same branch, they frequently create conflicts in `components/ui/`, `app/globals.css`, or shared layout files. Worktrees eliminate this entirely.

**AGENTS.md as a single source of truth.** All AI platforms read from one canonical instruction document. A sync script regenerates the platform-specific copies so the behavior stays consistent whether you're using Claude Code, Cursor, Gemini CLI, or any of the other 11+ supported agents.

**Asset downloads happen in Phase 2, not lazily.** If you try to reference an external image URL inside a Next.js app deployed to Vercel, you'll get CORS issues and slow loads. Downloading everything upfront gives you local `public/` paths that work everywhere.

## Related

- [[browser-design-token-extraction--from-ai-website-cloner-template]] — the reconnaissance mechanism
- [[component-spec-generation--from-ai-website-cloner-template]] — Phase 3 in detail
- [[parallel-worktree-build--from-ai-website-cloner-template]] — Phase 4 in detail
- [[multi-platform-agent-sync--from-ai-website-cloner-template]] — how AGENTS.md works across platforms
- [[design-artifact-generation--from-open-design]] (similar pipeline, but for AI-designed mockups rather than cloned sites)
