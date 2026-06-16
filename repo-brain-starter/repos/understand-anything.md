# Understand-Anything — origin index

- **Source:** https://github.com/Egonex-AI/Understand-Anything
- **What it is:** A Claude Code (+ 13-platform) plugin that turns any codebase into an interactive
  knowledge graph you can explore, search, and ask questions about. A multi-agent pipeline pairs
  Tree-sitter (deterministic structure) with LLMs (semantic meaning), persists a JSON graph, and
  renders it in a local React/Vite dashboard. Signature idea: split every step into a deterministic
  spine + a swappable LLM interpretation layer, and re-run only what changed.
- **Stack:** TypeScript/JavaScript (pnpm monorepo) + Python scripts; Tree-sitter; React 19 +
  React Flow + d3-force/dagre/elkjs + graphology; Vite; Vitest.
- **Date distilled:** 2026-06-15
- **Note:** Six core agents live in `understand-anything-plugin/agents/*.md` and are the richest
  source; bundled `.mjs`/`.py` scripts own all deterministic work. `@understand-anything/core`
  holds the shared graph types + SearchEngine (its internal scoring is not exposed in consumer code).

## Features extracted (all 9 distilled)
| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Multi-Agent Analysis Pipeline | code-analysis | [study](../features/code-analysis/study/multi-agent-analysis-pipeline--from-understand-anything.md) | [build](../features/code-analysis/build/multi-agent-analysis-pipeline--from-understand-anything.md) |
| Hybrid Static + Semantic Extraction | code-analysis | [study](../features/code-analysis/study/hybrid-static-semantic-extraction--from-understand-anything.md) | [build](../features/code-analysis/build/hybrid-static-semantic-extraction--from-understand-anything.md) |
| Diff Impact Analysis | code-analysis | [study](../features/code-analysis/study/diff-impact-analysis--from-understand-anything.md) | [build](../features/code-analysis/build/diff-impact-analysis--from-understand-anything.md) |
| Knowledge Graph Data Model | knowledge-graph | [study](../features/knowledge-graph/study/knowledge-graph-data-model--from-understand-anything.md) | [build](../features/knowledge-graph/build/knowledge-graph-data-model--from-understand-anything.md) |
| Interactive Graph Dashboard | visualization | [study](../features/visualization/study/interactive-graph-dashboard--from-understand-anything.md) | [build](../features/visualization/build/interactive-graph-dashboard--from-understand-anything.md) |
| Graph Search & Retrieval | search | [study](../features/search/study/graph-search-retrieval--from-understand-anything.md) | [build](../features/search/build/graph-search-retrieval--from-understand-anything.md) |
| Dependency-Ordered Guided Tours | onboarding | [study](../features/onboarding/study/dependency-ordered-guided-tours--from-understand-anything.md) | [build](../features/onboarding/build/dependency-ordered-guided-tours--from-understand-anything.md) |
| Business Domain Mapping | domain-modeling | [study](../features/domain-modeling/study/business-domain-mapping--from-understand-anything.md) | [build](../features/domain-modeling/build/business-domain-mapping--from-understand-anything.md) |
| Cross-Platform Plugin Installer | distribution | [study](../features/distribution/study/cross-platform-plugin-installer--from-understand-anything.md) | [build](../features/distribution/build/cross-platform-plugin-installer--from-understand-anything.md) |

## Known gaps (verify before relying)
- **Dashboard persona-adaptive mechanics** and the exact **token-validation path** are not in the
  public skill docs — confirm in `packages/dashboard/src`.
- **SearchEngine scoring** (fuzzy threshold vs semantic, field weights) lives inside
  `@understand-anything/core` and is not visible in consumer code — read `packages/core` before
  reimplementing exact ranking.
