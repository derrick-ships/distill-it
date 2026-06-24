# open-caffeine

- **Source:** https://github.com/sapsaldog/open-caffeine
- **What it is:** A native macOS menu-bar utility (Swift / SwiftUI, "Liquid Glass" design) that keeps a Mac awake for a chosen duration, with a countdown, battery-threshold cutoff, global hotkey, and Sparkle auto-updates. Notable for an exhaustive, coverage-gated test suite (22 test files, 100% line coverage on logic).
- **Distilled:** 2026-06-24

## Features extracted

| Domain | Feature | Study | Build |
|--------|---------|-------|-------|
| power-management | Power-Assertion Wake Lock | [study](../features/power-management/study/power-assertion-wake-lock--from-open-caffeine.md) | [build](../features/power-management/build/power-assertion-wake-lock--from-open-caffeine.md) |
| app-distribution | Sparkle EdDSA Auto-Update | [study](../features/app-distribution/study/sparkle-eddsa-autoupdate--from-open-caffeine.md) | [build](../features/app-distribution/build/sparkle-eddsa-autoupdate--from-open-caffeine.md) |
| testing-discipline | Coverage-Gated Testable Core | [study](../features/testing-discipline/study/coverage-gated-testable-core--from-open-caffeine.md) | [build](../features/testing-discipline/build/coverage-gated-testable-core--from-open-caffeine.md) |

## Why these three
The wake-lock is the repo's signature capability; the Sparkle pipeline and the coverage-gated testable-core architecture are the most reusable, repo-agnostic patterns. The testable-seam discipline (X) is exemplified directly by the wake-lock (Z).
