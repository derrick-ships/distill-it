# Signals Reactivity Engine — from [tldraw](https://github.com/tldraw/tldraw)

> Domain: [[_domain]] · Source: https://github.com/tldraw/tldraw (`packages/state`, `@tldraw/state`) · NotebookLM: <add link>

## What it does
It's a small, fast, dependency-free reactivity library — tldraw's home-grown answer to MobX or
Solid's signals. You wrap a piece of mutable state in an **atom**, you derive read-only values
from it with **computed**, and you run side-effects with **react**. When an atom changes, every
computed and effect that *actually read it* recalculates — and nothing else does. It's the
invisible nervous system underneath the whole tldraw editor: the moment a shape's position atom
changes, exactly the parts of the canvas that depend on that shape re-render, and nothing else.

Two things make it more than "just signals": it tracks a **global logical clock** (an "epoch") so
it can answer "has anything I depend on changed since the last time I looked?" in O(1), and atoms
can keep a **history buffer of diffs**, so a consumer can ask "what *specifically* changed since
epoch N?" rather than just "did something change?". That diff-history capability is what makes the
reactive store and the multiplayer sync layer possible.

## Why it exists
An infinite canvas app has tens of thousands of interdependent values — shape positions, camera,
selection, derived geometry, rendered DOM. Recomputing everything on every pointer-move would be
unusable; manually wiring "when X changes update Y" would be unmaintainable. tldraw needed
fine-grained reactivity where the dependency graph is **discovered automatically** by simply
watching which signals get read during a computation, and where staleness checks are nearly free.

They didn't use MobX because they needed two things off-the-shelf libraries don't give cheaply:
(1) a globally-ordered notion of time (the epoch) so the store can compute precise diffs between
any two points, and (2) signals that carry their own *change history as diffs*, not just their
current value. Those two features are the seed from which the store, queries, undo/redo, and the
sync protocol all grow. The job-to-be-done: "make derived state automatic, surgical, and
diff-aware."

## How it actually works
There's one global counter called the **epoch** (`globalEpoch`). Every time any atom is set to a
new value, the epoch ticks up by one. Think of it as a clock that only advances when *something*
in the system changes. Every signal remembers two timestamps on this clock: the epoch when it was
**last checked** and the epoch when it **last changed**.

**Atoms** are the only true source of state. Setting an atom: first checks equality (if the new
value equals the old, it's a no-op — nothing ticks); otherwise it advances the global epoch,
records the new `lastChangedEpoch`, optionally pushes a *diff* into a fixed-size history buffer,
stores the value, and notifies its children.

**Computeds** are lazy and cached. A computed doesn't recalculate when its inputs change — it
recalculates when someone *reads it* and its inputs have actually changed. The clever part is how
it decides. When a computed runs its derivation function, the library brackets that execution with
"start capturing parents" / "stop capturing parents." Every signal that gets `.get()`-ed during
the derivation is automatically recorded as a parent, **along with the epoch that parent was at**.
Next time the computed is read, it does a cheap check: if the global epoch hasn't moved at all
since it was last checked, return the cache instantly. Otherwise it walks its recorded parents and
asks each "is your `lastChangedEpoch` newer than the epoch I recorded for you?" — that's
`haveParentsChanged`. If no parent actually moved, it bumps its own `lastCheckedEpoch` and returns
the cache without recomputing. Only if a parent genuinely changed does it re-run the derivation.

This is the whole trick: **automatic dependency capture by observation, plus epoch-stamped parents
for near-free staleness checks.** Dependencies are re-captured every run, so they can change shape
dynamically (a computed that reads atom A on Tuesday and atom B on Wednesday just works).

**Effects (react/reactor)** are computeds that exist to *do* something rather than return a value.
They capture parents the same way. When a parent changes, the effect is *scheduled* (not
necessarily run immediately) — and you can supply a custom scheduler, e.g. "batch all my effects
into the next `requestAnimationFrame`," which is exactly how tldraw avoids re-rendering 100 times
during a single drag gesture.

**Transactions** batch changes. Inside `transact(fn)`, all the atom mutations happen, but effects
don't flush until the outermost transaction commits. Transactions also enable **rollback**: when a
transaction starts touching an atom, it stashes that atom's value first; if the transaction throws
or is explicitly aborted, every touched atom is reset to its stashed value. That's the foundation
of "try this change; undo it cleanly if it fails."

## The non-obvious parts
- **The epoch is the master stroke.** One integer that only advances on real change turns "is my
  cache stale?" from a graph traversal into an integer comparison in the common case
  (`lastCheckedEpoch === globalEpoch` → definitely fresh, return immediately).
- **Diffs live in the signals, not bolted on top.** An atom can carry a `computeDiff` function and
  a `historyLength`, so it stores not just "the value changed" but "*here's the patch*." Computeds
  can produce diffs too. This is why the store can later say "give me exactly what changed between
  epoch 5 and epoch 9" — the history buffers already hold it. Most signal libraries throw this
  information away.
- **Lazy + cached + auto-captured is a hard combination.** Lazy means it won't waste work; cached
  means repeated reads are free; auto-captured means you never declare dependencies by hand. Doing
  all three correctly (without leaks, without stale reads, with dynamically-changing deps) is the
  bulk of the engineering.
- **Re-capturing parents every run is deliberate**, not wasteful. It's what lets the dependency
  graph be data-dependent (branchy derivations). Parents that are no longer read get detached so
  they stop holding the computed alive.
- **Effects don't run themselves — they get scheduled.** Decoupling "something changed" from "do
  the work" is what makes frame-batched rendering possible. The reactivity core stays synchronous
  and predictable; the *timing* is a pluggable policy.
- **Equality short-circuits everywhere.** Set an atom to an equal value → no epoch tick → no
  cascade. A computed that recomputes to an equal result → `lastChangedEpoch` doesn't move → its
  own children don't recompute. Change stops propagating the instant it stops mattering.

## Related
- [[reactive-record-store]] — built directly on this; records live in atoms, queries are computeds,
  the store's change-history is an atom with a diff buffer.
- [[schema-migrations]] — operates on the data this store holds.
- [[multiplayer-sync]] — consumes the store's epoch-stamped diffs to send minimal patches over the wire.
- See also: MobX, SolidJS signals, Preact signals, Vue reactivity — same family, but tldraw's epoch
  clock + diff-carrying signals are the distinguishing features.
