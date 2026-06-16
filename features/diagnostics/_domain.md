# Domain: diagnostics

Patterns for answering "is this actually working right now?" — health probing of external dependencies, survivable aggregation into a human/agent-readable report, and turning failures into actionable, specific fixes.

## What this domain is about

Tools that orchestrate many moving parts (external CLIs, services, providers) need a trustworthy, runtime answer to "what's healthy and what's broken." The hard part is that the cheap checks lie: a command on the PATH may not execute, a logged-out tool may exit non-zero while being perfectly installed. Diagnostics is about *executing real probes*, classifying failure precisely enough that the fix is unambiguous (install vs. reinstall vs. log-in vs. retry), aggregating without letting one bad component crash the report, and surfacing the result so both a human and an agent can act. A good diagnostic also rides security/correctness audits onto a command users already run.

## Core patterns

- **Execute, don't stat**: real health = run a side-effect-free command; file existence is not proof of usability (stale venv shebangs pass `which()`)
- **Precise failure taxonomy**: missing / broken / timeout / error / ok — each maps to a *different* repair, so don't collapse them
- **Survivable aggregation**: per-component `try/except` degrades to `error`; one misbehaving component never takes the whole report down (and stale state is cleared on error)
- **Side-effect-free + bounded retry**: retry only transient failures, only because probes are safe to repeat
- **Actionable output**: tiered grouping, "which backend is live" annotation only when there's a choice, one-line nudges for inactive optionals, and ride-along security audits (e.g. credential-file permissions)

## Features in this domain

- [[channel-health-diagnostics--from-agent-reach]] — `probe_command` (missing/broken/timeout/ok classification by real execution) + the `doctor` aggregator/report with tier grouping, active-backend annotation, and a credentials-permission audit
