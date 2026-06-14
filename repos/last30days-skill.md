# last30days-skill

**Source:** https://github.com/mvanhorn/last30days-skill
**Description:** Claude Code skill that generates a structured research brief on any topic by
fan-out retrieval from 12+ sources (Reddit, HN, X, GitHub, Polymarket, TikTok, YouTube, etc.),
RRF ranking, LLM reranking, cross-source clustering, and a strict 5-law output contract.
**Date distilled:** 2026-06-14
**Stack:** Python 3.11+, ThreadPoolExecutor, difflib, python-dotenv, yt-dlp, OpenRouter

---

## Distilled Features

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Agent Output Contract | agent-architecture | [study](../features/agent-architecture/study/agent-output-contract--from-last30days-skill.md) | [build](../features/agent-architecture/build/agent-output-contract--from-last30days-skill.md) |
| Multi-Source Research Engine | research-automation | [study](../features/research-automation/study/multi-source-research-engine--from-last30days-skill.md) | [build](../features/research-automation/build/multi-source-research-engine--from-last30days-skill.md) |
| Entity Resolution | research-automation | [study](../features/research-automation/study/entity-resolution--from-last30days-skill.md) | [build](../features/research-automation/build/entity-resolution--from-last30days-skill.md) |
| Engagement Signal Ranking | research-automation | [study](../features/research-automation/study/engagement-signal-ranking--from-last30days-skill.md) | [build](../features/research-automation/build/engagement-signal-ranking--from-last30days-skill.md) |
| Cross-Source Clustering | content-synthesis | [study](../features/content-synthesis/study/cross-source-clustering--from-last30days-skill.md) | [build](../features/content-synthesis/build/cross-source-clustering--from-last30days-skill.md) |
| Multi-Tier Credentials | credential-management | [study](../features/credential-management/study/multi-tier-credentials--from-last30days-skill.md) | [build](../features/credential-management/build/multi-tier-credentials--from-last30days-skill.md) |

---

## Not distilled

- **Skill+Engine Architecture** (feature 1) — the SKILL.md/engine separation pattern; useful
  context but the output contract (feature 2) covers the actionable parts
- **HTML Brief Generation** (feature 7) — thin Jinja2 template layer over the Markdown output;
  not distilled as it adds little beyond standard templating

---

## Key design decisions

- **Keyless-first:** Tier 1 sources (Reddit fallback chain, HN, Polymarket, GitHub public API)
  need zero credentials, making the skill usable out-of-the-box
- **Depth tiers** (quick/default/deep) cap source count and control LLM reranking behavior,
  letting callers trade latency for coverage
- **Same-source isolation** in clustering prevents echo-chamber grouping
- **5-law output contract** enforced via SKILL.md prompt text rather than runtime validation
