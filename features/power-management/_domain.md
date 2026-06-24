# Domain: power-management

Controlling the host operating system's power and sleep behaviour from an app: holding the machine (or just the display) awake, releasing cleanly, and tying that to timers, battery state, and user intent.

## What this domain is about
Some apps must stop the OS from sleeping while work happens: long downloads, presentations, builds, media playback. On macOS that means IOKit power assertions. The real engineering is making the acquire/release lifecycle leak-proof and testable, and driving it from policy (timed sessions, battery cutoffs, display-vs-system distinction) rather than ad-hoc calls.

## Key design principle
A power assertion is a held OS resource: every acquire must have a matching release, including on crash/deinit. Wrap the raw OS call behind a protocol seam so the lifecycle state machine is unit-testable without real hardware.

## Features in this domain
- [[power-assertion-wake-lock--from-open-caffeine]] — IOKit sleep-prevention behind a testable seam, with timed sessions and a battery-threshold cutoff.
