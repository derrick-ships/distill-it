# Domain: testing-discipline

How a codebase makes itself provably tested: structuring code so the logic is testable, and enforcing a coverage bar automatically so it can't rot.

## What this domain is about
Most apps are "untestable" only because logic is tangled into UI and system calls. This domain is about the discipline that fixes that: push every decision into pure types behind protocol seams, quarantine the unavoidable OS/UI glue into thin shells, and gate merges/pushes on a coverage threshold computed over just the logic. The interesting part is the enforcement mechanism and the exclusion policy, not the tests themselves.

## Key design principle
100% coverage is only meaningful if you are honest about what is excluded. Keep a small, justified exclude-list of genuine shells; everything else must hit the bar; new files are not exempt by default. Enforce it with a hook so it is impossible to forget.

## Features in this domain
- [[coverage-gated-testable-core--from-open-caffeine]] — protocol-seam architecture + a 100%-line-coverage pre-push gate with a curated, self-policing exclude list.
