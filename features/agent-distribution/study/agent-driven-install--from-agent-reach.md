# Agent-Driven Install (the install doc IS the installer) — from [Agent-Reach](https://github.com/Panniantong/Agent-Reach)

> Domain: [[_domain]] · Source: https://github.com/Panniantong/Agent-Reach · NotebookLM:

## What it does

You don't install Agent-Reach by running an installer. You tell your AI agent one sentence — "install Agent-Reach: <URL to install.md>" — and the agent fetches that markdown document and *executes it as a plan*: it installs the package, runs the bootstrap, decides what your environment needs, asks you which optional platforms you want, fixes what's broken, requests only the credentials it genuinely needs, and (optionally) sets up a daily self-check. The install document is written for two readers in one file: a "For Humans" section (the sentence to copy) and a much longer "For AI Agents" section that is, in effect, the program the agent runs.

## Why it exists

The product is a capability layer for agents — so the *agent* is the natural installer. A human doesn't want to learn `pipx` vs. venv vs. PEP 668, doesn't know that Reddit now requires login or that a Homebrew Python will refuse a global pip install. An agent can navigate all of that, adapt to the machine in front of it, and recover from failures — *if* it's given a clear, bounded plan and hard guardrails. The deeper bet: software distribution for the agent era is a well-specified natural-language runbook, versioned and fetched live, not a frozen binary. The same mechanism powers updates ("update Agent-Reach: <update.md>") and daily maintenance, so the install doc is really the spec for an agent that keeps a capability layer healthy over time.

## How it actually works

The install doc is a structured runbook with a fixed shape:

**A one-line human trigger,** plus a "safe mode" variant that tells the agent to add `--safe` so nothing auto-installs system packages. This is the entire human-facing surface.

**An explicit goal + a philosophy line** that prevents the most likely misunderstanding: "Agent-Reach is the selector, installer, health checker and router — *never a wrapper*. After install you call the upstream tools directly." This stops the agent from trying to route every request through Agent-Reach forever.

**Hard boundaries, stated as DO-NOTs** — no `sudo` without explicit approval, don't touch system files outside `~/.agent-reach/`, don't install anything not in the guide, don't disable firewalls/security, and (crucially) **don't create files or clone repos inside the user's working directory.** If something needs elevated permission, *tell the user and let them decide.* There's even a directory table dictating where every artifact goes (config in `~/.agent-reach/`, tool repos in `~/.agent-reach/tools/`, temp in `/tmp/`, skills in `~/.openclaw/skills/`) with the rationale: polluting the workspace silently degrades the user's own project over time.

**A numbered procedure the agent follows:**
1. Install the basics — with *branching* install instructions the agent chooses among (pipx; or a venv when PEP 668 / Homebrew Python is detected; or the Windows `py -3` launcher when `python3` is a Microsoft Store alias). This turns common, confusing failures into pre-decided paths.
2. Present a curated menu of optional channels in plain language and **ask the user which they want** — explicitly not installing everything by default.
3. Run the health check (`doctor`), try to fix what's broken *within the boundaries*, and only escalate to the user when genuinely blocked.
4. Collect credentials the agent can't self-provide, with security framing (use a secondary account; prefer the Cookie-Editor browser-extension import) and exact per-platform commands.
5. (For the OpenClaw runtime) offer to schedule a daily `watch` that stays silent when everything's fine and only pings the user on a problem or a new version — including the literal sentence to paste to trigger an update.

**A quick-reference command table** closes it, so after the conversational install the agent has a durable cheat-sheet of every command and every platform's upstream tool.

## The non-obvious parts

- **The doc is executable specification.** Its primary reader is an LLM, and it's written like code: imperative steps, explicit pre-decided branches, hard constraints, and a clear "definition of done" (get as many channels to ✅ as possible). The "For Humans" part is a thin shim over a program.
- **Guardrails are the product, not boilerplate.** Handing an agent shell access to install things is the risky part; the value is the *bounded autonomy* — a precise blast-radius (`~/.agent-reach/`), an explicit no-`sudo` rule, and a "stop and ask" escape hatch. The boundaries are what make agent-driven install safe enough to ship.
- **"Don't pollute the workspace" is a hard-won, agent-specific rule.** Agents naturally `git clone` and scribble files wherever they're working; over a project's life that corrupts the user's repo. The directory table exists specifically to fight that failure mode.
- **Branch-on-environment is encoded as prose, not detected by code.** The doc enumerates the exact symptoms (PEP 668 message, Store-alias path) and the exact alternative command, so the *agent* does the environment detection a traditional installer would hard-code. Cheaper to maintain, and adaptable.
- **Ask, don't assume — twice.** Both "which optional channels?" and "which credentials?" are explicit user checkpoints. The install is a conversation with decision points, not a silent firehose.
- **Distribution, update, and maintenance are one mechanism.** install.md / update.md / the daily `watch` cron are the same "agent reads a live doc and acts" pattern at three points in the lifecycle. Versioning lives in the fetched doc, not a pinned binary.

## The playbook (how this drives adoption)

- **Near-zero install friction** is the growth lever: the entire onboarding is one sentence the user can paste anywhere their agent runs. No README archaeology, no dependency wrangling.
- **Agent-agnostic by construction** — because the "installer" is just a doc + shell, it works in any harness that can fetch a URL and run commands (Claude Code, Cursor, Windsurf, OpenClaw), widening the addressable surface with zero per-platform engineering.
- **The silent daily `watch`** is a retention loop: it keeps capabilities working without nagging, and converts "platform changed its blocking" (a normal failure) into a quiet auto- or guided-fix instead of churn.
- **Cloneability:** the *mechanism* is trivial to copy (anyone can write an install.md). The moat is the maintained routing knowledge behind it — which backend works for which platform this week — not the delivery trick.

## Related

The procedure installs and then leans on the rest of the system:

- [[ordered-backend-routing--from-agent-reach]] — what the installed backends plug into
- [[channel-health-diagnostics--from-agent-reach]] — the `doctor`/`watch` step 3 and step 5 invoke
- [[cookie-credential-extraction--from-agent-reach]] — the step-4 credential flow
- [[agent-output-contract--from-last30days-skill]] — sibling "the markdown spec governs the agent's behavior" pattern (output rules vs. install steps); see also [[plugin-system--from-markitdown]] for the non-agent equivalent of extensible install/registration
