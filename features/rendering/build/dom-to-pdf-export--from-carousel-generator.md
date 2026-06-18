# DOM-to-PDF Export (build spec) — distilled from carousel-generator

## Summary
Export a live React/DOM view as a multi-page PDF that matches the on-screen preview pixel-for-pixel.
Pipeline: **deep-clone the node → strip editor-only chrome by `id`-prefix → re-inline fonts →
proxy cross-origin images same-origin → `html-to-image` rasterize a tall canvas at scale →
slice the canvas into fixed-size pages and `addImage` each into jsPDF**. Uses `react-to-print`
purely for its clone/lifecycle plumbing; the `print` callback runs the canvas→PDF logic instead of
opening the print dialog.

## Core logic (inlined)

Full hook from `src/lib/hooks/use-component-printer.tsx` (key parts verbatim):

```tsx
import React from "react";
import { useReactToPrint } from "react-to-print";
import { SIZE } from "@/lib/page-size";              // { width: 400, height: 500 }
import { useFieldArrayValues } from "@/lib/hooks/use-field-array-values";
import { useFormContext } from "react-hook-form";
import { toCanvas } from "html-to-image";
import { Options as HtmlToImageOptions } from "html-to-image/lib/types";
import { jsPDF, jsPDFOptions } from "jspdf";

type HtmlToPdfOptions = {
  margin: [number, number, number, number];
  filename: string;
  image: { type: string; quality: number };
  htmlToImage: HtmlToImageOptions;
  jsPDF: jsPDFOptions;
};

export const toPx = (val: number, k: number) => Math.floor(((val * k) / 72) * 96);

function getPdfPageSize(opt: HtmlToPdfOptions) {
  // @ts-ignore  jsPDF.getPageSize is not officially exported
  const pageSize = jsPDF.getPageSize(opt.jsPDF);
  if (!pageSize.hasOwnProperty("inner")) {
    pageSize.inner = {
      width:  pageSize.width  - opt.margin[1] - opt.margin[3],
      height: pageSize.height - opt.margin[0] - opt.margin[2],
    };
    pageSize.inner.px = {
      width:  toPx(pageSize.inner.width,  pageSize.k),
      height: toPx(pageSize.inner.height, pageSize.k),
    };
    pageSize.inner.ratio = pageSize.inner.height / pageSize.inner.width;
  }
  return pageSize;
}

function canvasToPdf(canvas: HTMLCanvasElement, opt: HtmlToPdfOptions) {
  const pdfPageSize = getPdfPageSize(opt);
  const pxFullHeight = canvas.height;
  const pxPageHeight = Math.floor(canvas.width * pdfPageSize.inner.ratio);
  const nPages = Math.ceil(pxFullHeight / pxPageHeight);
  let pageHeight = pdfPageSize.inner.height;

  const pageCanvas = document.createElement("canvas");
  const pageCtx = pageCanvas.getContext("2d");
  if (!pageCtx) throw Error("Canvas context of created element not found");
  pageCanvas.width = canvas.width;
  pageCanvas.height = pxPageHeight;

  const pdf = new jsPDF(opt.jsPDF);
  for (let page = 0; page < nPages; page++) {
    if (page === nPages - 1 && pxFullHeight % pxPageHeight !== 0) {   // trim last page
      pageCanvas.height = pxFullHeight % pxPageHeight;
      pageHeight = (pageCanvas.height * pdfPageSize.inner.width) / pageCanvas.width;
    }
    const w = pageCanvas.width, h = pageCanvas.height;
    pageCtx.fillStyle = "white";
    pageCtx.fillRect(0, 0, w, h);
    pageCtx.drawImage(canvas, 0, page * pxPageHeight, w, h, 0, 0, w, h);
    if (page) pdf.addPage();
    const imgData = pageCanvas.toDataURL("image/" + opt.image.type, opt.image.quality);
    pdf.addImage(imgData, opt.image.type, opt.margin[1], opt.margin[0],
                 pdfPageSize.inner.width, pageHeight);
  }
  return pdf;
}

export function useComponentPrinter() {
  const { numPages } = useFieldArrayValues("slides");
  const { watch } = useFormContext();
  const [isPrinting, setIsPrinting] = React.useState(false);
  const componentRef = React.useRef(null);

  const reactToPrintContent = React.useCallback(() => {
    const current = componentRef.current;
    if (current && typeof current === "object") {
      // @ts-ignore
      const clone = current.cloneNode(true);
      proxyImgSources(clone);
      removeSelectionStyleById(clone, "page-base-");
      removeSelectionStyleById(clone, "content-image-");
      removePaddingStyleById(clone, "carousel-item-");
      removeStyleById(clone, "slide-wrapper-", "px-2");
      removeAllById(clone, "add-slide-");
      removeAllById(clone, "add-element-");
      removeAllById(clone, "element-menubar-");
      removeAllById(clone, "slide-menubar-");
      insertFonts(clone);
      clone.className = "flex flex-col";
      clone.style = {};
      return clone;
    }
    return componentRef.current;
  }, []);

  const handlePrint = useReactToPrint({
    content: reactToPrintContent,
    removeAfterPrint: true,
    onBeforePrint: () => setIsPrinting(true),
    onAfterPrint:  () => setIsPrinting(false),
    pageStyle: `@page { size: ${SIZE.width}px ${SIZE.height}px;  margin: 0; } @media print { body { -webkit-print-color-adjust: exact; }}`,
    print: async (printIframe) => {
      const contentDocument = printIframe.contentDocument;
      if (!contentDocument) return;
      const html = contentDocument.getElementById("element-to-download-as-pdf");
      if (!html) return;

      const SCALE_TO_LINKEDIN_INTRINSIC_SIZE = 1.8;
      const options: HtmlToPdfOptions = {
        margin: [0, 0, 0, 0],
        filename: watch("filename"),
        image: { type: "webp", quality: 0.98 },
        htmlToImage: {
          height: SIZE.height * numPages,
          width:  SIZE.width,
          canvasHeight: SIZE.height * numPages * SCALE_TO_LINKEDIN_INTRINSIC_SIZE,
          canvasWidth:  SIZE.width  * SCALE_TO_LINKEDIN_INTRINSIC_SIZE,
        },
        jsPDF: { unit: "px", format: [SIZE.width, SIZE.height] },
      };
      const canvas = await toCanvas(html, options.htmlToImage).catch(console.error);
      if (!canvas) return;
      const pdf = canvasToPdf(canvas, options);
      pdf.save(options.filename);
    },
  });

  return { componentRef, handlePrint, isPrinting };
}
```

