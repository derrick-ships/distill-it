# Kanban Pipeline (drag-and-drop) — from [auto-crm](https://github.com/Hainrixz/auto-crm)

> Domain: [[_domain]] · Source: https://github.com/Hainrixz/auto-crm (`src/components/pipeline/`, `src/app/api/pipeline/route.ts`) · NotebookLM: <add link>

## What it does
It's the visual sales board: vertical columns, one per pipeline stage (Prospect → Contacted →
Proposal → Negotiation → Won / Lost), each holding cards for the deals currently in that stage. You
drag a deal card from one column to another to advance (or demote) it, and the move sticks — the
board updates instantly under your hand and saves to the database in the background. It's the
spatial, tactile way to manage a pipeline that spreadsheets can't match: you *see* where the money
is bunched up and physically push deals forward.

## Why it exists
Salespeople think in pipelines, and a pipeline is inherently spatial — "what's stuck in
Negotiation?" is a question you answer by looking, not querying. The job-to-be-done is **make stage
management feel direct**: moving a deal forward should be one drag, not a form with a dropdown. The
drag-and-drop board is table stakes for a modern CRM (Pipedrive, HubSpot all have it); shipping it
well — instant, never-janky, never-loses-your-change — is what makes the product feel real rather
than a toy.

## How it actually works
The board is built on `@dnd-kit`, a React drag-and-drop library. The whole board sits inside a
`DndContext` configured with a pointer sensor that requires an 8-pixel drag before it "activates" —
this distinguishes a real drag from an accidental click, so tapping a card to open it doesn't get
mistaken for a move. Collision detection uses "closest corners," which feels natural when dropping a
card between others.

The interaction is built around **optimistic updates with rollback**, which is the heart of why it
feels good:

1. **On drag start**, it records which deal is being dragged and takes a *snapshot* of the entire
   board's current state — this snapshot is the undo card it keeps in its back pocket.
2. **During the drag** (`onDragOver`), it moves the card between columns in local state immediately,
   so the UI reflows in real time as you hover over a new column. Nothing has hit the server yet;
   this is pure perceived-performance.
3. **On drop** (`onDragEnd`), it fires a `PUT /api/pipeline` with just the deal id and the target
   stage id. The server validates the deal exists and updates its `stageId` and timestamp.
4. **If that save fails**, it restores the pre-drag snapshot and shows a toast: "Error moving the
   deal. The change was reverted." So a failed network call never leaves the board lying about where
   a deal is — it visibly snaps back.

A `DragOverlay` renders a floating copy of the card under the cursor while dragging, so the card
looks "picked up" rather than just sliding. The same `PUT /api/pipeline` endpoint does double duty:
with `{ dealId, stageId }` it's a single move; with a `{ stages }` array it reconfigures the whole
pipeline (rename/reorder/recolor stages) — but that bulk reconfigure is only allowed when there are
no deals yet, to avoid orphaning deals whose stage just got deleted.

## The non-obvious parts
- **Optimistic-with-snapshot is the whole trick.** Most of the perceived quality comes from updating
  local state immediately and keeping a full board snapshot to roll back to on failure. The user
  never waits for the server to see their drag land, but also never ends up with a lie on screen.
- **The 8px activation distance is a real UX decision.** Without it, every click on a card would
  start a drag and feel twitchy; with it, clicks and drags are cleanly separated. Small number, big
  feel difference.
- **One endpoint, two jobs, guarded by a precondition.** `PUT /api/pipeline` moves a single deal
  *or* replaces the whole stage set — and the destructive whole-replace is blocked if any deals
  exist. That guard prevents the "you reconfigured stages and now deals point at nothing" disaster.
- **Optimistic move happens in `onDragOver`, not `onDragEnd`.** The card visibly changes columns
  while you're still holding it, not only when you let go — which is what makes the reflow feel live.
- **Rollback is total, not field-level.** It restores the entire snapshotted board, so even a
  complex multi-column hover sequence cleanly reverts on a failed save.
- **Default stages are seeded, with explicit won/lost flags.** The init script creates six stages
  with colors and `isWon`/`isLost` booleans, so analytics (conversion rate) and the board both know
  which columns are terminal outcomes.

## Related
- [[crm-dashboard-kpis--from-auto-crm]] — consumes the same pipeline/stage data to compute pipeline
  value and conversion; the board is the editor, the dashboard is the readout.
- [[mcp-crm-server--from-auto-crm]] — `crm_move_deal` and `crm_get_pipeline` are the conversational
  equivalents of dragging a card / reading the board.
- [[node-dragging--from-xyflow]] — same domain, harder problem: dnd-kit gives you list/column DnD
  out of the box, whereas xyflow hand-rolls free-canvas dragging on d3-drag with snap and auto-pan.
- See also: any Trello/Pipedrive-style board — same optimistic-DnD pattern.
