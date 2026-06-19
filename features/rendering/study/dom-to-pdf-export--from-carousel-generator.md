# DOM-to-PDF Carousel Export — from [carousel-generator](https://github.com/FranciscoMoretti/carousel-generator)

> Domain: [[_domain]] · Source: https://github.com/FranciscoMoretti/carousel-generator · NotebookLM:

## What it does

Click "Download" and the live, on-screen carousel — the exact React components you've been editing —
becomes a multi-page PDF sized for LinkedIn, one slide per page, ready to upload. What you see in
the editor is what lands in the file, minus all the editing chrome (menus, "add slide" buttons,
selection outlines).

## Why it exists

LinkedIn carousels are uploaded as PDFs (or "documents"). The product is a WYSIWYG editor, so the
export has to be pixel-faithful to the editor preview — users trust that the download matches what
they designed. Rather than maintain a *separate* rendering engine for export (a second source of
truth that would drift from the editor), the app screenshots its own DOM and paginates it. The
job-to-be-done: "give me the file LinkedIn wants, looking exactly like my preview, in one click."

## How it actually works

There are three stages: **clone & clean → rasterize → paginate.**

1. **Clone the live node and strip the editor chrome.** It deep-clones the on-screen container
   (`cloneNode(true)`) so the real UI is never mutated, then walks the clone removing everything
   that's editor-only. Elements are tagged with stable `id` *prefixes* (`add-slide-`,
   `element-menubar-`, `slide-menubar-`, `slide-wrapper-`, `page-base-`, `carousel-item-`...), and
   the cleanup matches by prefix (`[id^=...]`) to: delete add/menu buttons, strip selection-ring
   classes (`ring-2 ring-offset-2 ...`), remove layout padding meant only for the editor, and flip
   the container to a simple vertical stack.

2. **Re-inline fonts the screenshot would otherwise lose.** Tailwind font classes (`font-...`) map
   to CSS variables (`--font-...`) on the page. When you rasterize a detached clone, those computed
   variables don't follow. So it reads the *computed* font-family for each `font-*` class off the
   body and writes it directly onto each `<textarea>`'s inline `style.fontFamily`, guaranteeing the
   right typeface in the image.

3. **Proxy external images through a same-origin endpoint.** Any `<img>` whose `src` isn't local
   (`/...`) or a data URI gets rewritten to `/api/proxy?url=<original>`. That tiny edge route fetches
   the remote image server-side and re-serves it with CORS headers, so the canvas rasterization
   isn't tainted/blocked by cross-origin rules.

4. **Rasterize at 1.8× for crisp output.** `html-to-image`'s `toCanvas` renders the cleaned clone to
   a single tall canvas. Logical size is `400 × (500 × numPages)`; the canvas is captured at 1.8×
   ("scale to LinkedIn intrinsic size") so the PDF isn't soft.

5. **Slice the tall canvas into PDF pages.** `canvasToPdf` computes how many 400×500 pages fit in
   the tall canvas, then for each page draws that horizontal band onto a one-page scratch canvas
   (white background first), encodes it as WebP at 0.98 quality, and `addImage`s it into a jsPDF
   document. The final page is *trimmed* to its real content height so the file isn't padded with
   blank space. `pdf.save(filename)` downloads it.

The whole thing is triggered through `react-to-print`'s lifecycle — but note the twist below.

## The non-obvious parts

- **It hijacks `react-to-print` to do *not* printing but PDF generation.** `useReactToPrint` is used
  for its clone/lifecycle plumbing (`content`, `onBeforePrint`, `removeAfterPrint`), but the actual
  `print:` callback ignores the print dialog and instead grabs the iframe's document, finds
  `#element-to-download-as-pdf`, and runs the html-to-image → jsPDF pipeline. Clever reuse of an
  off-the-shelf hook's machinery for a different end.
- **Editor chrome is removed by `id`-prefix convention, not by component logic.** Because every
  removable element carries a known prefix, export cleanup is a handful of generic
  `querySelectorAll('[id^=prefix]')` passes — decoupled from the components themselves.
- **The CORS image proxy exists *only* so canvas rasterization works.** Cross-origin images taint a
  canvas and make `toDataURL` throw; routing them same-origin is the workaround.
- **Final-page trimming** is a deliberate file-size optimization — without it every carousel's last
  page would carry blank padding.
- **WebP at 0.98** balances near-lossless quality against PDF weight (vs PNG's bulk).
- **The 1.8× "LinkedIn intrinsic size" factor** is a magic number tying the on-screen 400×500 design
  to LinkedIn's actual document resolution so the upload looks sharp.

## Related

- [[byok-rate-limited-action--from-carousel-generator]] — same repo; the `/api/proxy` route used here is sibling plumbing
- [[oklch-theme-palettes--from-carousel-generator]] — the colors being faithfully rasterized come from this theme system
- [[hand-drawn-rendering--from-excalidraw]] — another "data model → pixels" rendering pipeline, but canvas-native rather than DOM-screenshot
- See also: any "export this React view as PDF/PNG" feature — html-to-image + jsPDF is the canonical stack
