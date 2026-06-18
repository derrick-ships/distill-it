# HTML→PNG Slide Export (build spec) — distilled from open-carrusel

## Summary

Render HTML/CSS to **pixel-exact PNGs** with headless Chromium (Puppeteer), guaranteeing that a live HTML preview and the exported image are byte-identical because both go through one `wrapSlideHtml()` wrapper and one renderer. Fonts are inlined as base64 `@font-face` and images as data URIs so headless rendering needs zero network. Output is normalized to sRGB via Sharp. Built for fixed output specs (here: Instagram 1080×1080 / 1080×1350 / 1080×1920).

## Core logic (inlined)

### Dimensions + the one wrapper used by BOTH preview and export

```ts
export type AspectRatio = "1:1" | "4:5" | "9:16";
export const DIMENSIONS: Record<AspectRatio, { width: number; height: number }> = {
  "1:1":  { width: 1080, height: 1080 },
  "4:5":  { width: 1080, height: 1350 },
  "9:16": { width: 1080, height: 1920 },
};

// Slides are stored as BODY-LEVEL html (no <html>/<head>).
// `forExport` toggles font inlining vs. Google Fonts CDN link.
export function wrapSlideHtml(
  bodyHtml: string,
  ratio: AspectRatio,
  opts: { forExport: boolean; inlineFontCss?: string; googleFontsHref?: string },
): string {
  const { width, height } = DIMENSIONS[ratio];
  const fontHead = opts.forExport
    ? `<style>${opts.inlineFontCss ?? ""}</style>`         // base64 @font-face
    : `<link rel="stylesheet" href="${opts.googleFontsHref ?? ""}">`; // preview
  return `<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=${width}, height=${height}">
${fontHead}
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  html,body{width:${width}px;height:${height}px;overflow:hidden}
</style></head>
<body>${bodyHtml}</body></html>`;
}

// Pull declared fonts out of the slide html, drop generics.
const GENERIC = new Set(["serif","sans-serif","monospace","cursive","fantasy","system-ui","inherit","initial"]);
export function extractFontFamilies(html: string): string[] {
  const re = /font-family:\s*['"]?([^;'"}\n]+?)['"]?\s*[;}]/g;
  const out = new Set<string>();
  let m: RegExpExecArray | null;
  while ((m = re.exec(html))) {
    for (const fam of m[1].split(",").map(s => s.trim().replace(/['"]/g, "")))
      if (fam && !GENERIC.has(fam.toLowerCase())) out.add(fam);
  }
  return [...out];
}
```

### The export pipeline (Puppeteer + Sharp, concurrency + restart)

```ts
import puppeteer, { Browser } from "puppeteer";
import sharp from "sharp";
import fs from "node:fs/promises";

const MAX_CONCURRENCY = 3;
const MAX_EXPORTS_BEFORE_RESTART = 50;

let browser: Browser | null = null;
let exportCount = 0;

async function getBrowser(): Promise<Browser> {
  if (browser && exportCount >= MAX_EXPORTS_BEFORE_RESTART) {
    await browser.close(); browser = null; exportCount = 0;   // dodge Chromium memory creep
  }
  if (!browser) {
    browser = await puppeteer.launch({
      headless: true,
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"],
    });
  }
  return browser;
}

async function renderSlide(bodyHtml: string, ratio: AspectRatio): Promise<Buffer> {
  const { width, height } = DIMENSIONS[ratio];
  const inlineFontCss = await buildInlineFontFace(extractFontFamilies(bodyHtml)); // base64 @font-face
  const htmlWithImages = await inlineImagesAsDataUris(bodyHtml);                  // data:<mime>;base64,
  const fullHtml = wrapSlideHtml(htmlWithImages, ratio, { forExport: true, inlineFontCss });

  const b = await getBrowser();
  const page = await b.newPage();
  try {
    await page.setViewport({ width, height, deviceScaleFactor: 1 }); // exactly 1080px wide, no DPR upscale
    await page.setContent(fullHtml, { waitUntil: "domcontentloaded", timeout: 15000 });
    try {
      await page.waitForFunction(() => (document as any).fonts.ready.then(() => true), { timeout: 10000 });
    } catch { /* fonts didn't settle — proceed rather than hang */ }
    const shot = (await page.screenshot({ type: "png" })) as Buffer;
    exportCount++;
    return await sharp(shot).toColorspace("srgb").png().toBuffer();        // normalize color
  } finally {
    await page.close();
  }
}

// bounded-concurrency map over slides
export async function exportSlides(
  slides: { id: string; html: string }[], ratio: AspectRatio,
): Promise<{ name: string; buffer: Buffer }[]> {
  const results: { name: string; buffer: Buffer }[] = [];
  let i = 0;
  async function worker() {
    while (i < slides.length) {
      const idx = i++;
      const s = slides[idx];
      results[idx] = { name: `slide-${String(idx + 1).padStart(2, "0")}.png`, buffer: await renderSlide(s.html, ratio) };
    }
  }
  await Promise.all(Array.from({ length: Math.min(MAX_CONCURRENCY, slides.length) }, worker));
  return results;
}
```

