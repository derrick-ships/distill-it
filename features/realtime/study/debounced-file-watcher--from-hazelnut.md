# Debounced File Watcher — from [hazelnut](https://github.com/ricardodantas/hazelnut)

> Domain: [[_domain]] · Source: https://github.com/ricardodantas/hazelnut · NotebookLM: <link once added>

## What it does

It watches one or more folders and reacts the instant a file shows up or changes — but it's smart about
it: it ignores the flurry of duplicate events the OS fires while a file is still being written
(debouncing), can watch a whole tree recursively, and on startup it also sweeps the folders for files
that are *already* there. Each watched folder can be tied to a specific subset of rules. It's the
"eyes" of a Hazel-style file organizer.

## Why it exists

File automation only feels magical if it's immediate and reliable. Two things ruin that: reacting to a
half-written file (the OS fires many "modify" events while a download finishes), and missing files that
existed before the watcher started. This component solves both — debounce so you act once, when the
file has settled, and an initial scan so nothing is missed — while staying responsive (the scan runs
off the main thread so the UI never blocks).

## How it actually works

It wraps the OS file-notification API (the Rust `notify` crate). Events are pushed onto a channel; the
app **polls** that channel non-blockingly, collecting pending events, then processes them. Only
`Create` and `Modify` events are acted on — renames-away, deletes, etc. are ignored.

The **debounce** is a small map of `path → last-seen-time`. When an event arrives, the handler checks:
have we seen this path within the debounce window? If yes, skip it; if no (or never), record the time
and let it through. A periodic cleanup drops entries older than ~10× the debounce window so the map
doesn't grow forever. The effect: a file being written fires many events, but the rule runs once, after
it goes quiet.

Each watched directory is registered with an optional **list of allowed rule names**, stored against
the directory's *canonicalized* path. When a file event fires, the watcher finds which watched
directory the file belongs to using **longest-prefix matching** on canonical paths (so nested watches
resolve to the most specific one), and only the rules allowed for that directory are evaluated. It
tries the raw event path first to avoid a syscall, falling back to canonicalizing only if needed (for
symlinked paths).

On `watch()`, it kicks off a **background initial scan** in a separate thread: walk the directory
(recursively if asked, skipping symlinks), and run each existing file through the rule engine — so
files already sitting in the folder get organized immediately, without blocking TUI startup. A files
that vanishes between the event and processing (a `NotFound`) is silently skipped — a common race. A
shared atomic counter tracks total files processed, and survives config reloads.

## The non-obvious parts

- **Debounce by "last seen", not a timer.** It doesn't wait a fixed delay then fire; it lets an event
  through only if the path has been quiet for the window. Cheap, and naturally collapses bursts.
- **Initial scan on a background thread.** Watching a folder also processes what's already in it — but
  off the main thread so the UI starts instantly.
- **Per-directory rule filtering via longest-prefix canonical matching.** Different folders can run
  different rule sets; nested watches pick the most specific one. Raw-path-first avoids a syscall per
  event.
- **Only Create/Modify matter.** Delete/rename-away events are ignored — you organize files that
  *appear*, not ones that leave.
- **NotFound races are expected and skipped.** Files often disappear between the event and processing;
  that's a debug log, not an error.
- **Symlinks are skipped during the scan** to avoid cycles and double-processing.
- **The map is self-limiting** — cleanup keeps it from growing without bound on a busy folder.

## Related
- [[file-rules-engine--from-hazelnut]] (each event/file is run through this)
- [[file-actions-executor--from-hazelnut]] (what runs when a rule matches)
- [[queue-backed-crawl--from-firecrawl]] (a different "process things as they appear" model: queue+Redis vs OS events+debounce)
- See also: [[realtime]] peers.
