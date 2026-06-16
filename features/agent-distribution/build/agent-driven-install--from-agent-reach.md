# Agent-Driven Install (build spec) — distilled from Agent-Reach

## Summary

A software-distribution pattern where the installer is a **markdown runbook an LLM agent executes**, not a binary. Ship a single `install.md` whose primary reader is an agent: a one-line human trigger up top, then an imperative "For AI Agents" program — explicit goal + philosophy, hard safety boundaries, an artifact-location table, a numbered procedure with pre-decided environment branches, user checkpoints for choices it can't make, and a closing command cheat-sheet. The same shape powers `update.md` and a daily `watch` cron. Transplanting this is mostly *authoring the doc correctly*; the code side is a thin CLI (`install`/`doctor`/`configure`/`watch`) the doc drives. Below is a reusable skeleton plus the rules that make it safe.

## Core logic (inlined) — the install.md skeleton to copy

```markdown
# <Product> — Installation Guide

## For Humans
Copy this to your AI Agent:
    install <Product>: https://raw.githubusercontent.com/<org>/<repo>/main/docs/install.md
> Security-conscious? Safe mode (won't auto-install system packages):
>     install <Product> (safe mode): <same URL>  — use the --safe flag

---

## For AI Agents

### Goal
Install <Product> + upstream tools so the user's agent has <capability>. After
install, call the upstream tools directly — <Product> is the selector, installer,
health checker and router, **never a wrapper**.

### ⚠️ Boundaries  (these are the product — do not soften)
- DO NOT run `sudo` unless the user explicitly approved.
- DO NOT modify system files outside `~/.<product>/`.
- DO NOT install packages not listed in this guide.
- DO NOT disable firewalls/security settings.
- DO NOT clone repos or create files inside the user's workspace/working dir.
- If something needs elevated permission, TELL the user and let them decide.

### 📁 Directory rules (never touch the workspace)
| Purpose          | Directory                  |
|------------------|----------------------------|
| Config & tokens  | `~/.<product>/`            |
| Upstream tools   | `~/.<product>/tools/`      |
| Temp files       | `/tmp/`                    |
| Skills           | `~/.<harness>/skills/<product>/` |

### Step 1 — Install the basics (choose the branch that matches the env)
    # preferred:
    pipx install <package-url>
    <product> install --env=auto
    # PEP 668 / Homebrew Python ("externally-managed-environment") → venv:
    python3 -m venv ~/.<product>-venv && source ~/.<product>-venv/bin/activate
    pip install <package-url> && <product> install --env=auto
    # Windows where `python3` is a Microsoft Store alias → use the launcher:
    py -3 -m venv ... ; ... ; <product> install --env=auto
Safe/dry:  `<product> install --env=auto --safe`   `--dry-run`

### Step 2 — Ask which optional channels the user wants  (DO NOT install all by default)
Present a short plain-language menu; install only the chosen ones:
    <product> install --env=auto --channels=<a>,<b>
    <product> install --env=auto --channels=all

### Step 3 — Fix what's broken
Run `<product> doctor`. Drive as many items to ✅ as possible, staying within
Boundaries. Only ask the user when you truly need input (creds/permissions).

### Step 4 — Configure credentials the agent can't self-provide
Security framing first (prefer a SECONDARY account; prefer Cookie-Editor export).
Give the exact per-platform command, e.g.:
    <product> configure <platform>-cookies "PASTED_STRING"

### Step 5 — (optional, harness-specific) daily self-check
Offer a daily cron running `<product> watch`: stay SILENT when all-good; only
notify on a problem or a new version (include the one-line update trigger).

---

## Quick Reference
| Command | What it does | ... |   ← durable cheat-sheet the agent keeps after install
```

### The thin CLI the doc drives (shape only)

```
<product> install --env=auto [--channels=a,b|all] [--safe] [--dry-run]
<product> doctor [--json]          # health report (see channel-health-diagnostics)
<product> configure <k> <v>        # save a credential/setting
<product> configure --from-browser chrome   # see cookie-credential-extraction
<product> watch                    # quiet health+update check for cron
<product> check-update
```

`--env=auto` detects local-machine vs. server and installs the zero-config tier;
`--channels` adds optional tiers; `--safe`/`--dry-run` are the "no surprises" modes.

### The update + watch lifecycle (same mechanism, three lifecycle points)

```
install:  agent fetches install.md → executes procedure
update:   agent fetches update.md  → executes upgrade procedure (versioning lives in the doc)
maintain: cron runs `<product> watch` daily, sessionTarget=isolated, delivery=announce:
          - output says "all good"  → stay silent
          - output has ❌/⚠️/🆕      → send full report + suggested fix (+ update trigger line)
```

