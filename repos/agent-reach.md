# agent-reach

**Source:** https://github.com/Panniantong/Agent-Reach
**Product:** A CLI "capability layer" that gives AI agents (Claude Code, OpenClaw, Cursor, Windsurf…) free, unified read access to ~12 internet platforms (general web via Jina Reader, YouTube, Twitter/X, Reddit, Bilibili, Xiaohongshu, GitHub, RSS, Exa semantic search, LinkedIn, V2EX, Xueqiu, podcasts). It does **not** wrap the platforms — it *selects, installs, health-checks, and routes* upstream CLI tools, then the agent calls those tools directly.
**Stack:** Python ≥3.10, Hatchling. `requests`, `feedparser`, `python-dotenv`, `loguru`, `pyyaml`, `rich`, `yt-dlp`; optional `playwright`, `mcp[cli]`, `browser-cookie3`/`rookiepy`. Orchestrates upstream tools: twitter-cli, OpenCLI, bird, bili-cli, rdt-cli, yt-dlp, mcporter+Exa, gh CLI, xiaohongshu-mcp. Entry point `agent-reach` → `agent_reach.cli:main`. v1.5.0.
**Distilled:** 2026-06-16

## Features distilled

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Ordered Backend Routing | agent-architecture | [study](../features/agent-architecture/study/ordered-backend-routing--from-agent-reach.md) | [build](../features/agent-architecture/build/ordered-backend-routing--from-agent-reach.md) |
| Channel Health Diagnostics | diagnostics | [study](../features/diagnostics/study/channel-health-diagnostics--from-agent-reach.md) | [build](../features/diagnostics/build/channel-health-diagnostics--from-agent-reach.md) |
| Cookie Credential Extraction | credential-management | [study](../features/credential-management/study/cookie-credential-extraction--from-agent-reach.md) | [build](../features/credential-management/build/cookie-credential-extraction--from-agent-reach.md) |
| Agent-Driven Install | agent-distribution | [study](../features/agent-distribution/study/agent-driven-install--from-agent-reach.md) | [build](../features/agent-distribution/build/agent-driven-install--from-agent-reach.md) |

## Not yet distilled (candidates)

- **Podcast/video → transcript pipeline** (`agent_reach/transcribe.py` + `tools/xiaoyuzhou/transcribe.sh`): yt-dlp download → transcode/slice → Groq Whisper `large-v3` → text, with free-tier rate-limit handling. (media-processing; more commodity.)
- **Per-platform channel integrations** (`agent_reach/channels/*.py`): the 12 concrete `can_handle`/`check` bodies (reddit, bilibili, xiaohongshu, exa_search, linkedin, v2ex, xueqiu, github, rss, web, youtube, xiaoyuzhou) — each a worked example of the routing pattern.
- **MCP integration via mcporter** (`agent_reach/integrations/`): registering Exa / xiaohongshu-mcp / linkedin-mcp servers and calling them through `mcporter`.
- **`--env=auto` environment detection & installer** (`agent_reach/cli.py` install path): local-machine vs. server detection, tiered channel install, `--safe`/`--dry-run`.

## Key takeaways

- **The engineering moat is resilience, not the integrations.** Anyone can shell out to `yt-dlp`. The durable ideas are: an *ordered, health-gated backend list* per capability (auto-fallback as a data edit), and a *probe that distinguishes "installed" from "actually runs"* (stale venv shebangs pass `which()`). Those two together are the reusable spine.
- **Existence ≠ health, and presence ≠ validity.** The probe executes a real command to catch broken installs; the credential layer checks for a logged-in marker token to reject anonymous cookie sets. The same skepticism shows up in both.
- **Security is baked into the plumbing.** Credential files are created owner-only atomically (`O_CREAT`+`0o600`, no write-then-chmod race), shell-mirrors are `shlex.quote`d, and `doctor` audits file permissions on a command users already run.
- **Distribution is agent-native.** The installer is a markdown runbook an agent executes, bounded by hard DO-NOT guardrails (no `sudo`, confined to `~/.agent-reach/`, never pollute the workspace). install.md / update.md / a silent daily `watch` are one mechanism across the whole lifecycle — a genuinely novel pattern worth its own domain (agent-distribution).
- **Two-phase selection is the subtle correctness fix.** Collect every backend's status, then prefer `ok` over `warn` regardless of order — so an installed-but-logged-out preferred backend never masks a fully-working fallback. The naive first-non-missing loop gets this wrong.
