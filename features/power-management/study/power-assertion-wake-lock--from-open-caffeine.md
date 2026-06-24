# Power-Assertion Wake Lock — from [open-caffeine](https://github.com/sapsaldog/open-caffeine)

> Domain: [[_domain]] · Source: https://github.com/sapsaldog/open-caffeine · NotebookLM: <add link>

## What it does
Keeps a Mac awake on demand. You pick a duration (5 min, an hour, custom, or Forever), the app holds the machine awake for exactly that long, shows a live countdown in the menu bar, and lets go on its own when the timer runs out or you stop it. It can keep just the system running while letting the screen sleep, or keep the display on too. It can also auto-stop when the battery drops below a threshold you set.

## Why it exists
macOS aggressively idles to save power. That is wrong during a long download, a build, a presentation, or a remote session. The job-to-be-done is "don't sleep while I'm doing this, but go back to normal the moment I'm done" — without leaving the machine awake forever because the app crashed or forgot to clean up.

## How it actually works
At the bottom is a single OS call: macOS lets an app register a "power assertion" that says "don't idle-sleep while I hold this." You create it, you get an id back, and you must release that id later or the Mac never sleeps again. open-caffeine treats that pair (create / release) as a tiny state machine wrapped in its own object: acquiring twice releases the old one first, releasing when nothing is held does nothing, and when the object is destroyed it releases automatically. That last bit is the safety net: even if everything else goes wrong, the assertion can't leak.

There are two flavours of assertion: one prevents the display from idling (which also keeps the system up — what people expect from "keep awake"), and one keeps only the system up while letting the screen sleep (good for unattended work). Which one is used is just a setting read at acquire time.

On top of the assertion sits a "session." Starting a session acquires the assertion, records what duration was chosen and when it started, and schedules a one-shot timer for the end. Stopping (by the user, by the timer firing, or by low battery) invalidates the timer and releases the assertion. The countdown shown in the menu bar is computed, not stored: given the start time and total duration, "remaining" is just total minus elapsed, clamped at zero; "Forever" sessions simply have no end.

The battery cutoff is a separate watcher. macOS can notify an app whenever a power source changes; on each change the watcher reads the current battery percentage and, if it is below the user's threshold, asks the session to stop. The watcher itself does no math beyond the threshold compare — reading the raw battery numbers is one isolated call, and turning those numbers into "has a battery, N percent" is pure parsing that is tested on its own.

## The non-obvious parts
- **The assertion is a resource, not an event.** The whole design is about guaranteeing release: re-acquire releases first, deinit releases, a failed IOKit release still flips the object to inactive so it never gets stuck "half held."
- **Display-sleep vs system-sleep is a real product choice.** "Keep display awake" and "keep system awake" are two different OS assertions; conflating them gives users the wrong behaviour for unattended tasks.
- **Everything OS-touching is a thin seam.** The actual IOKit calls live in a 4-line adapter with no logic; all the branching lives in plain objects that are unit-tested. That is why a sleep utility can have a near-exhaustive test suite.
- **The countdown is derived state.** Storing only start-time + duration and computing "remaining" on demand avoids a second source of truth that could drift from the timer.

## Related
- [[coverage-gated-testable-core--from-open-caffeine]] — the seam-and-test discipline this feature is the prime example of.
- [[provider-agnostic-llm--from-llm-scraper]] — the same "wrap the vendor/system behind a swappable protocol" idea, applied to LLMs.
