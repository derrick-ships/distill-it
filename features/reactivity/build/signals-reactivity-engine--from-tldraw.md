# Signals Reactivity Engine (build spec) — distilled from tldraw

## Summary
Build a fine-grained, pull-based reactive system with three primitives — **atom** (mutable source),
**computed** (lazy, cached, auto-tracking derived value), and **react/reactor** (auto-tracking
side-effect) — coordinated by a single global **epoch** counter. Dependencies are discovered by
observing which signals are `.get()`-ed during a derivation/effect. Staleness is decided by
comparing epochs, not by diffing values. Optionally, signals carry a fixed-size **history buffer of
diffs** so consumers can ask "what changed since epoch N?" — this is the hook the record store and
sync layer hang off. Roughly 1–2k LOC; no runtime dependencies.

## Core logic (inlined)

### Global state (singleton)
```ts
const GLOBAL_START_EPOCH = -1
let globalEpoch = GLOBAL_START_EPOCH + 1     // ticks only on real atom change
let globalIsReacting = false                 // true while effects are flushing
let currentTransaction: Transaction | null = null
let captureStack: CaptureStackFrame | null = null   // top of dependency-capture stack

function advanceGlobalEpoch() { globalEpoch++ }
function getGlobalEpoch() { return globalEpoch }
```

### Signal interface
```ts
interface Signal<Value, Diff = unknown> {
  name: string
  get(): Value                                   // reads + registers as dependency
  __unsafe__getWithoutCapture(ignoreErrors?: boolean): Value   // reads, no dependency registration
  lastChangedEpoch: number
  getDiffSince(epoch: number): RESET_VALUE | Diff[]
  children: ArraySet<Child>                       // dependents (computeds + effects)
}
// RESET_VALUE = unique symbol meaning "history doesn't go back that far; recompute from scratch"
```

### Atom
```ts
class _Atom<Value, Diff> implements Signal<Value, Diff> {
  current: Value
  lastChangedEpoch = getGlobalEpoch()
  children = new ArraySet<Child>()
  historyBuffer?: HistoryBuffer<Diff>            // present iff options.historyLength given
  isEqual: ((a: Value, b: Value) => boolean) | null
  computeDiff?: (a: Value, b: Value, lastEpoch: number) => Diff

  get(): Value { maybeCaptureParent(this); return this.current }
  __unsafe__getWithoutCapture() { return this.current }

  set(value: Value, diff?: Diff): Value {
    if (this.isEqual?.(this.current, value) ?? equals(this.current, value)) return this.current
    advanceGlobalEpoch()
    if (this.historyBuffer) {
      this.historyBuffer.pushEntry(
        this.lastChangedEpoch, getGlobalEpoch(),
        diff ?? this.computeDiff?.(this.current, value, this.lastChangedEpoch) ?? RESET_VALUE)
    }
    const prev = this.current
    this.current = value
    this.lastChangedEpoch = getGlobalEpoch()
    atomDidChange(this, prev)        // transaction stash OR flush effects
    return value
  }

  update(fn: (v: Value) => Value) { return this.set(fn(this.current)) }
  getDiffSince(epoch: number) { /* read from historyBuffer or RESET_VALUE */ }
}

function atom<V, D = unknown>(name: string, initial: V,
  opts?: { historyLength?: number; computeDiff?: ComputeDiff<V,D>; isEqual?: (a:V,b:V)=>boolean }) {
  return new _Atom(name, initial, opts)
}
```

