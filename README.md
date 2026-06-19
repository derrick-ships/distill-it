```
  ██████╗ ██╗███████╗████████╗██╗██╗      ██╗      ██╗████████╗
  ██╔══██╗██║██╔════╝╚══██╔══╝██║██║      ██║      ██║╚══██╔══╝
  ██║  ██║██║███████╗   ██║   ██║██║      ██║█████╗██║   ██║
  ██║  ██║██║╚════██║   ██║   ██║██║      ██║╚════╝██║   ██║
  ██████╔╝██║███████║   ██║   ██║███████╗ ███████╗ ██║   ██║
  ╚═════╝ ╚═╝╚══════╝   ╚═╝   ╚═╝╚══════╝ ╚══════╝ ╚═╝   ╚═╝
```

> **Point Claude at any GitHub repo. Get back structured knowledge you can actually reuse.**

![175 nodes](https://img.shields.io/badge/nodes-175-4299e1?style=flat-square)
![58 domains](https://img.shields.io/badge/domains-58-9f7aea?style=flat-square)
![34 repos](https://img.shields.io/badge/repos-34-68d391?style=flat-square)
![built by Claude](https://img.shields.io/badge/built%20by-Claude-f6ad55?style=flat-square)

---

## What this is

A knowledge base where **Claude does the reading, I just pick the repos**.

Give Claude a GitHub URL and it reads the codebase over the web, traces each feature
end-to-end, and writes two documents per feature:

| Layer | Audience | Purpose |
|-------|----------|---------|
| **Study doc** | You | Plain-language deep-dive, ready to upload to NotebookLM |
| **Build spec** | Claude (future sessions) | Self-contained technical guide for reimplementing the feature in any new project |

Everything feeds into an interactive knowledge graph you can browse and search.

---

## Browse the graph

Open [`graph/graph.html`](graph/graph.html) in a browser.

Click any node → see the summary, links to the study doc, build spec, and origin repo.

---

## What's inside

| Domain | Feature | From |
|--------|---------|------|
| realtime | Debounced File Watcher | [hazelnut](https://github.com/ricardodantas/hazelnut) |
| pipeline-orchestration | File Rules Engine | [hazelnut](https://github.com/ricardodantas/hazelnut) |
| pipeline-orchestration | File Actions Executor | [hazelnut](https://github.com/ricardodantas/hazelnut) |
| data-structures | MBQL — Metabase Query AST | [metabase](https://github.com/metabase/metabase) |
| pipeline-orchestration | Query Processor Middleware Pipeline | [metabase](https://github.com/metabase/metabase) |
| plugin-architecture | Multimethod Driver Abstraction | [metabase](https://github.com/metabase/metabase) |
| rendering | Visualization Auto-Selection | [metabase](https://github.com/metabase/metabase) |
| pipeline-orchestration | Declarative (Low-Code) CDK | [airbyte](https://github.com/airbytehq/airbyte) |
| data-portability | Airbyte Protocol | [airbyte](https://github.com/airbytehq/airbyte) |
| pipeline-orchestration | Incremental Sync & State | [airbyte](https://github.com/airbytehq/airbyte) |
| web-extraction | Declarative HTTP Stream Stack | [airbyte](https://github.com/airbytehq/airbyte) |
| code-generation | Connector Builder Test-Read | [airbyte](https://github.com/airbytehq/airbyte) |
| web-extraction | Site URL Map | [firecrawl](https://github.com/firecrawl/firecrawl) |
| web-extraction | Agentic Browser Actions | [firecrawl](https://github.com/firecrawl/firecrawl) |
| research-automation | Deep Research Loop | [firecrawl](https://github.com/firecrawl/firecrawl) |
| content-synthesis | Generate llms.txt | [firecrawl](https://github.com/firecrawl/firecrawl) |
| payments | Credit Billing & Concurrency | [firecrawl](https://github.com/firecrawl/firecrawl) |
| credential-management | Keyless & x402 Access | [firecrawl](https://github.com/firecrawl/firecrawl) |
| web-extraction | Scrape Engine + Fallback Pipeline | [firecrawl](https://github.com/firecrawl/firecrawl) |
| pipeline-orchestration | Queue-Backed Crawl | [firecrawl](https://github.com/firecrawl/firecrawl) |
| structured-extraction | LLM Extract (map-reduce) | [firecrawl](https://github.com/firecrawl/firecrawl) |
| web-extraction | Web Search (+ scrape) | [firecrawl](https://github.com/firecrawl/firecrawl) |
| ai-integration | Citation-Grounded Chat | [openpaper](https://github.com/khoj-ai/openpaper) |
| content-preprocessing | PDF Ingestion Pipeline | [openpaper](https://github.com/khoj-ai/openpaper) |
| canvas-interaction | PDF Highlights & Annotations | [openpaper](https://github.com/khoj-ai/openpaper) |
| web-extraction | Corpus & Academic Search | [openpaper](https://github.com/khoj-ai/openpaper) |
| tts | Audio Overview (TTS) | [openpaper](https://github.com/khoj-ai/openpaper) |
| credential-management | Multi-Path Authentication | [openpaper](https://github.com/khoj-ai/openpaper) |
| adaptive-parsing | Adaptive Element Relocation | [Scrapling](https://github.com/D4Vinci/Scrapling) |
| document-conversion | Converter Pipeline | [markitdown](https://github.com/microsoft/markitdown) |
| document-conversion | PDF Conversion | [markitdown](https://github.com/microsoft/markitdown) |
| document-conversion | Office Doc Conversion | [markitdown](https://github.com/microsoft/markitdown) |
| document-conversion | ZIP Archive Traversal | [markitdown](https://github.com/microsoft/markitdown) |
| plugin-architecture | Plugin System | [markitdown](https://github.com/microsoft/markitdown) |
| file-detection | Magika File Detection | [markitdown](https://github.com/microsoft/markitdown) |
| media-processing | Image + LLM Captioning | [markitdown](https://github.com/microsoft/markitdown) |
| media-processing | Audio Transcription | [markitdown](https://github.com/microsoft/markitdown) |
| web-extraction | HTML Web Conversion | [markitdown](https://github.com/microsoft/markitdown) |
| web-extraction | YouTube Extraction | [markitdown](https://github.com/microsoft/markitdown) |
| ai-integration | Azure Doc Intelligence | [markitdown](https://github.com/microsoft/markitdown) |
| agent-architecture | Agent Output Contract | [last30days-skill](https://github.com/mvanhorn/last30days-skill) |
| research-automation | Multi-Source Research Engine | [last30days-skill](https://github.com/mvanhorn/last30days-skill) |
| research-automation | Entity Resolution | [last30days-skill](https://github.com/mvanhorn/last30days-skill) |
| research-automation | Engagement Signal Ranking | [last30days-skill](https://github.com/mvanhorn/last30days-skill) |
| content-synthesis | Cross-Source Clustering | [last30days-skill](https://github.com/mvanhorn/last30days-skill) |
| credential-management | Multi-Tier Credentials | [last30days-skill](https://github.com/mvanhorn/last30days-skill) |
| ai-automation | AI Rules Engine | [inbox-zero](https://github.com/elie222/inbox-zero) |
| ai-automation | AI Reply Drafting | [inbox-zero](https://github.com/elie222/inbox-zero) |
| inbox-cleanup | Bulk Unsubscriber | [inbox-zero](https://github.com/elie222/inbox-zero) |
| inbox-cleanup | Bulk Archiver | [inbox-zero](https://github.com/elie222/inbox-zero) |
| email-platform | Email Provider Abstraction | [inbox-zero](https://github.com/elie222/inbox-zero) |
| agent-architecture | Ordered Backend Routing | [Agent-Reach](https://github.com/Panniantong/Agent-Reach) |
| diagnostics | Channel Health Diagnostics | [Agent-Reach](https://github.com/Panniantong/Agent-Reach) |
| credential-management | Cookie Credential Extraction | [Agent-Reach](https://github.com/Panniantong/Agent-Reach) |
| agent-distribution | Agent-Driven Install | [Agent-Reach](https://github.com/Panniantong/Agent-Reach) |
| tts | ONNX TTS Pipeline | [supertonic](https://github.com/supertone-inc/supertonic) |
| tts | Flow-Matching Sampler | [supertonic](https://github.com/supertone-inc/supertonic) |
| tts | Expression Tags | [supertonic](https://github.com/supertone-inc/supertonic) |
| ai-workflow | Agentic Loop | [open-design](https://github.com/nexu-io/open-design) |
| ai-workflow | Agent CLI Integration | [open-design](https://github.com/nexu-io/open-design) |
| codegen | Design Artifact Generation | [open-design](https://github.com/nexu-io/open-design) |
| design-systems | Design Systems Library | [open-design](https://github.com/nexu-io/open-design) |
| infrastructure | BYOK Proxy | [open-design](https://github.com/nexu-io/open-design) |
| infrastructure | Local-First Architecture | [open-design](https://github.com/nexu-io/open-design) |
| plugin-architecture | Skills System | [open-design](https://github.com/nexu-io/open-design) |
| plugin-architecture | Plugin Ecosystem | [open-design](https://github.com/nexu-io/open-design) |
| reactivity | Signals Reactivity Engine | [tldraw](https://github.com/tldraw/tldraw) |
| state-management | Reactive Record Store | [tldraw](https://github.com/tldraw/tldraw) |
| schema-migrations | Schema & Migrations | [tldraw](https://github.com/tldraw/tldraw) |
| realtime | Multiplayer Sync | [tldraw](https://github.com/tldraw/tldraw) |
| design-systems | Token Pipeline Orchestration | [style-dictionary](https://github.com/style-dictionary/style-dictionary) |
| design-systems | Reference Resolution Engine | [style-dictionary](https://github.com/style-dictionary/style-dictionary) |
| design-systems | Transforms & Transform Groups | [style-dictionary](https://github.com/style-dictionary/style-dictionary) |
| plugin-architecture | Register / Extensibility API | [style-dictionary](https://github.com/style-dictionary/style-dictionary) |
| canvas-interaction | Pan & Zoom Canvas | [xyflow](https://github.com/xyflow/xyflow) |
| canvas-interaction | Node Dragging | [xyflow](https://github.com/xyflow/xyflow) |
| canvas-interaction | Minimap Navigation | [xyflow](https://github.com/xyflow/xyflow) |
| graph-editing | Connection Handles | [xyflow](https://github.com/xyflow/xyflow) |
| graph-editing | Node Resizer | [xyflow](https://github.com/xyflow/xyflow) |
| graph-rendering | Edge Path Algorithms | [xyflow](https://github.com/xyflow/xyflow) |
| state-management | Reactive Store Architecture | [xyflow](https://github.com/xyflow/xyflow) |
| rendering | Hand-Drawn Rendering | [excalidraw](https://github.com/excalidraw/excalidraw) |
| realtime-collab | E2E-Encrypted Collaboration | [excalidraw](https://github.com/excalidraw/excalidraw) |
| realtime-collab | Scene Reconciliation | [excalidraw](https://github.com/excalidraw/excalidraw) |
| data-structures | Fractional Indexing (z-order) | [excalidraw](https://github.com/excalidraw/excalidraw) |
| ai-integration | Submit-and-Poll Generation Client | [open-generative-ai](https://github.com/Anil-matcha/Open-Generative-AI) |
| ai-integration | Centralized Model Registry | [open-generative-ai](https://github.com/Anil-matcha/Open-Generative-AI) |
| credential-management | Browser→Host API Proxy + Auth Bridge | [open-generative-ai](https://github.com/Anil-matcha/Open-Generative-AI) |
| ui-architecture | Multi-Studio Shell Architecture | [open-generative-ai](https://github.com/Anil-matcha/Open-Generative-AI) |
| code-generation | Interview-Driven App Scaffolding | [whatsapp-agentkit](https://github.com/Hainrixz/whatsapp-agentkit) |
| messaging | WhatsApp Provider Adapter Layer | [whatsapp-agentkit](https://github.com/Hainrixz/whatsapp-agentkit) |
| agent-architecture | Per-Contact Conversation Memory | [whatsapp-agentkit](https://github.com/Hainrixz/whatsapp-agentkit) |
| lead-scoring | Rule-Based Lead Scoring | [auto-crm](https://github.com/Hainrixz/auto-crm) |
| ai-integration | AI Lead Classification (Claude) | [auto-crm](https://github.com/Hainrixz/auto-crm) |
| lead-ingestion | Webhook Lead Ingestion | [auto-crm](https://github.com/Hainrixz/auto-crm) |
| agent-architecture | MCP CRM Server | [auto-crm](https://github.com/Hainrixz/auto-crm) |
| canvas-interaction | Kanban Pipeline (drag-and-drop) | [auto-crm](https://github.com/Hainrixz/auto-crm) |
| analytics | CRM Dashboard KPIs | [auto-crm](https://github.com/Hainrixz/auto-crm) |
| data-portability | CSV Import / Export | [auto-crm](https://github.com/Hainrixz/auto-crm) |
| activity-tracking | Activity Tracking & Follow-up Buckets | [auto-crm](https://github.com/Hainrixz/auto-crm) |
| agent-distribution | Self-Customizing CRM (Claude commands) | [auto-crm](https://github.com/Hainrixz/auto-crm) |
| content-synthesis | AI Carousel Generation | [carousel-generator](https://github.com/FranciscoMoretti/carousel-generator) |
| rendering | DOM-to-PDF Carousel Export | [carousel-generator](https://github.com/FranciscoMoretti/carousel-generator) |
| design-systems | OKLCH Theme Palettes | [carousel-generator](https://github.com/FranciscoMoretti/carousel-generator) |
| data-portability | Zod Form Persistence & JSON Portability | [carousel-generator](https://github.com/FranciscoMoretti/carousel-generator) |
| infrastructure | BYOK + Rate-Limited AI Action | [carousel-generator](https://github.com/FranciscoMoretti/carousel-generator) |
| pipeline-orchestration | Graph Execution Engine | [scrapegraph-ai](https://github.com/ScrapeGraphAI/Scrapegraph-ai) |
| web-extraction | SmartScraper Pipeline | [scrapegraph-ai](https://github.com/ScrapeGraphAI/Scrapegraph-ai) |
| web-extraction | Multi-Source Fetch Node | [scrapegraph-ai](https://github.com/ScrapeGraphAI/Scrapegraph-ai) |
| structured-extraction | Map-Reduce Answer Generation | [scrapegraph-ai](https://github.com/ScrapeGraphAI/Scrapegraph-ai) |
| ai-integration | Provider-Agnostic Model Layer | [scrapegraph-ai](https://github.com/ScrapeGraphAI/Scrapegraph-ai) |
| research-automation | Search-Driven Scraping | [scrapegraph-ai](https://github.com/ScrapeGraphAI/Scrapegraph-ai) |
| state-management | Change-Based Mutation Model | [penpot](https://github.com/penpot/penpot) |
| design-systems | Native Design Tokens | [penpot](https://github.com/penpot/penpot) |
| rendering | WASM/Skia Render Engine | [penpot](https://github.com/penpot/penpot) |
| macos-ui | Notch-Shaped Always-On-Top Window | [boring.notch](https://github.com/TheBoredTeam/boring.notch) |
| media-control | Multi-Provider Media Control | [boring.notch](https://github.com/TheBoredTeam/boring.notch) |
| macos-ui | System HUD Replacement | [boring.notch](https://github.com/TheBoredTeam/boring.notch) |
| ai-workflow | Chat-Completion Middleware | [open-webui](https://github.com/open-webui/open-webui) |
| permissions | Unified Permission Abstraction | [PermissionsKit](https://github.com/sparrowcode/PermissionsKit) |
| infrastructure | Modular Per-Permission Packaging | [PermissionsKit](https://github.com/sparrowcode/PermissionsKit) |
| infrastructure | Async-to-Sync Status Bridging | [PermissionsKit](https://github.com/sparrowcode/PermissionsKit) |
| web-extraction | Indexed DOM Serialization | [browser-use](https://github.com/browser-use/browser-use) |
| agent-architecture | Agent Loop & Recovery | [browser-use](https://github.com/browser-use/browser-use) |
| agent-architecture | Action / Tool Registry | [browser-use](https://github.com/browser-use/browser-use) |
| ai-integration | Multi-Provider LLM Abstraction | [browser-use](https://github.com/browser-use/browser-use) |
| browser-automation | Browser Session & Stealth | [browser-use](https://github.com/browser-use/browser-use) |

---

## How it's organized

```
distill-it/
├── graph/
│   ├── graph.json        ← single source of truth (all nodes + edges)
│   └── graph.html        ← open in browser for the interactive map
├── features/             ← organized by WHAT it does, not which repo
│   └── <domain>/
│       ├── _domain.md
│       ├── study/        ← human-readable, NotebookLM-ready
│       └── build/        ← agent-ready transplant spec
└── repos/
    └── <repo>.md         ← index of everything extracted from one repo
```

Features are filed by **what they do** — so all "file detection" approaches sit together
regardless of which repo they came from.

---

## Add a new repo

Run `/distill https://github.com/owner/repo` in Claude Code.

Claude reads the repo over the web (no cloning), shows you the feature list,
writes the study + build docs for whichever you pick, updates the graph, commits, and pushes.

---

*Built with [Claude Code](https://claude.ai/code) using the `repository-intelligence` skill.*
