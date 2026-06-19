# carousel-generator

- **Source:** https://github.com/FranciscoMoretti/carousel-generator
- **Product:** An open-source, account-free web app for creating AI-generated, fully-editable
  **LinkedIn carousels**. Type a topic → get an 8–15 slide draft → edit in a WYSIWYG editor →
  download as a LinkedIn-ready PDF. Themeable, with browser persistence and JSON import/export.
- **Stack:** Next.js 14 (App Router) · React 18 · TypeScript · Tailwind + Radix/shadcn ·
  React Hook Form + Zod · LangChain + OpenAI (`gpt-4o-mini`) · jsPDF + html-to-image + react-to-print ·
  culori (color) · Upstash Redis (rate limit) · Vercel
- **License:** MIT
- **Date distilled:** 2026-06-18

## Architecture in one breath
The entire app is one big **React Hook Form document** validated by a single Zod `DocumentSchema`
(`{ slides, config, filename }`). That one schema is the spine: it shapes the AI's structured output,
gates localStorage persistence, and guards JSON imports. There's no backend database — the document
lives in the browser and in files the user controls. AI generation runs through a server action that
keeps the OpenAI key server-side and (optionally) rate-limits per IP via Upstash. Export works by
*screenshotting the app's own DOM* (html-to-image) and paginating the canvas into a jsPDF — so the
download is pixel-faithful to the editor preview. Theming is DaisyUI-style themes reduced to a small
runtime palette, with contrasting text colors derived in OKLCH.

## Features distilled

| Feature | Domain | Study | Build |
|---|---|---|---|
| AI Carousel Generation (Zod function-call, styled/unstyled split) | content-synthesis | [study](../features/content-synthesis/study/ai-carousel-generation--from-carousel-generator.md) | [build](../features/content-synthesis/build/ai-carousel-generation--from-carousel-generator.md) |
| DOM-to-PDF Carousel Export | rendering | [study](../features/rendering/study/dom-to-pdf-export--from-carousel-generator.md) | [build](../features/rendering/build/dom-to-pdf-export--from-carousel-generator.md) |
| OKLCH Theme Palettes | design-systems | [study](../features/design-systems/study/oklch-theme-palettes--from-carousel-generator.md) | [build](../features/design-systems/build/oklch-theme-palettes--from-carousel-generator.md) |
| Zod Form Persistence & JSON Portability | data-portability | [study](../features/data-portability/study/zod-form-persistence--from-carousel-generator.md) | [build](../features/data-portability/build/zod-form-persistence--from-carousel-generator.md) |
| BYOK + Rate-Limited AI Action | infrastructure | [study](../features/infrastructure/study/byok-rate-limited-action--from-carousel-generator.md) | [build](../features/infrastructure/build/byok-rate-limited-action--from-carousel-generator.md) |

## Source files (reference only — repo may be gone later)
- `src/lib/langchain.ts` — OpenAI function-call generation; `carouselCreator` schema via `zodToJsonSchema`.
- `src/lib/validation/*.tsx` — `DocumentSchema`, `ConfigSchema`, `MultiSlideSchema`, styled/unstyled
  text element schemas (`text-schema.tsx`), `element-type.tsx`, `theme-schema.tsx`.
- `src/app/actions.tsx` — `"use server"` action: key gate → Upstash rate limit → generate.
- `src/lib/rate-limit.ts` — Upstash `slidingWindow(10, "15 m")` limiter.
- `src/lib/hooks/use-component-printer.tsx` — clone-clean → html-to-image → paginated jsPDF export.
- `src/app/api/proxy/route.ts` — edge CORS image proxy (so canvas rasterization isn't tainted).
- `src/lib/hooks/use-persist-form.tsx` — localStorage persist + validate-on-read self-heal.
- `src/lib/hooks/use-fields-file-importer.tsx` — JSON import → schema `.parse()` → `setValue`.
- `src/lib/theme-utils.ts` + `src/lib/pallettes.tsx` + `src/lib/themes.ts` — OKLCH color derivation.
- `src/lib/page-size.tsx` — `SIZE = { width: 400, height: 500 }` (LinkedIn portrait slide).
- `src/lib/hooks/use-keys.tsx` + `src/components/api-keys-dialog.tsx` — client BYOK key.

## Cloneability verdict
Mostly commodity, assembled with taste. The **AI generation** is a textbook forced-function-call
extractor — the one genuinely portable idea is the **styled/unstyled Zod split** (LLM fills content,
app injects styling via `.default()`), which is reusable anywhere you want structured AI output that
drops into a typed form. The **DOM-to-PDF export** is the most distinctive engineering: reusing
`react-to-print`'s clone plumbing to instead run html-to-image → paginated jsPDF, with the careful
clone-cleanup (id-prefix chrome stripping, font re-inlining, CORS image proxy) being the part that's
easy to get wrong — worth copying wholesale. Persistence/portability and the Upstash rate-limit gate
are five-line patterns, valuable as reference more than as code. The OKLCH foreground derivation is a
neat, genuinely reusable color trick. No real moat — an LLM-assisted rebuild of the whole product is
a few days — but several of the individual mechanisms are clean transplant targets.
