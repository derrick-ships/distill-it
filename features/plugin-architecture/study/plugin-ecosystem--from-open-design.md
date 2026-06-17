# Plugin Ecosystem — from [open-design](https://github.com/nexu-io/open-design)

> Domain: [[_domain]] · Source: https://github.com/nexu-io/open-design · NotebookLM: 

## What it does

Open Design's plugin model is how the app stays extensible without a monolithic codebase. Official skills, community contributions, and design systems all use the same discovery mechanism: drop a folder in the right place, restart, and it's live. The runtime normalizes everything to a common manifest format so the rest of the app doesn't care whether something came from a SKILL.md, a Claude plugin, or a sidecar JSON.

## Why it exists

Design tools need to grow — new output modes, new brand systems, new agent integrations. A plugin ecosystem means the community can add Linear's design system or a new "motion graphics brief" skill without touching core code. Open Design treats extensibility as a first-class requirement, not an afterthought.

## How it actually works

The ecosystem has three tiers:

**Official plugins** — first-party, bundled with the app, auto-registered at startup. These are the 54+ built-in skills and 150 design systems.

**Community plugins** — user-installable contributions. Not pre-installed. Discovered from a registry.

**User custom plugins** — you drop folders into your local `skills/` or `design-systems/` directories and they appear after restart.

The runtime that handles all of this is the `plugin-runtime` package — a pure TypeScript library with no Node.js imports (so it works in browsers and CI too). It exposes:
- A parser for SKILL.md frontmatter
- Adapters that convert raw skill files into a normalized `PluginManifest`
- A merge function that reconciles multiple sources (sidecar JSON overrides adapter output)
- A validator that checks manifest correctness
- A digest function that fingerprints a skill+input combination

When the daemon starts, it scans for skills and design systems, converts them to manifests, and registers them. When a user picks a skill, the runtime resolves it, validates it, and hands the manifest to the agent runner, which injects the skill instructions into the agent's system prompt.

The real extensibility power is in the `PluginManifest` schema — a skill can declare not just instructions but also: what input form fields to show the user, what live-tweakable parameters exist (sliders, pickers), which design system sections it needs, which agent capabilities it requires, and what pipeline stages to run. The host app doesn't need to know anything about the skill's content — it just reads the manifest.

## The non-obvious parts

**22+ coding-agent CLIs are all adapters.** Each agent CLI (Claude Code, Cursor, Copilot, Hermes, Codex, Qwen, Devin, Kiro, etc.) has an adapter in `apps/daemon/src/agents.ts` that specifies: the binary name, how to check its version, how to build the invocation command, and what output format it produces. Adding a new agent is adding one adapter object.

**Agent communication is stdio-based.** Skills don't call APIs — the skill instructions go into the agent's system prompt, the agent CLI runs as a child process, and its output streams back via stdio. The MCP server integration is a separate layer that gives the agent access to tools (file system, design API).

**The sidecar pattern is a clean override mechanism.** Adding an `open-design.json` file next to any `SKILL.md` applies the highest-priority customization without touching the original file. It's the plugin equivalent of CSS specificity.

## Related

- [[skills-system--from-open-design]] (the SKILL.md format and PluginManifest internals)
- [[agent-cli-integration--from-open-design]] (the 22 CLI adapters that execute plugin instructions)
- [[agentic-loop--from-open-design]] (where plugins are resolved and injected)
