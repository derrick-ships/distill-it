# Coverage-Gated Testable Core — from [open-caffeine](https://github.com/sapsaldog/open-caffeine)

> Domain: [[_domain]] · Source: https://github.com/sapsaldog/open-caffeine · NotebookLM: <add link>

## What it does
Guarantees that a desktop app's logic is fully tested, automatically. A tiny menu-bar utility ships with 22 test files and a rule: every logic file must hit 100% line coverage, and a git hook blocks any push that drops below it. The result is a UI app you can refactor fearlessly.

## Why it exists
"Add tests later" never happens, and coverage numbers quietly rot. The deeper problem is that GUI code feels untestable: logic is smeared across SwiftUI views and OS calls. This project's answer is a discipline, not a tool: make the logic testable by design, then make falling below 100% literally block a push, so the bar can't erode.

## How it actually works
Two halves: an architecture that makes logic testable, and a gate that enforces it.

The architecture rule is "extract the decision, quarantine the glue." Anything that touches the OS (IOKit power assertions, battery reads, Sparkle, login-item registration, hotkeys) is reduced to a 3-5 line adapter that just forwards to the system API, behind a small protocol. All the actual branching — when to acquire, countdown math, battery-threshold compares, settings parsing, icon-style selection — lives in plain structs/enums with no UI or OS imports. In tests, the protocol is filled by a fake, so the logic runs with no hardware. The SwiftUI view bodies stay declarative ("logic lives in the model"); they hold no decisions worth testing.

The gate is a script. It regenerates the project, runs the test suite with coverage on, dumps the coverage report as JSON, and pipes it to a small Python checker. The checker walks every source file, skips a hand-maintained EXCLUDE set of shells (each line carries a comment justifying why it's exempt), and fails if any remaining file is below 100%. Two honesty features make the exclude-list trustworthy: a new source file is NOT exempt by default (it must be tested or consciously added to the list), and the checker flags any EXCLUDE entry that no longer matches a real file (so the list can't accumulate stale lies). A git pre-push hook simply runs this script, so a push that would drop coverage is rejected before it leaves the machine.

## The non-obvious parts
- **The exclude-list is the real artifact.** 100% coverage is trivially gamed by excluding things; the discipline is the curated, commented, self-policing EXCLUDE set. It names exactly the code the team chose not to test and why.
- **Protocol seams exist for testability first, swappability second.** `PowerAssertionAPI`, `BatteryProvider`, `SleepAssertionProviding` aren't there for alternate implementations — they exist so a fake can stand in for the OS.
- **Default-deny on new files.** The gate's power is that adding an untested file fails the push; you can't silently lower the bar.
- **Stale-exclusion detection.** Flagging exclude entries that match no file stops the list from rotting into "everything is excluded."
- **The hook makes it social-proof-free.** No one has to remember to run coverage; the push won't go without it (and there's a documented escape hatch for emergencies).

## Related
- [[power-assertion-wake-lock--from-open-caffeine]] — the clearest worked example of the seam-and-test pattern.
- [[provider-agnostic-llm--from-llm-scraper]], [[email-provider-abstraction--from-inbox-zero]] — the same "behind an interface" move, there for vendor-swap, here for testability.