### Zipping (separate step — the export fn only returns buffers)

```ts
import JSZip from "jszip"; // or archiver
const zip = new JSZip();
for (const { name, buffer } of await exportSlides(slides, ratio)) zip.file(name, buffer);
const zipBuffer = await zip.generateAsync({ type: "nodebuffer" });
```

## Data contracts

- **Input:** `slides: { id, html /* body-level */ }[]`, `ratio: "1:1" | "4:5" | "9:16"`.
- **Per render:** viewport `{ width, height, deviceScaleFactor: 1 }` from `DIMENSIONS`.
- **Output:** `{ name: string; buffer: Buffer }[]` (PNG, sRGB) → zipped to a single download.
- **Font CSS:** `@font-face { font-family: 'X'; src: url(data:font/woff2;base64,...) }` inlined for export; `<link href="https://fonts.googleapis.com/...">` for preview.

## Dependencies & assumptions

- `puppeteer` (bundles Chromium) or `puppeteer-core` + a Chromium path; `sharp` for color/PNG; `jszip`/`archiver` for the bundle.
- Server runtime that allows headless Chromium (the `--no-sandbox` flags imply a trusted/containerized host).
- Font files available on disk (to base64-inline) or fetchable at build time.
- Swappable: `playwright` instead of puppeteer; skip Sharp if you don't need sRGB normalization; output JPEG/WebP by changing the screenshot/Sharp encode.

## To port this, you need:
- [ ] A non-serverless (or Chromium-capable serverless, e.g. `@sparticuz/chromium`) host.
- [ ] One shared HTML-wrapper function used by *both* your preview and your export — this is what guarantees parity. Do not let preview and export build HTML differently.
- [ ] Font inlining (base64 `@font-face`) and image→data-URI inlining for export.
- [ ] Fixed target dimensions and `deviceScaleFactor: 1` (or your spec's DPR) — don't rely on default viewport.
- [ ] A `document.fonts.ready` wait, time-boxed.
- [ ] A browser singleton with periodic restart and bounded concurrency for batch jobs.

## Gotchas

- **Fonts are the #1 failure.** A font that renders in your dev browser will silently fall back in headless Chromium unless inlined → text reflows, export ≠ preview. Inline base64 `@font-face`; don't trust CDN links at export time.
- **`deviceScaleFactor`:** for an exact-pixel spec (Instagram 1080), render the layout at that CSS width with DPR 1. Cranking DPR resamples and can break the required dimensions.
- **Chromium leaks** on long batches — restart the browser every N renders (50 here) or you'll OOM.
- **`--no-sandbox` is a security trade-off** required to run as a server/container process; only acceptable on a trusted host.
- **`waitUntil: "domcontentloaded"` not `networkidle0`:** because everything is inlined there's no network to idle on; waiting for network would just burn the timeout.
- **Time-box `fonts.ready`** (10s) and proceed on timeout, else one bad font hangs the whole export.
- **Body-level HTML storage** keeps slides composable and forces the single-wrapper discipline — store fragments, wrap at render time.

## Origin (reference only)

- `src/lib/export-slides.ts` — Puppeteer launch, viewport, `fonts.ready` wait, Sharp sRGB, concurrency, browser restart.
- `src/lib/slide-html.ts` — `wrapSlideHtml()`, `extractFontFamilies()`, `DIMENSIONS`, font/image inlining.
- Repo: https://github.com/Hainrixz/open-carrusel