### Dependency capture (the auto-tracking magic)
```ts
class CaptureStackFrame {
  offset = 0
  maybeRemoved?: Signal<any>[]
  constructor(public below: CaptureStackFrame | null, public child: Computed | EffectScheduler) {}
}

function startCapturingParents(child) {
  captureStack = new CaptureStackFrame(captureStack, child)
  child.parentSet.clear()          // ArraySet of parents, rebuilt each run
  // child.parents[] and child.parentEpochs[] are reused/overwritten via offset
}

function maybeCaptureParent(p: Signal) {           // called inside every .get()
  const frame = captureStack
  if (!frame) return                                // not inside a derivation/effect → no tracking
  const child = frame.child
  if (frame.child.parentSet.has(p)) return          // already captured this run
  child.parentSet.add(p)
  if (child.isActivelyListening) attach(p, child)   // register child in p.children
  const idx = frame.offset
  if (child.parents[idx] !== p) {                   // reorder/replace bookkeeping
    if (child.parents[idx]) (frame.maybeRemoved ??= []).push(child.parents[idx])
    child.parents[idx] = p
  }
  child.parentEpochs[idx] = p.lastChangedEpoch      // <-- stamp the epoch we saw this parent at
  frame.offset++
}

function stopCapturingParents() {
  const frame = captureStack!
  // any parent no longer in parentSet gets detached; truncate arrays to frame.offset
  child.parents.length = frame.offset
  child.parentEpochs.length = frame.offset
  captureStack = frame.below
}

function haveParentsChanged(child): boolean {       // the cheap staleness check
  for (let i = 0; i < child.parents.length; i++) {
    // reading parent's CURRENT epoch may itself recompute a computed parent (lazy chain)
    child.parents[i].__unsafe__getWithoutCapture(true)
    if (child.parents[i].lastChangedEpoch !== child.parentEpochs[i]) return true
  }
  return false
}
```

### Computed (lazy + cached)
```ts
class _Computed<Value, Diff> implements Signal<Value, Diff> {
  lastCheckedEpoch = GLOBAL_START_EPOCH
  lastChangedEpoch = GLOBAL_START_EPOCH
  parents: Signal[] = []; parentEpochs: number[] = []; parentSet = new ArraySet()
  children = new ArraySet<Child>()
  state: Value | UNINITIALIZED = UNINITIALIZED
  error?: { thrownValue: any }
  historyBuffer?: HistoryBuffer<Diff>
  get isActivelyListening() { return !this.children.isEmpty }

  __unsafe__getWithoutCapture(ignoreErrors?): Value {
    const isNew = this.lastChangedEpoch === GLOBAL_START_EPOCH
    if (!isNew && (this.lastCheckedEpoch === getGlobalEpoch() || !haveParentsChanged(this))) {
      this.lastCheckedEpoch = getGlobalEpoch()
      if (this.error && !ignoreErrors) throw this.error.thrownValue
      return this.state as Value
    }
    try {
      startCapturingParents(this)
      const result = this.derive(this.state, this.lastCheckedEpoch)   // user fn; may return WithDiff
      const newState = result instanceof WithDiff ? result.value : result
      const changed = isNew || !(this.isEqual?.(this.state, newState) ?? equals(this.state, newState))
      if (changed) {
        if (this.historyBuffer && !isNew) {
          const d = result instanceof WithDiff ? result.diff
                    : this.computeDiff?.(this.state, newState, this.lastCheckedEpoch) ?? RESET_VALUE
          this.historyBuffer.pushEntry(this.lastChangedEpoch, getGlobalEpoch(), d)
        }
        this.lastChangedEpoch = getGlobalEpoch()
        this.state = newState
      }
      this.lastCheckedEpoch = getGlobalEpoch()
      this.error = undefined
      return this.state as Value
    } catch (e) {
      this.error = { thrownValue: e }; this.lastCheckedEpoch = getGlobalEpoch()
      if (!ignoreErrors) throw e
      return this.state as Value
    } finally { stopCapturingParents() }
  }

  get(): Value { const v = this.__unsafe__getWithoutCapture(); maybeCaptureParent(this); return v }
}

function computed(name, deriveFn, opts?) { return new _Computed(name, deriveFn, opts) }
// also a @computed method decorator (TC39 + legacy) that lazily creates one _Computed per instance.
```

