```
  ██████╗ ██╗███████╗████████╗██╗██╗      ██╗      ██╗████████╗
  ██╔══██╗██║██╔════╝╚══██╔══╝██║██║      ██║      ██║╚══██╔══╝
  ██║  ██║██║███████╗   ██║   ██║██║      ██║█████╗██║   ██║
  ██║  ██║██║╚════██║   ██║   ██║██║      ██║╚════╝██║   ██║
  ██████╔╝██║███████║   ██║   ██║███████╗ ███████╗ ██║   ██║
  ╚═════╝ ╚═╝╚══════╝   ╚═╝   ╚═╝╚══════╝ ╚══════╝ ╚═╝   ╚═╝
```

> **Point Claude at any GitHub repo. Get back structured knowledge you can actually reuse.**

![52 nodes](https://img.shields.io/badge/nodes-52-4299e1?style=flat-square)
![28 domains](https://img.shields.io/badge/domains-28-9f7aea?style=flat-square)
![10 repos](https://img.shields.io/badge/repos-10-68d391?style=flat-square)
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
