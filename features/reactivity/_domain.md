# reactivity — domain

**What this domain means across repos studied:** fine-grained reactive state systems — the
machinery that makes derived values and side-effects update *automatically and surgically* when
their inputs change, without the developer wiring dependencies by hand. The interesting engineering
lives in *dependency discovery* (how does the system know what depends on what?), *staleness
checking* (how cheaply can it decide whether to recompute?), and *change propagation* (batching,
scheduling, and — in the richest systems — carrying diffs of what changed, not just that it changed).

## Features filed here
| Feature | Repo | Study | Build |
|---------|------|-------|-------|
| Signals Reactivity Engine | tldraw | [study](study/signals-reactivity-engine--from-tldraw.md) | [build](build/signals-reactivity-engine--from-tldraw.md) |

## Mental model
A modern fine-grained reactive system has three primitives:
1. **Atom** — a mutable source of truth.
2. **Computed** — a lazy, cached, derived value that auto-tracks which atoms/computeds it reads.
3. **Effect** — a side-effect that re-runs when its tracked inputs change (often frame-batched).

The cleverness is in the bookkeeping: a **global epoch/clock** that ticks only on real change turns
"is my cache stale?" into an integer comparison, and **observing reads during execution** discovers
the dependency graph for free. The most powerful variants (tldraw's) also let signals carry a
**history of diffs**, so consumers can ask "what changed since clock N?" — the seed for stores,
undo/redo, and network sync.
