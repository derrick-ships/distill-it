# Cross-Platform Plugin Installer — from [Understand-Anything](https://github.com/Egonex-AI/Understand-Anything)

> Domain: [[_domain]] · Source: https://github.com/Egonex-AI/Understand-Anything · NotebookLM:

## What it does
One install script drops the plugin into whichever AI coding agent you use — Gemini CLI, Codex,
OpenCode, Cursor/VS Code, Cline, Kimi, and ~13 platforms in all — each of which keeps its skills in
a different directory. Instead of copying files into each, it clones the repo once and **symlinks**
the skills into every platform's folder, so a single `git pull` updates them all at once.

## Why it exists
The AI-agent ecosystem is fragmented: every tool has its own plugin/skills convention. Copy-paste
installs go stale the moment the plugin updates, and maintaining N copies is a nightmare. Reach is
a growth lever — a tool that installs cleanly *everywhere* gets adopted where a single-platform
tool dies. Symlinks make "installed in 13 places" and "updated in one command" the same thing.

## How it actually works
A bash installer (`install.sh`, with a PowerShell `install.ps1` sibling):
- **Clone once** to `$HOME/.understand-anything/repo`, and expose a universal root symlink at
  `$HOME/.understand-anything-plugin`.
- **A platform table** maps each of the 13 supported agents (`gemini, codex, opencode, pi,
  openclaw, antigravity, vibe, vscode, hermes, cline, kimi, trae, nanobot`) to its target directory
  and a linking strategy.
- **Two linking styles:**
  - *Per-skill linking* — one symlink per skill dir, e.g.
    `$HOME/.agents/skills/<skill> → repo/skills/<skill>` (gemini, codex, opencode, pi, vibe,
    vscode, trae, nanobot).
  - *Folder linking* — one symlink wrapping the whole skills dir, e.g.
    `$HOME/.openclaw/skills/understand-anything → repo/skills` (openclaw, antigravity, hermes,
    cline, kimi).
- **No auto-detection** — you pass the platform (`install.sh codex`) or pick from an interactive
  numbered menu.
- **`--update`** does a `git pull` in the clone; because everything is symlinked, all platforms get
  the new version instantly.
- **Uninstall** scans for and removes stale symlinks even if the clone was already deleted.
- **Env-var overrides** let you point at a different repo URL or destination dir for custom
  deployments.

(Separately, native Claude Code installs via `/plugin marketplace add Egonex-AI/Understand-Anything`
then `/plugin install understand-anything` — the marketplace path, not this script.)

## The non-obvious parts
- **Symlinks, not copies, are the whole design.** They collapse "install everywhere" and "update
  once" into one operation and eliminate version drift across platforms.
- **Two linking styles because platforms disagree** on whether they scan a skills *folder* or
  expect individual skill entries — the table encodes that per-platform quirk.
- **Stateless updates**: the installer holds no state; the symlink graph *is* the state, so update
  and uninstall just manipulate links.
- **Explicit platform choice** avoids fragile auto-detection across a moving ecosystem.

## Related
- See also: dotfile managers (stow) — same clone-once-symlink-everywhere pattern
- [[multi-agent-analysis-pipeline--from-understand-anything]] — the thing being distributed
