# Cross-Platform Plugin Installer (build spec) — distilled from Understand-Anything

## Summary
A bash/PowerShell installer that clones a plugin repo once and symlinks its `skills/` into each of
~13 AI-agent platforms using one of two per-platform linking strategies. `--update` = git pull
(propagates via symlinks); uninstall removes stale links even if the clone is gone. Platform is
explicit (arg or menu), not auto-detected.

## Core logic (inlined)
```
CLONE_DIR = ${UA_REPO_DIR:-$HOME/.understand-anything/repo}
REPO_URL  = ${UA_REPO_URL:-https://github.com/Egonex-AI/Understand-Anything}
ROOT_LINK = $HOME/.understand-anything-plugin   # universal symlink -> clone

install(platform):
  git clone REPO_URL CLONE_DIR   (or git -C CLONE_DIR pull if exists)
  ln -s CLONE_DIR/understand-anything-plugin ROOT_LINK
  (target_dir, style) = PLATFORM_TABLE[platform]
  if style == per-skill:
      for skill in repo/skills/*:  ln -s repo/skills/<skill>  target_dir/<skill>
  if style == folder:
      ln -s repo/skills  target_dir/understand-anything

PLATFORM_TABLE (13):
  per-skill: gemini, codex, opencode, pi, vibe, vscode, trae, nanobot
             e.g. target ~/.agents/skills/<skill> -> repo/skills/<skill>
  folder:    openclaw, antigravity, hermes, cline, kimi
             e.g. ~/.openclaw/skills/understand-anything -> repo/skills

update:   git -C CLONE_DIR pull      # all platforms update via existing symlinks
uninstall: scan known target dirs for symlinks pointing into CLONE_DIR; rm them
           (works even if CLONE_DIR already deleted -> detect dangling links)
platform selection: argv[1] OR interactive numbered menu (NO auto-detection)
overrides: UA_REPO_URL, UA_REPO_DIR
```

## Data contracts
No data files. State = the symlink graph on disk. Inputs: platform name (string from the fixed
set), optional flags (`--update`, `--uninstall`), optional env overrides. Each platform entry =
`{ name, targetDir, style: "per-skill" | "folder" }`.

## Dependencies & assumptions
- `git`, a POSIX shell (bash) / PowerShell; symlink support (so: not native Windows without dev
  mode — hence the `.ps1` variant / junctions).
- Each platform's skills directory convention is known and stable (the table).

## To port this, you need:
- [ ] A clone-once location + a universal root symlink.
- [ ] A platform table mapping name → target dir → linking style.
- [ ] Per-skill vs whole-folder link logic.
- [ ] `--update` = pull-in-place; uninstall = remove links (handle dangling).
- [ ] Explicit platform arg + interactive menu fallback.
- [ ] Env-var overrides for repo URL / dest.

## Gotchas
- Symlinks on Windows need dev mode or junctions — the PowerShell path must handle this.
- Uninstall must detect *dangling* symlinks (clone deleted first) or it leaves cruft.
- Adding a platform = one table row, but you must know whether it scans a folder or per-skill
  entries; guessing wrong silently fails to register the plugin.
- This is the symlink-install path; native Claude Code uses the `/plugin marketplace` flow instead.

## Origin (reference only)
`install.sh` (+ `install.ps1`) at the Understand-Anything repo root.