### Effects (react / reactor)
```ts
class EffectScheduler<Result> {
  parents: Signal[] = []; parentEpochs: number[] = []; parentSet = new ArraySet()
  lastReactedEpoch = GLOBAL_START_EPOCH
  private _isActivelyListening = false
  scheduleEffect?: (execute: () => void) => void   // optional custom scheduler (e.g. rAF batching)

  attach() { this._isActivelyListening = true; for (const p of this.parents) attach(p, this) }
  detach() { this._isActivelyListening = false; for (const p of this.parents) detach(p, this) }

  maybeScheduleEffect() {
    if (!this._isActivelyListening) return
    if (this.lastReactedEpoch === getGlobalEpoch()) return
    if (this.parents.length && !haveParentsChanged(this)) { this.lastReactedEpoch = getGlobalEpoch(); return }
    if (this.scheduleEffect) this.scheduleEffect(() => this.execute())
    else this.execute()
  }

  execute(): Result {
    try { startCapturingParents(this)
      const r = this.runEffect(this.lastReactedEpoch)   // user fn; receives last epoch
      this.lastReactedEpoch = getGlobalEpoch()
      return r
    } finally { stopCapturingParents() }
  }
}

function react(name, fn, opts?): () => void {        // returns stop()
  const scheduler = new EffectScheduler(name, fn, opts)
  scheduler.attach(); scheduler.execute()             // run once immediately to capture deps
  return () => scheduler.detach()
}
function reactor(name, fn, opts?) { /* same but returns { start, stop, scheduler } */ }
```

### Transactions (batching + rollback)
```ts
class Transaction {
  parent: Transaction | null
  initialAtomValues = new Map<_Atom, any>()    // first-seen value per atom, for rollback
  get isRoot() { return this.parent === null }

  commit() {
    if (globalIsReacting) { /* traverse touched atoms for cleanup */ }
    else if (this.isRoot) flushChanges(this.initialAtomValues.keys())
    else for (const [a, v] of this.initialAtomValues)            // merge into parent
      if (!this.parent!.initialAtomValues.has(a)) this.parent!.initialAtomValues.set(a, v)
  }
  abort() {
    advanceGlobalEpoch()
    for (const [a, v] of this.initialAtomValues) a.set(v)        // roll back
    this.commit()
  }
}

function transaction<T>(fn: (rollback: () => void) => T): T {
  const txn = new Transaction(currentTransaction); currentTransaction = txn
  let rolledBack = false
  try { const r = fn(() => rolledBack = true); rolledBack ? txn.abort() : txn.commit(); return r }
  catch (e) { txn.abort(); throw e }
  finally { currentTransaction = txn.parent }
}
function transact<T>(fn: () => T): T {            // reuse existing txn if any
  return currentTransaction ? fn() : transaction(fn)
}

function atomDidChange(atom: _Atom, prev: any) {
  if (currentTransaction) {
    if (!currentTransaction.initialAtomValues.has(atom))
      currentTransaction.initialAtomValues.set(atom, prev)       // stash for rollback
  } else if (globalIsReacting) {
    traverseAtomForCleanup(atom)
  } else {
    flushChanges([atom])                                          // not in txn → flush now
  }
}

function flushChanges(atoms: Iterable<_Atom>) {
  globalIsReacting = true
  try {
    const reactors = new Set<EffectScheduler>()
    for (const a of atoms) a.children.visit(c => collectReactors(c, reactors))
    for (const r of reactors) r.maybeScheduleEffect()
    // then drain cleanupReactors set until empty, hard depth cap ~1000 to catch infinite loops
  } finally { globalIsReacting = false }
}
```

### Support data structures
- **`ArraySet`**: a Set that stays a plain array below ~8 elements (cheaper for the small
  parent/child sets that dominate), auto-promoting to a real `Set` above the threshold. Exposes
  `add/remove/has/visit/isEmpty`.
- **`HistoryBuffer<Diff>`**: fixed-size ring buffer of `{ fromEpoch, toEpoch, diff }`. `getChangesSince(epoch)`
  concatenates diffs newer than `epoch`, or returns `RESET_VALUE` if `epoch` predates the buffer.
- **`equals(a,b)`**: `Object.is` plus an opt-in `a.equals(b)` if the value implements it.