Clone-cleanup helpers (all match by `id` prefix):

```tsx
function proxyImgSources(html: HTMLElement) {           // route cross-origin imgs same-origin
  const images = Array.from(html.getElementsByTagName("img")) as HTMLImageElement[];
  const url = process.env.NEXT_PUBLIC_APP_URL;
  images.filter(i => !i.src.startsWith("/") && !i.src.startsWith("data:"))
        .forEach(image => {
          const u = new URL(`${url}/api/proxy`);
          u.searchParams.set("url", image.src);
          image.src = u.toString();
        });
}
function removeAllById(html: HTMLElement, id: string) {
  (Array.from(html.querySelectorAll(`[id^=${id}]`)) as HTMLElement[]).forEach(e => e.remove());
}
function removeStyleById(html: HTMLElement, id: string, classNames: string) {
  (Array.from(html.querySelectorAll(`[id^=${id}]`)) as HTMLElement[]).forEach(e => {
    e.className = e.className.split(" ")
      .filter(cn => !classNames.split(" ").includes(cn)).join(" ");
  });
}
const removePaddingStyleById   = (h,id) => removeStyleById(h, id, "pl-2 md:pl-4");
const removeSelectionStyleById = (h,id) => removeStyleById(h, id, "outline-input ring-2 ring-offset-2 ring-ring");

function insertFonts(element: HTMLElement) {            // re-inline Tailwind font vars onto textareas
  (Array.from(element.getElementsByTagName("textarea")) as HTMLTextAreaElement[]).forEach(el => {
    el.className.split(" ").filter(cn => cn.startsWith("font-")).forEach(font => {
      const fontFaceValue = getComputedStyle(el.ownerDocument.body).getPropertyValue("--" + font);
      if (fontFaceValue) el.style.fontFamily = fontFaceValue;
    });
  });
}
```