## Data contracts

```
install.md structure (the contract with the agent):
  - "For Humans": the copyable one-line trigger (+ safe-mode variant)
  - "For AI Agents":
      Goal (1 paragraph, includes the "never a wrapper" framing)
      Boundaries (DO-NOT list — the safety contract)
      Directory rules (table: purpose → path; "never the workspace")
      Numbered Steps with pre-decided env branches + explicit user checkpoints
      Quick Reference command table (post-install cheat-sheet)

Channel/capability tiers presented to the user:
  tier 0 = zero-config (installed by basics)   tier 1 = needs free key/login   tier 2 = complex setup

User checkpoints (must pause and ask, not assume):
  (a) which optional channels?    (b) which credentials? (with security guidance)

Trigger string format (human → agent):  "<verb> <Product>: <raw-doc-URL> [extra flag instructions]"
```

## Dependencies & assumptions

- An agent harness that can (1) fetch a URL and (2) run shell commands with the user's consent (Claude Code, Cursor, Windsurf, OpenClaw…). The pattern is harness-agnostic *because* it's just doc + shell.
- A package installable via `pipx`/`pip` and a CLI exposing `install`/`doctor`/`configure`/`watch`.
- For the daily check: a scheduler in the harness (cron-like) with an "announce only on change" delivery mode.
- Assumes the agent reliably follows negative constraints (the DO-NOTs). Write them imperatively and without hedging; repeat the blast-radius path (`~/.<product>/`).
- `--safe`/`--dry-run` must actually be honored by the CLI for the safety story to be real.

## To port this, you need:

- [ ] An `install.md` with both readers: a one-line human trigger and an imperative agent program (use the skeleton above).
- [ ] An explicit Boundaries list (no `sudo`, confined to `~/.<product>/`, never touch the workspace, escalate-don't-elevate) — treat it as a hard spec, not flavor text.
- [ ] A directory-location table so the agent never writes into the user's project.
- [ ] Pre-decided environment branches for the failures you *know* happen (PEP 668, Homebrew Python, Windows Store-alias `python3`) — enumerate symptom → exact alternative command.
- [ ] Explicit user checkpoints for choices the agent shouldn't make alone (which optionals, which creds) — and instruct it NOT to install everything by default.
- [ ] A CLI with `install --env=auto [--channels] [--safe] [--dry-run]`, `doctor`, `configure`, `watch`.
- [ ] A matching `update.md` and a silent-unless-problem `watch` cron for the maintenance half.
- [ ] A closing Quick-Reference table so the agent retains a command cheat-sheet.

## Gotchas

- **The boundaries ARE the feature.** Agent + shell + install = risk; the value is bounded autonomy. If you omit/weaken the DO-NOTs, you've shipped an arbitrary-code-execution prompt. State them first, imperatively, no hedging.
- **Workspace pollution is the signature agent failure.** Without the directory table, agents `git clone` and drop files into the user's repo and slowly corrupt it. Make "never the workspace" explicit and give every artifact a home outside it.
- **Don't install everything by default.** Firehosing every optional channel wastes setup, triggers needless credential asks, and erodes trust. Make the optional menu an explicit user choice.
- **Encode known-failure branches, or the agent will improvise badly.** PEP 668 and the Store-alias trap are the two that bite; spell out the symptom and the exact fix so the agent doesn't try `sudo pip` (which your boundaries forbid anyway).
- **"Never a wrapper" must be said outright** or the agent keeps routing every call through your tool forever, adding latency and brittleness. Tell it to call upstream tools directly post-install.
- **Live-fetched docs are a supply-chain surface.** The agent runs whatever the doc says; serve it over HTTPS from a source you control, and have users paste a trusted URL. Treat doc edits with the same care as code releases (it *is* the release).
- **`--safe`/`--dry-run` are trust-builders only if real.** A safe mode that still mutates the system is worse than none. Wire them through.

## Origin (reference only)

Repo: https://github.com/Panniantong/Agent-Reach
Key files: `docs/install.md` (the full agent runbook — Goal/Boundaries/Directory-rules/Steps 1-5/Quick-Reference), `docs/update.md` (update trigger doc), `agent_reach/cli.py` (`install`/`doctor`/`configure`/`watch` entry: `agent_reach.cli:main`), `agent_reach/core.py` (`AgentReach` facade delegating to doctor), `agent_reach/skill/SKILL.md` + `~/.openclaw/skills/agent-reach/` (the installed post-install command reference). Human trigger example: "install Agent Reach: https://raw.githubusercontent.com/Panniantong/agent-reach/main/docs/install.md".
