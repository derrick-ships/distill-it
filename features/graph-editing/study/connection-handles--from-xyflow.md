# Connection Handles (drag-to-connect) — from [xyflow](https://github.com/xyflow/xyflow)

> Domain: [[_domain]] · Source: https://github.com/xyflow/xyflow · NotebookLM: <link once added>

## What it does

Those little dots on the edge of a node are **handles**. Press one, drag, and a live wire follows your cursor; hover near another node's handle and the wire snaps to it and turns "valid" (or stays "invalid" if the connection isn't allowed); release on a valid handle and a new edge is born. It also powers *reconnecting* an existing edge by dragging its endpoint somewhere else.

## Why it exists

This is how users actually build the graph's *structure* — the edges. Dragging a node moves it; dragging from a handle wires two nodes together. Without a fluid, forgiving connect gesture (snap to nearby handles, clear valid/invalid feedback, rules about what can connect to what) building a flowchart would be miserable. The forgiveness — a generous snap radius, prioritizing the handle directly under the cursor — is what makes it feel good rather than fiddly.

## How it actually works

Unlike pan/zoom and drag, this one does **not** wrap a d3 module. It manages raw pointer/touch events itself, because the gesture is bespoke: it has to do live hit-testing against other handles every frame.

When you press a handle, `onPointerDown` fires. It figures out the "from" handle (which node, which handle id, is it a source or a target) and seeds an **in-progress connection** object — a transient bundle describing the wire being drawn: where it starts, where the cursor is, what (if anything) it's currently snapped to, and whether that's valid. It then attaches global `mousemove`/`mouseup` (and touch) listeners to the *document* (or the shadow-root host, so it works inside web components).

A small **drag threshold** means a click that barely moves doesn't start a connection — you have to drag a few pixels. Once you cross it, `onConnectStart` fires and the live wire appears.

On every move:
- It converts the pointer to world coordinates and asks `getClosestHandle` for the nearest handle within the **connection radius** (a snap distance). This is pure geometry over the node lookup.
- But it *also* does a DOM hit-test: `document.elementFromPoint()` at the cursor. If there's a handle element literally under the pointer, that one wins over the geometrically-closest one — because the dot your cursor is on top of is what you "mean," even if another dot's center happens to be a hair closer.
- It then validates: is this a real handle? In **strict mode**, only source→target (or target→source) is allowed — no source-to-source. Self-connections (same node+handle) are always blocked. Then a user-supplied `isValidConnection(connection)` predicate gets the final say.
- It updates the in-progress connection (new endpoint, snapped or free; valid flag; which node/handle it's over) and streams it to the renderer so the wire redraws and recolors.
- If the cursor nears the canvas edge, the same **auto-pan** rAF loop from dragging kicks in so you can connect to off-screen nodes.

On release (`onPointerUp`): if there's a valid snapped handle and a valid connection, `onConnect(connection)` fires — that's the app's cue to actually add the edge. Either way `onConnectEnd` fires with the final state (and `onReconnectEnd` if this was an edge-reconnection). All the global listeners are torn down and the in-progress state is cleared.

## The non-obvious parts

- **DOM hit-test beats geometry.** The handle under the cursor (`elementFromPoint`, checked via a CSS class) is prioritized over the closest-by-distance handle. This is the single most important "feel" decision — it stops the wire from snapping to a neighbor when you're clearly aiming at one specific dot.
- **It listens on the document, not the node.** Once a drag starts the mouse can go anywhere, including off the node and off the canvas; global listeners (on the shadow host if inside a web component) are required so the gesture survives.
- **Strict vs loose connection mode.** Strict enforces direction (source connects only to target). Loose lets any handle connect to any other handle on a different node. This is a product policy baked into the validity check.
- **The connection object is direction-normalized.** Whether you started from the source or target end, the emitted `{ source, sourceHandle, target, targetHandle }` is always oriented correctly, so the app always gets a canonical edge.
- **Reconnection reuses the same machinery.** Dragging an existing edge's endpoint is just a connection drag seeded with `edgeUpdaterType`; it fires `onReconnectEnd` instead of treating it as brand new.
- **Two CSS-class gates on the target:** a handle must be both `connectable` and `connectableend` to accept a drop — letting the app disable handles dynamically.
- **Multitouch guard on release:** if other touches remain, pointerup is ignored so a second finger doesn't prematurely commit.

## Related

- [[node-dragging--from-xyflow]] — sibling gesture; shares the auto-pan loop and pointer→world conversion but moves nodes instead of wiring them
- [[edge-path-algorithms--from-xyflow]] — the live wire and the final edge are drawn with these path functions
- [[reactive-store--from-xyflow]] — holds the in-progress `connection` state and the node lookup used for hit-testing
- See also: any node-editor "drag to connect" (Blender, Unreal Blueprints) — same closest-handle-with-DOM-priority idea
