# Scene Reconciliation — from [excalidraw](https://github.com/excalidraw/excalidraw)

> Domain: [[_domain]] · Source: https://github.com/excalidraw/excalidraw · NotebookLM: 

## What it does

When two people draw on the same Excalidraw board at once, both clients are constantly sending each other their version of the scene. Reconciliation is the rule that decides, element by element, *whose version wins* when a local copy and an incoming remote copy disagree — and it does so in a way that always lands every client on the **same** final picture, no matter what order the messages arrived in. It's how Excalidraw stays consistent across collaborators without a central server arbitrating every edit and without a heavyweight CRDT engine.

## Why it exists

Real-time collaboration has a hard problem: the network reorders and delays messages, so two clients can briefly hold different states. You need a merge function that is **deterministic** (same inputs → same output on every machine) and **convergent** (everyone ends up identical). The fully-general answer is a CRDT, but CRDTs are complex, memory-hungry, and overkill for a whiteboard where conflicts are rare and "last edit wins per shape" is perfectly acceptable. Excalidraw's bet: model each *element* as the unit of conflict, give it a version clock, and resolve ties with a random-but-deterministic number. It's a few dozen lines instead of a CRDT library, and it's good enough because two people rarely edit the *same shape* at the same instant.

## How it actually works

Every element carries two numbers that make merging possible:
- **`version`** — a plain counter that goes up by one every time the element is mutated. Think of it as "how many edits has this shape seen." Higher version = more recent = more authoritative.
- **`versionNonce`** — a random integer regenerated on every mutation. Its only job is to break ties when two versions are equal.

When a remote scene arrives, Excalidraw walks the remote elements and, for each one, looks up the matching local element by `id`. Then it asks one question: *should I discard the remote version and keep my local one?* The answer is yes if **any** of these hold:

1. **I'm actively editing this element right now** — it's the text I'm typing into, the shape I'm resizing, or the shape I'm in the middle of drawing. The user's live interaction always wins; you never want a network message to yank a shape out from under someone's cursor.
2. **My local version is newer** (`local.version > remote.version`).
3. **Versions are tied, and my versionNonce is lower-or-equal** (`local.version === remote.version && local.versionNonce <= remote.versionNonce`).

That third rule is the quiet genius. When two clients both edited a shape to the same version count, you need a tiebreaker that *every* client computes the same way. Comparing the random nonces — "lowest nonce wins" — does exactly that: it's arbitrary but identical everywhere, so all clients independently pick the same winner. No coordination needed.

Elements present locally but absent from the remote message are simply kept (they're edits the remote hasn't seen yet). The result is a single merged list containing every element exactly once.

Finally, the merged list is **sorted by fractional index** (the elements' z-order keys), and any broken or missing ordering keys are repaired. Reconciliation produces not just "the right elements" but "the right elements in the right stacking order" — because two clients must also agree on what's on top of what.

The same merge runs in two places: on each client when a peer's update arrives, and on the **server-side save** — before Excalidraw persists a scene to Firebase, it reconciles the incoming elements against whatever was already stored, inside a transaction, so a save can't clobber a concurrent collaborator's work.

## The non-obvious parts

- **It's last-write-wins *per element*, not per scene.** Two people editing two different shapes never conflict — both edits survive. Conflict only exists when the *same* shape is touched, which is rare.
- **The tiebreaker is randomness used deterministically.** `versionNonce` looks like noise but is the thing that lets uncoordinated clients converge. The rule "lowest nonce wins on equal version" is computed identically everywhere, so there's no need for a server to decide.
- **Active-editing state overrides version math entirely.** Even if a remote element is "newer," if you're currently typing in or resizing the local one, the local one is kept. UX trumps the clock.
- **`<=` not `<` in the tie rule matters.** Using less-than-or-equal makes the comparison total and symmetric — there's never an "equal nonce, no decision" gap that could let two clients diverge.
- **Reconciliation also fixes z-order.** Merging the *set* of elements isn't enough; the *order* must converge too, which is why fractional indices are re-sorted and repaired as the last step.
- **No operational transforms, no CRDT.** Excalidraw broadcasts whole elements (or deltas of changed elements), not operations. The merge is stateless given the two element lists. This is dramatically simpler than OT/CRDT and is the reason a small team can maintain it.

## Related

- [[fractional-indexing--from-excalidraw]] (the z-order keys reconciliation sorts and repairs at the end)
- [[e2e-encrypted-collaboration--from-excalidraw]] (the transport that delivers the remote elements this merges)
- [[hand-drawn-rendering--from-excalidraw]] (`versionNonce` is reused as the render cache key)
- See also: CRDT-based tools (Figma's fractional-index + LWW, Yjs/Automerge) solve the same problem with heavier machinery.
