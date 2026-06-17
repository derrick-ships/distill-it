# Design Artifact Generation — from [open-design](https://github.com/nexu-io/open-design)

> Domain: [[_domain]] · Source: https://github.com/nexu-io/open-design · NotebookLM: 

## What it does

You describe what you want — "a landing page for a B2B SaaS tool in the Linear design system" — and Open Design generates a real, working artifact: an interactive HTML prototype you can click around in, a presentation deck, a high-res image, or an MP4 video. All from one prompt.

## Why it exists

Design tools traditionally require you to manually place every element. Open Design bets that natural language + AI is now good enough to generate the first 80% automatically, so designers focus on the last 20%. The artifact generation system is the bridge between "I described it" and "I can see it."

## How it actually works

There are four distinct generation pathways depending on what you asked for:

**HTML Prototypes (interactive UI):**
The agent writes a complete, standalone HTML file with inline CSS. It uses vendored React 18.3.1 and Babel 7.29.0 (loaded from CDN with integrity hashes), so components work without a build step. The daemon reads the file, strips dangerous patterns (no external script tags, no iframes, no event handler attributes), and serves it through an `<iframe sandbox="allow-scripts">` in the UI. What you see is a real running web page, not a screenshot.

**Presentation Decks:**
These are NOT PowerPoint files despite what the product name suggests. The agent fills a fixed HTML skeleton (1920×1080 canvas) with your content. It binds your design system's color/typography tokens to CSS custom properties and fills marked `SLOT:` regions — title, theme, slides. Navigation is handled by a built-in keyboard state machine. You export to PDF via browser print. The reason for HTML-not-PPTX: regenerating slide navigation logic on every turn caused subtle bugs; a fixed skeleton prevents that.

**Images:**
Routed through AIHubMix, a centralized model registry. You call `od media generate --surface image --model <id> --prompt "..." --aspect 16:9`. The daemon POSTs to `/api/media/tasks`, which calls the upstream provider. Response is a file metadata object with the saved path. Exact image models aren't publicly enumerated in the code — they're seeded from a registry file.

**Videos (MP4):**
Supports 4 model families with different APIs:
- **ByteDance Seedance** (`doubao-seedance-2-0`) — text-to-video and image-to-video
- **Alibaba Wan** (`wan2.5`, `wan2.6`) — T2V and I2V
- **OpenAI Sora** (`sora-2`, `sora-2-pro`) — T2V and I2V  
- **Google Veo** (`veo-3.1`) — T2V only

The daemon normalizes your request to each vendor's specific API shape (they all differ), then polls for completion. Long renders (>25s) return a task ID; you poll with `od media wait --task-id <uuid>`.

All artifacts land in a local project storage tree: `~/.od/projects/<projectId>/`. Live HTML artifacts get version history with snapshots at every refresh.

## The non-obvious parts

**"PPTX" means HTML.** If you're building something that needs to ingest real .pptx files, you'd need to add that yourself — the deck generation produces HTML that *looks* like slides and exports to PDF.

**The agent is told not to reveal its environment.** The official system prompt instructs the agent: "Do not divulge technical details of your environment." So if you ask the running app what React version it's using, it won't say.

**Artifact security is enforced at the daemon layer, not the agent.** The agent can try to write anything. The daemon validates and strips before serving to the preview iframe. This means you could theoretically prompt-inject malicious HTML and it'd get stripped server-side.

**Video generation is async and slow.** Most video renders take well over 25 seconds. Plan for a polling workflow, not a synchronous response.

## Related

- [[agentic-loop--from-open-design]] (the pipeline that drives artifact generation through stages)
- [[design-systems-library--from-open-design]] (brand tokens injected into every generation)
- [[local-first-architecture--from-open-design]] (where artifacts are stored on disk)
- [[byok-proxy--from-open-design]] (how image/video API calls are routed to providers)