## Data contracts
```ts
type ComputeDiff<V, D> = (prev: V, next: V, lastComputedEpoch: number) => D | RESET_VALUE
type AtomOptions<V, D>     = { historyLength?: number; computeDiff?: ComputeDiff<V,D>; isEqual?(a:V,b:V): boolean }
type ComputedOptions<V, D> = AtomOptions<V, D>
type EffectSchedulerOptions = { scheduleEffect?(execute: () => void): void }
// WithDiff<V,D>: wrapper a computed/atom can return to supply an explicit diff alongside the value.
```

## Dependencies & assumptions
- Zero runtime dependencies. Pure TypeScript/JavaScript; runs in any JS environment.
- Single-threaded assumption (the global epoch + capture stack are module-level singletons).
- React binding (`@tldraw/state-react`) is a thin layer: `useValue(signal)` subscribes a component
  via `useSyncExternalStore` driven by a `react()` effect; `track(Component)` wraps render in a
  captured effect so any signal read during render re-renders the component. The core is
  framework-agnostic — the React layer is swappable.

## To port this, you need:
- [ ] A module-level singleton for `globalEpoch`, `currentTransaction`, and the capture stack
      (or an explicit context object threaded through, if you need multi-instance isolation).
- [ ] The `ArraySet` (or just use `Set` — slower but correct) and a ring-buffer for history.
- [ ] `.get()` on every signal must call `maybeCaptureParent(this)`; the derivation/effect runner
      must bracket with `startCapturingParents`/`stopCapturingParents`.
- [ ] An equality hook (default `Object.is`) — getting this wrong causes either missed updates or
      infinite re-renders.
- [ ] A scheduler seam on effects if you want frame-batched UI (otherwise effects run synchronously).
- [ ] (Optional but high-value) diff/history support on atoms+computeds if a store or sync layer
      will consume "what changed since epoch N."

## Gotchas
- **Always advance the epoch BEFORE writing the value and reading `getGlobalEpoch()` for
  `lastChangedEpoch`** — order matters; the new value must be stamped with the new epoch.
- **Equality short-circuit is load-bearing.** If `set()` doesn't bail on equal values, the epoch
  ticks needlessly and the whole graph re-checks. If a computed doesn't bail on equal results, its
  children recompute for nothing. Both are correctness-adjacent perf cliffs.
- **`haveParentsChanged` must read each parent's *current* epoch**, which can force a lazy parent
  computed to recompute first (the chain is pull-based). Calling `__unsafe__getWithoutCapture(true)`
  inside the check is deliberate: refresh the parent *without* capturing it as a new dependency.
- **Re-capture parents every run.** Don't cache the dependency list — data-dependent branches
  (`cond ? a.get() : b.get()`) need the deps to change run-to-run. Detach parents dropped this run
  or you leak (the computed stays subscribed to signals it no longer reads).
- **Effects only schedule when actively listening.** A `react()` that's been stopped (detached)
  must not fire. `maybeScheduleEffect` checks `_isActivelyListening` and `lastReactedEpoch` first.
- **Transaction rollback stashes the *first* value seen per atom**, not every intermediate. Stash on
  first touch only (`if (!initialAtomValues.has(atom))`).
- **Infinite-loop guard:** effects that mutate atoms they depend on can cascade forever; keep a hard
  depth cap (~1000) in the flush loop and throw a descriptive error.
- **Throwing computeds:** cache the thrown error and re-throw on next read unless `ignoreErrors`,
  so an error doesn't silently become a stale value.

## Origin (reference only)
Repo: https://github.com/tldraw/tldraw — package `@tldraw/state` (`packages/state/src/lib/`):
`Atom.ts`, `Computed.ts`, `EffectScheduler.ts`, `capture.ts`, `transactions.ts`, `HistoryBuffer.ts`,
`ArraySet.ts`, `types.ts`. React bindings in `@tldraw/state-react` (`useValue`, `track`,
`useStateTracking`). Published standalone as the `signia`-lineage reactivity core.
