# Scrapling — origin index

- **Source:** https://github.com/D4Vinci/Scrapling
- **What it is:** An adaptive Python web-scraping framework — fetching (incl. stealth/anti-bot),
  parsing, a spider framework, an interactive shell, and AI/MCP integration. Its signature
  differentiator is adaptive parsing (self-healing selectors).
- **License:** BSD-3-Clause · **Author:** Karim Shoair
- **Date distilled:** 2026-06-13
- **Note:** Ships its own official agent skill at `agent-skill/Scrapling-Skill/SKILL.md` —
  author-blessed feature docs worth mining if distilling more of it later.

## Features extracted
| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Adaptive Element Relocation | adaptive-parsing | [study](../features/adaptive-parsing/study/adaptive-element-relocation--from-scrapling.md) | [build](../features/adaptive-parsing/build/adaptive-element-relocation--from-scrapling.md) |

## Not yet distilled (candidates)
- StealthyFetcher / anti-bot bypass (Cloudflare Turnstile) → domain: `stealth-fetching`
- Spider framework (concurrent crawl, pause/resume, proxy rotation) → domain: `crawling`
- Interactive shell (curl2fetcher, page/pages history) → domain: `dev-tooling`
- Pluggable fingerprint storage (SQLite/online) → domain: `adaptive-parsing`