The CORS proxy it depends on, `src/app/api/proxy/route.ts` (edge runtime):

```ts
export const runtime = "edge";
export async function GET(request: NextRequest) {
  const imageUrl = new URL(request.url).searchParams.get("url");
  if (!imageUrl) return new NextResponse("URL Not provided", { status: 500 });
  const resp = await fetch(imageUrl);
  const contentType = resp.headers.get("Content-Type");
  if (!contentType?.startsWith("image"))
    return new NextResponse("Content type must be image", { status: 500 });
  const headers = new Headers();
  headers.set("Access-Control-Allow-Origin", process.env.NEXT_PUBLIC_APP_URL || "");
  headers.set("Content-Type", contentType);
  return new NextResponse(resp.body, { status: 200, headers });
}
```

## Data contracts
- `SIZE = { width: 400, height: 500 }` — one slide in CSS px (LinkedIn portrait ratio).
- `numPages` = slide count (from the form's `slides` field array).
- Tall canvas logical size: `width=400`, `height=500*numPages`; captured at `canvasWidth/Height ×1.8`.
- jsPDF: `{ unit: "px", format: [400, 500] }`, one image per page, WebP `quality 0.98`, margins `[0,0,0,0]`.
- The exported root DOM node must have `id="element-to-download-as-pdf"`; `componentRef` is attached
  to the printable container; removable chrome carries `id` prefixes listed above.

## Dependencies & assumptions
- `react-to-print`, `html-to-image`, `jspdf`, `react-hook-form` (for `watch("filename")` + field array).
- Next.js (the same-origin `/api/proxy` edge route). `NEXT_PUBLIC_APP_URL` must be set for image proxying.
- Tailwind font-family CSS variables named `--font-*`, applied via `font-*` utility classes.
- Swappable: drop `react-to-print` and call the clone+rasterize+paginate directly off a ref; the
  print-hook is only there for clone/lifecycle convenience.

## To port this, you need:
- [ ] A single DOM subtree representing the full document (stacked pages), with a known root id.
- [ ] `id`-prefix tagging on every editor-only element so cleanup is generic `[id^=]` passes.
- [ ] A same-origin image proxy if you render remote images (else canvas taint blocks `toDataURL`).
- [ ] Font handling: inline computed font-family if you use CSS-variable-based fonts (detached clones lose them).
- [ ] Fixed per-page pixel dimensions + a capture scale factor for your target resolution.

## Gotchas
- **Canvas taint:** any cross-origin `<img>` without proper CORS makes `toDataURL` throw — the
  `/api/proxy` same-origin reserve is mandatory, not optional.
- **Detached-clone CSS loss:** custom properties / `@font-face` set on `<head>`/`body` don't travel
  with a cloned node into html-to-image — re-inline them (the `insertFonts` step).
- `jsPDF.getPageSize` is `@ts-ignore`d (not in the public types) — version-fragile.
- Last-page trimming is essential; skip it and every export carries blank trailing space.
- `-webkit-print-color-adjust: exact` in `pageStyle` keeps backgrounds from being dropped.
- Big carousels = a very tall canvas at 1.8×; watch browser max-canvas-size limits on huge docs.

## Origin (reference only)
`src/lib/hooks/use-component-printer.tsx` (entire pipeline), `src/lib/page-size.tsx` (SIZE),
`src/app/api/proxy/route.ts` (CORS image proxy). Triggered from the editor menubar download button.
