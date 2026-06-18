# Hazelnut — origin index

- **Source:** https://github.com/ricardodantas/hazelnut
- **What it is:** A terminal-based file organizer (a CLI/TUI "Hazel" for Linux/macOS). Watches folders
  and auto-applies rules — match files by name/ext/size/age, then move/copy/rename/trash/delete/archive
  or run a custom script. Two-binary: a TUI frontend + a background daemon.
- **Author:** Ricardo Dantas · **License:** GPL-3.0-or-later
- **Stack:** Rust (1.93+) · `notify` (FS events) · `glob` + `regex` · `trash` · `serde` config · a TUI.
- **Date distilled:** 2026-06-18
- **Architecture in one line:** the watcher debounces OS file events (+ an initial scan) → routes each
  file to its directory's allowed rules → the rule engine AND-matches optional conditions → executes
  the matched action, stopping after a destructive one.

## Features extracted
| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Debounced File Watcher | realtime | [study](../features/realtime/study/debounced-file-watcher--from-hazelnut.md) | [build](../features/realtime/build/debounced-file-watcher--from-hazelnut.md) |
| File Rules Engine | pipeline-orchestration | [study](../features/pipeline-orchestration/study/file-rules-engine--from-hazelnut.md) | [build](../features/pipeline-orchestration/build/file-rules-engine--from-hazelnut.md) |
| File Actions Executor | pipeline-orchestration | [study](../features/pipeline-orchestration/study/file-actions-executor--from-hazelnut.md) | [build](../features/pipeline-orchestration/build/file-actions-executor--from-hazelnut.md) |

## Not yet distilled (candidates)
- **TUI + daemon two-binary architecture** (IPC between frontend and background processor) → domain: `infrastructure`
- **Theme system** (15 built-in terminal color schemes) → domain: `design-systems`
- **Config schema + hot reload** (serde rules config, reload without losing counters) → domain: `infrastructure`

## Verification gaps flagged in build docs (check before transplant)
- `notify` config/backends per OS, daemon loop driving process_events — watcher build.
- Config (de)serialization shape, glob case-sensitivity, age rounding — rules-engine build.
- Placeholder set + date format, zip details, shell arg escaping, cross-fs move fallback — actions build.

> Distill note: traced inline (no agent fan-out); small Rust repo, spines read/grepped from raw source.
