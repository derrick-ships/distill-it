# Domain: Distribution

Features about getting a tool *installed* across a fragmented ecosystem — here, one plugin that
must drop into 13+ different AI coding agents (Claude Code, Cursor, Codex, Gemini CLI, Copilot,
and more), each with its own skills/plugin directory convention. The common thread: one cloned
source of truth, symlinked into each platform so a single `git pull` updates them all.

## Features in this domain
- [[cross-platform-plugin-installer--from-understand-anything]] — a bash/PowerShell installer
  that clones once to `~/.understand-anything/repo` and symlinks skills into each platform's
  directory using per-skill or whole-folder linking, with `--update` and stale-symlink-safe
  uninstall. (from Understand-Anything)

## Why this domain matters
Reach is a moat. A tool that installs cleanly into every agent a developer might use — without
copy-paste drift, with one-command updates — gets adopted where a single-platform tool dies. The
"clone once, symlink everywhere, per-platform link strategy table" pattern is reusable for any
cross-agent plugin or dotfile-style distribution. When studying a repo, anything about
multi-platform install/packaging belongs here.
