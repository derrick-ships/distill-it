# Change-Based Document Mutation Model — from [penpot](https://github.com/penpot/penpot)

> Domain: [[_domain]] · Source: https://github.com/penpot/penpot · NotebookLM:

## What it does

It's the rule that nobody ever edits the design file directly. Instead, every single edit — move a
rectangle, recolor it, add a page, rename a layer — is turned into a small, self-describing
*instruction* ("change") that gets applied to the file. The file is only ever modified by replaying
these instructions. That one discipline is what quietly powers undo/redo, saving, and two people
editing the same board at the same time.

## Why it exists

A design editor has to do several hard things at once: let you undo any action, save your work
incrementally (not re-upload the whole file every keystroke), and merge edits from multiple people
live. If edits were just direct mutations of the in-memory file, none of that would be tractable —
you'd have no record of *what* changed, no way to invert it, and nothing small to send over the
network. By making every edit a first-class, serializable instruction, Penpot gets all three for
free: undo is "apply the inverse instruction," save is "ship the list of instructions," and collab
is "broadcast the instructions and replay them on everyone's copy." It's the architectural decision
the rest of the product leans on.

## How it actually works

There are two halves: a **builder** that constructs instructions (with their inverses), and a
**processor** that applies them.

**Each edit is a "change" — a map tagged with a `:type`.** There's a fixed vocabulary of around
forty change types: `:add-obj`, `:mod-obj`, `:del-obj`, `:mov-objects`, `:reorder-children`,
`:add-page`/`:del-page`/`:mov-page`, `:reg-objects`, plus library changes (`:add-color`,
`:add-component`, `:add-typography`) and the whole design-tokens family (`:set-token`,
`:set-token-set`, `:set-token-theme`, …). A change carries everything needed to apply it: which page
or component, which object id, and the payload.

**Applying changes is a big dispatch table.** A `process-change` multimethod switches on `:type` and
knows how to fold each change into the file data. Applying a whole edit is just reducing the file
through its list of changes. Modifying a shape (`:mod-obj`) is itself a *sub*-list of fine-grained
**operations** — `:set` (set one attribute), `:set-touched` (mark a component copy as locally
edited), `:set-remote-synced` — so even "change these 3 properties" is a precise, replayable record
rather than a blob.

**The clever part: every forward change is built with its inverse.** When you build an edit you don't
just record "do X" — you record both "do X" (redo) and "undo X" at the same time, while you still
have the old values in hand. The builder keeps two tracks: `redo-changes` (a vector, appended in
order) and `undo-changes` (a list, *prepended* so it naturally reverses). Add an object → redo is
`:add-obj`, undo is `:del-obj`. Update a shape's attributes → redo records the new values, undo
records the prior values. So undo/redo isn't a separate system; it falls out of how edits are
constructed.

**Building reads from a snapshot of the file.** Before constructing changes you attach the current
objects to the builder (as metadata), so it can compute correct inverses (it needs the old shape to
know what to restore). The builder also applies changes to its own local copy as it goes, so a
sequence of edits sees the effects of earlier ones.

**Files carry a version and migrations.** Because the file format evolves, every file has a version
and there's a migration chain that upgrades old files to the current schema on load — the same
discipline (a list of ordered, replayable transformations) applied to the *format* itself. There's
also a validate/repair pass that checks structural integrity and fixes malformed data.

## The non-obvious parts

- **Undo/redo is emergent, not bolted on.** Because inverses are recorded at build time (when the
  old value is still available), there's no separate "undo stack of snapshots" — just the same change
  instructions, replayed backward. This is the highest-leverage idea in the whole model.
- **`redo` is a vector, `undo` is a list — on purpose.** Vectors append cheaply (forward order);
  lists prepend cheaply (reverse order). The data structure choice encodes the direction.
- **Operations inside `:mod-obj` keep edits surgical.** You never resend a whole shape to change its
  fill; you send `{:type :set :attr :fill :val ...}`. Tiny payloads = cheap network sync + tiny saves.
- **The same change list is the unit of *everything*** — undo, persistence, and realtime broadcast all
  consume the identical structure. Collaboration is "ship your changes, replay theirs," which is why
  it doesn't need a separate CRDT for most edits.
- **`:set-touched` exists because of components.** When you locally tweak a copy of a shared
  component, that attribute is marked "touched" so a later component update won't clobber your change —
  override tracking is modeled *as a change operation*, not a side table.
- **Migrations apply the same philosophy to the format.** Schema evolution is just another ordered,
  replayable list — consistent thinking top to bottom.

## Related

- [[native-design-tokens--from-penpot]] — same repo; token edits ride the very same change system (`:set-token*` change types)
- [[wasm-skia-render-engine--from-penpot]] — same repo; the renderer consumes the file state these changes produce
- [[reactive-record-store--from-tldraw]] — a different take on the same problem: a reactive store with typed records + diffs
- [[scene-reconciliation--from-excalidraw]] — how another tool merges concurrent edits into one scene
- [[schema-migrations--from-tldraw]] — the same "versioned, ordered migrations" idea for an evolving document format
- See also: event sourcing / command pattern — this is that, applied to a design document
