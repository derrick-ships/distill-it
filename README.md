# repo-brain 🧠

One organized home for every repository I reverse-engineer, feature by feature.

This isn't a code repo — it's a **knowledge repo**. Each entry distills one feature from some
open-source product into two layers: a plain-language **study** doc (for understanding, and for
uploading to NotebookLM) and a transplant-grade **build** doc (for an AI agent to reimplement
that feature in a new project, even without the original repo).

Built and maintained with the `repository-intelligence` skill.

## How it's organized

```
repo-brain/
├── graph/
│   ├── graph.json   ← single source of truth (all nodes + edges)
│   └── graph.html   ← open this in a browser for the clickable map
├── features/        ← organized BY FEATURE, not by repo
│   └── <domain>/    ← e.g. adaptive-parsing, auth, billing, crawling
│       ├── _domain.md           what this domain means across all repos
│       ├── study/<feature>--from-<repo>.md   plain-language explainer
│       └── build/<feature>--from-<repo>.md   technical rebuild spec
└── repos/
    └── <repo>.md    ← index of everything distilled from one source repo
```

Features are filed by **what they do**, so "every auth approach I've ever studied" sit together,
each tagged with the repo it came from via the `--from-<repo>` suffix.

## How to use it

- **Browse the map:** open `graph/graph.html` in a browser. Click any node → summary + links to
  the study doc, the build spec, the origin repo, and (once added) its NotebookLM notebook.
- **Study a feature:** read the `study/` doc. To go deep, upload a `study/` folder (or the whole
  `features/` tree) to NotebookLM and let it build its own graph + answer questions. Paste the
  notebook link back into the feature's `graph.json` node so the map links to it.
- **Reuse a feature in a build:** in Claude Code, point the `repository-intelligence` skill at
  the relevant `build/` doc and ask it to implement the feature in your current project.
- **Open as an Obsidian vault** (optional): the `study/` docs use `[[wikilinks]]`, so Obsidian
  draws the graph natively too — same source of truth, second renderer.

## Adding to it

Run the `repository-intelligence` skill in DISTILL mode on any GitHub repo (just give the plain
repo URL — no cloning). It writes the study + build docs, updates `graph.json`, and regenerates
`graph.html`. Changes are committed and pushed automatically.

## What's inside so far

| Domain | Features | Source repo |
|--------|----------|-------------|
| adaptive-parsing | 1 | [Scrapling](https://github.com/D4Vinci/Scrapling) |
| document-conversion | 4 | [markitdown](https://github.com/microsoft/markitdown) |
| plugin-architecture | 1 | [markitdown](https://github.com/microsoft/markitdown) |
| file-detection | 1 | [markitdown](https://github.com/microsoft/markitdown) |
| media-processing | 2 | [markitdown](https://github.com/microsoft/markitdown) |
| web-extraction | 2 | [markitdown](https://github.com/microsoft/markitdown) |
| ai-integration | 1 | [markitdown](https://github.com/microsoft/markitdown) |
| agent-architecture | 1 | [last30days-skill](https://github.com/mvanhorn/last30days-skill) |
| research-automation | 3 | [last30days-skill](https://github.com/mvanhorn/last30days-skill) |
| content-synthesis | 1 | [last30days-skill](https://github.com/mvanhorn/last30days-skill) |
| credential-management | 1 | [last30days-skill](https://github.com/mvanhorn/last30days-skill) |

**18 nodes · 30 edges** — open [`graph/graph.html`](graph/graph.html) to explore the map.

_Last updated: 2026-06-15_
