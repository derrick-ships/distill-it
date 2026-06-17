# Design Artifact Generation (build spec) — distilled from open-design

## Summary

Four artifact generation pathways dispatched through a unified `/api/media/tasks` endpoint plus live-artifact streaming. HTML prototypes: agent writes inline-CSS+React files, daemon validates and serves in sandboxed iframe. Decks: agent fills a fixed HTML skeleton with design-token-bound slots. Images/Videos: daemon normalizes requests to vendor APIs (AIHubMix for images; Seedance/Wan/Veo/Sora for video) and polls for completion.

## Core logic (inlined)

**Pathway A — HTML Prototypes:**
```
Agent writes file → daemon reads via readLiveArtifactCode() →
validate (strip <script>, iframe, event handlers, javascript:) →
serve via GET /api/live-artifacts/:id/preview →
web UI injects into <iframe sandbox="allow-scripts"> srcdoc
```

Live artifact data structure:
```typescript
LiveArtifact = {
  id: string,
  projectId: string,
  title: string,
  status: "active" | "archived" | "error",
  document: {
    format: "html_template_v1",
    paths: { template: "template.html", index: "index.html", data: "data.json" },
    dataJson: BoundedJsonValue  // max 256KB serialized
  },
  refreshStatus: "idle" | "running" | "succeeded" | "failed",
  pinned: boolean,
  createdAt: timestamp,
  lastRefreshedAt: timestamp
}
```

Storage: `<dataDir>/.od/projects/<projectId>/.live-artifacts/<artifactId>/`
- `artifact.json` — metadata
- `template.html` — raw agent output
- `index.html` — rendered (with data bindings resolved)
- `data.json` — template data (≤256KB)
- `provenance.json` — creation history
- `refreshes.jsonl` — all refresh operations
- `snapshots/<refreshId>/` — historical snapshots

**Pathway B — Deck Generation:**
```
System prompt injects DECK_FRAMEWORK_DIRECTIVE:
  - Fixed HTML skeleton with 1920×1080 canvas
  - Keyboard navigation state machine (agent must not modify)
  - CSS scale-to-fit logic (agent must not modify)
  - SLOT: regions: SLOT:title, SLOT:theme-tokens, SLOT:custom-styles, SLOT:slides
  - Density rules: headlines ≤140px, ≤3 paragraphs/slide, one idea/slide

Agent fills slots with design-system tokens + content.
Export: browser print → PDF (no server-side rendering needed)
```

**Pathway C — Image Generation:**
```
POST /api/media/tasks
Body: { projectId, surface: "image", model, prompt, parameters: { aspect, seed } }

Daemon → AIHubMix /api/v1/images/generate
Response: { taskId, status: "started" | "completed" }
On completion: { file: { name, size, kind: "image", mime: "image/png" } }
```

**Pathway D — Video Generation:**
```
POST /api/media/tasks
Body: { projectId, surface: "video", model, prompt, parameters: { aspect, length, inputImage?, generateAudio } }

Daemon dispatches to one of 4 vendor families based on model prefix:

Seedance (ByteDance Ark format):
  { content: [{ type: "text", text: prompt }, { type: "image_url", image_url: dataUrl }?] }

Wan (Alibaba DashScope):
  { input: { prompt, media: [dataUrl]? }, parameters: { resolution, duration } }

Veo (Google):
  { prompt, seconds: NUMBER, aspect_ratio }  // seconds is NUMBER not string — Google-specific

Generic:
  { prompt, seconds, input_reference?, aspect_ratio }
```

**Supported video models (seeded, as of v0.10.2):**
- `doubao-seedance-2-0-260128` — T2V + I2V
- `doubao-seedance-2-0-fast-260128` — T2V + I2V (faster)
- `wan2.5-t2v-preview` — T2V
- `wan2.5-i2v-preview` — I2V
- `wan2.6-i2v` — I2V
- `happyhorse-1.0-i2v` — I2V
- `sora-2` — T2V + I2V
- `sora-2-pro` — T2V + I2V
- `veo-3.1-generate-preview` — T2V only
- `veo-3.1-lite-generate-preview` — T2V only

