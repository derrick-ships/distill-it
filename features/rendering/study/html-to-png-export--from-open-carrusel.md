# HTML→PNG Slide Export — from [open-carrusel](https://github.com/Hainrixz/open-carrusel)

> Domain: [[_domain]] · Source: https://github.com/Hainrixz/open-carrusel · NotebookLM: <link once added>

## What it does

Slides in Open Carrusel are just HTML/CSS. When you hit "export," each slide is rendered by a headless Chromium (Puppeteer) at the exact Instagram pixel size, screenshotted to PNG, color-corrected, and bundled into a ZIP you can drag straight into Instagram. The promise printed in the docs: *"what you see is exactly what you export. No surprises."*

## Why it exists

Instagram is pixel-fussy: a carousel slide must be exactly 1080×1080 (square), 1080×1350 (4:5 portrait), or 1080×1920 (9:16). A design tool that exports "close enough" produces blurry or cropped posts. By making the *same HTML* that renders in the live preview iframe also be the thing Chromium screenshots, the app guarantees the preview and the export are byte-identical layouts. The browser is the renderer in both cases, so there's no second rendering engine to disagree.

## How it actually works

1. **One HTML contract, two consumers.** Slides are stored as *body-level* HTML (no `<html>`/`<head>` wrapper). A single function, `wrapSlideHtml()`, wraps that fragment into a full document — used for both the preview iframe and the export. Same wrapper = same pixels.

2. **Fonts are made self-contained for export.** The wrapper scans the slide HTML for `font-family` declarations (regex), throws away the generic keywords (`serif`, `sans-serif`, etc.), and for export *inlines* the real font files as base64 `@font-face` rules. (For preview it just links Google Fonts.) This is critical: headless Chromium has no network guarantee and no system fonts, so an un-inlined font would silently fall back and shift the layout.

3. **Images become data URIs.** Any image path in the slide is read off disk and embedded as `data:<mime>;base64,...`, so the rendered page needs zero external fetches.

4. **Render at exact size.** Puppeteer launches headless with `--no-sandbox --disable-setuid-sandbox --disable-gpu`. The viewport is set to the aspect ratio's exact width/height with `deviceScaleFactor: 1` — no retina upscaling, the page *is* 1080px wide. Content loads with `waitUntil: "domcontentloaded"`, then it waits for `document.fonts.ready` (up to 10s) so text is laid out in the right font before the shot. If fonts time out, it proceeds anyway rather than hang.

5. **Screenshot → Sharp → PNG.** The screenshot buffer is passed through Sharp, forced to the **sRGB** colorspace, and re-encoded as PNG. sRGB normalization keeps colors consistent across machines/monitors.

6. **Throughput without leaks.** Up to **3 slides render concurrently**. The browser instance is **restarted every 50 exports** to dodge Chromium's well-known memory creep. The pipeline returns an array of `{ name, buffer }`; a separate step zips them.

## The non-obvious parts

- **Preview/export parity is the entire value prop**, and it's achieved structurally — one `wrapSlideHtml()`, one renderer (Chromium) — not by trying to match two engines.
- **Font inlining is non-negotiable for headless.** The single most common "export looks wrong" bug is a font that loaded in your browser preview but not in headless Chromium. Inlining base64 `@font-face` removes the network and system-font variables entirely.
- **`deviceScaleFactor: 1` is deliberate.** People instinctively crank DPR for "quality," but Instagram wants exactly 1080px; rendering the layout *at* 1080 CSS px with DPR 1 gives a clean 1080px PNG with no resampling.
- **`document.fonts.ready` gate prevents flash-of-fallback-font** baked into the screenshot — but it's time-boxed so a missing font can't deadlock the export.
- **Browser restart every N renders** is a quiet but important reliability trick: long-lived headless Chromium leaks, and a batch export of many carousels would OOM without it.
- **Sandbox flags** (`--no-sandbox`) are needed to run Chromium as a server process / in containers, with the usual security caveat.

## Related

- [[cli-subprocess-agent--from-open-carrusel]] (the agent that authors the slide HTML this pipeline renders)
- [[hand-drawn-rendering--from-excalidraw]] (another "HTML/canvas is the source of truth for an image" rendering approach)
- See also: any static-site OG-image generator — same headless-screenshot pattern, different output spec.