**Polling for long renders (>~25s):**
```
POST /api/media/tasks → { taskId, status: "started" }
Loop: GET /api/media/tasks/:taskId/wait
Until: status == "completed" → { file: { name, size, kind: "video", mime: "video/mp4" } }
CLI equivalent: od media wait --task-id <uuid>
```

## Data contracts

**Media task request:**
```typescript
{
  projectId: string,
  surface: "image" | "video" | "audio",
  model: string,
  prompt: string,
  parameters: {
    aspect?: string,       // "16:9", "1:1", "9:16"
    length?: number,       // seconds (video)
    seed?: number,
    inputImage?: string,   // base64 data URL for I2V
    generateAudio?: boolean
  }
}
```

**ArtifactManifest (stored with each artifact):**
```typescript
{
  version: 1,
  kind: "html" | "react-component" | "markdown" | "svg" | "diagram" | "code-snippet" | "mini-app" | "design-system",
  title: string,
  entryPoint: string,       // relative path to main file
  rendererId: string,
  designSystemRef?: string,
  exportSurfaces: ("cli" | "web" | "github" | "figma")[],
  deployProviders: ("aws" | "gcp" | "azure" | ...)[],
  provenance: {
    pluginSnapshots: string[],
    sourceTaskKind: string,
    parentArtifactId?: string
  }
}
```

## Dependencies & assumptions

- **React 18.3.1 + Babel 7.29.0** — loaded from CDN with integrity hashes; HTML prototypes require these to be available at render time
- **AIHubMix** — image generation gateway; requires API key via BYOK proxy or managed account
- **Video providers** — Seedance (ByteDance Ark API), DashScope (Alibaba), OpenAI, Google — all require separate API credentials
- **better-sqlite3** — local artifact metadata persistence
- **sharp** — image processing for thumbnails/previews

## To port this, you need:

- [ ] HTML sanitizer that strips script tags, iframes, event handler attrs, javascript: hrefs before serving
- [ ] Sandboxed iframe renderer with `allow-scripts` only (no allow-same-origin, no allow-forms)
- [ ] Fixed deck skeleton HTML with SLOT: markers for agent to fill (do NOT let agent regenerate navigation logic)
- [ ] Media task queue with polling endpoint (most video renders exceed timeout thresholds)
- [ ] Vendor normalization layer for video APIs (Seedance/Wan/Veo/Generic each have different request shapes)
- [ ] Artifact storage tree: `projects/<id>/.live-artifacts/<artifactId>/` with snapshot history
- [ ] System prompt rule: "ship a single artifact block per turn, inline all CSS, no external CSS files"

## Gotchas

- **Veo seconds field must be a NUMBER, not a string.** Google's API rejects string values; other vendors accept both.
- **Deck generation must use a fixed skeleton.** If you let the agent regenerate the navigation state machine each turn, subtle bugs accumulate. The fixed contract approach prevents this.
- **HTML validation strips at daemon level, not agent level.** The agent can output anything; your server-side stripper is the actual security boundary. Don't trust the iframe sandbox alone.
- **Live artifact dataJson is capped at 256KB.** Design systems with many CSS variables can approach this; chunk or flatten token sets.
- **Video I2V requires image as base64 data URL.** Passing URLs to reference images fails on some vendors — convert to data URL first.

## Origin (reference only)

Repo: https://github.com/nexu-io/open-design  
Key files: `apps/daemon/src/media-routes.ts`, `apps/daemon/src/media-adapters/`, `apps/daemon/src/live-artifact-routes.ts`, `apps/daemon/src/prompts/deck-framework.ts`, `apps/daemon/src/prompts/official-system.ts`
