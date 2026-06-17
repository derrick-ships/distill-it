# Connection Handles / drag-to-connect (build spec) — distilled from xyflow

## Summary

Implement "press a handle, drag a live wire, drop on a valid handle to create an edge." Unlike pan/drag this does **not** use d3 — it manages raw pointer/touch listeners on `document` (or shadow host). Core entry `XYHandle.onPointerDown(event, params)`. Each move: convert pointer→world, find the closest handle within `connectionRadius` (geometry) BUT prioritize the handle under the cursor (`elementFromPoint`), validate (strict/loose + self-loop block + custom predicate), and stream an in-progress connection to the renderer. On release, fire `onConnect(connection)` if valid. Includes auto-pan and a drag threshold.

## Core logic (inlined)

### onPointerDown — sets up the gesture
```ts
function onPointerDown(event, p) {
  const doc = getHostForElement(event.target);   // document OR shadow-root host (web-component safe)
  let closestHandle = null, autoPanId = 0, autoPanStarted = false, connectionStarted = false;
  let connection = null, isValid = false, resultHandleDomNode = null;

  const { x, y } = getEventPosition(event);                 // screen coords at press
  const handleType = getHandleType(p.edgeUpdaterType, p.handleDomNode); // 'source' | 'target'
  const containerBounds = p.domNode?.getBoundingClientRect();
  const fromHandleInternal = getHandle(p.nodeId, handleType, p.handleId, p.nodeLookup, p.connectionMode);
  if (!containerBounds || !handleType || !fromHandleInternal) return;

  let position = getEventPosition(event, containerBounds); // screen px relative to container

  const fromHandle = { ...fromHandleInternal, nodeId: p.nodeId, type: handleType };
  const fromNode = p.nodeLookup.get(p.nodeId);
  const from = getHandlePosition(fromNode, fromHandle, Position.Left, true); // world anchor of wire start

  let previous = {            // the in-progress connection object streamed to the renderer
    inProgress: true, isValid: null,
    from, fromHandle, fromPosition: fromHandle.position, fromNode,
    to: position, toHandle: null, toPosition: oppositePosition[fromHandle.position],
    toNode: null, pointer: position,
  };

  function startConnection() {
    connectionStarted = true;
    p.updateConnection(previous);
    p.onConnectStart?.(event, { nodeId: p.nodeId, handleId: p.handleId, handleType });
  }
  if (p.dragThreshold === 0) startConnection();

  doc.addEventListener('mousemove', onPointerMove); doc.addEventListener('mouseup', onPointerUp);
  doc.addEventListener('touchmove', onPointerMove); doc.addEventListener('touchend', onPointerUp);
  // ... onPointerMove / onPointerUp below
}
```

### onPointerMove — threshold, closest-handle, validate, stream
```ts
function onPointerMove(event) {
  if (!connectionStarted) {                       // DRAG THRESHOLD (screen px, squared compare)
    const { x: ex, y: ey } = getEventPosition(event);
    const dx = ex - x, dy = ey - y;
    if (dx*dx + dy*dy <= p.dragThreshold * p.dragThreshold) return;
    startConnection();
  }
  const transform = p.getTransform();
  position = getEventPosition(event, containerBounds);

  // 1) geometric closest handle within radius (world space)
  closestHandle = getClosestHandle(
    pointToRendererPoint(position, transform, false, [1,1]), p.connectionRadius, p.nodeLookup, fromHandle);

  if (!autoPanStarted) { autoPan(); autoPanStarted = true; }

  // 2) validate — DOM hit-test PRIORITIZED over geometric closest
  const result = isValidHandle(event, {
    handle: closestHandle, connectionMode: p.connectionMode, fromNodeId: p.nodeId,
    fromHandleId: p.handleId, fromType: p.isTarget ? 'target' : 'source',
    isValidConnection: p.isValidConnection, doc, lib: p.lib, flowId: p.flowId, nodeLookup: p.nodeLookup });

  connection = result.connection;
  isValid = isConnectionValid(!!closestHandle, result.isValid);

  const newConn = {
    ...previous,
    from: getHandlePosition(p.nodeLookup.get(p.nodeId), fromHandle, Position.Left, true),
    isValid,
    to: result.toHandle && isValid                     // snap to handle if valid, else follow cursor
      ? rendererPointToPoint({ x: result.toHandle.x, y: result.toHandle.y }, transform)
      : position,
    toHandle: result.toHandle,
    toPosition: isValid && result.toHandle ? result.toHandle.position : oppositePosition[fromHandle.position],
    toNode: result.toHandle ? p.nodeLookup.get(result.toHandle.nodeId) : null,
    pointer: position,
  };
  p.updateConnection(newConn);
  previous = newConn;
}
```

### isValidHandle — DOM-priority hit-test + rules
```ts
function isValidHandle(event, c) {
  const isTarget = c.fromType === 'target';
  // the handle element we computed by distance (may be null)
  const handleDomNode = c.handle
    ? c.doc.querySelector(`.${c.lib}-flow__handle[data-id="${c.flowId}-${c.handle.nodeId}-${c.handle.id}-${c.handle.type}"]`)
    : null;

  const { x, y } = getEventPosition(event);
  const handleBelow = c.doc.elementFromPoint(x, y);          // <-- the handle physically under the cursor
  // PRIORITY: handle under cursor wins over distance-closest
  const handleToCheck = handleBelow?.classList.contains(`${c.lib}-flow__handle`) ? handleBelow : handleDomNode;

  const result = { handleDomNode: handleToCheck, isValid: false, connection: null, toHandle: null };
  if (!handleToCheck) return result;

  const handleType   = getHandleType(undefined, handleToCheck);
  const handleNodeId = handleToCheck.getAttribute('data-nodeid');
  const handleId     = handleToCheck.getAttribute('data-handleid');
  const connectable    = handleToCheck.classList.contains('connectable');
  const connectableEnd = handleToCheck.classList.contains('connectableend');
  if (!handleNodeId || !handleType) return result;

  // direction-normalized connection (canonical source->target)
  const connection = {
    source:       isTarget ? handleNodeId : c.fromNodeId,
    sourceHandle: isTarget ? handleId     : c.fromHandleId,
    target:       isTarget ? c.fromNodeId : handleNodeId,
    targetHandle: isTarget ? c.fromHandleId : handleId,
  };
  result.connection = connection;

  const isConnectable = connectable && connectableEnd;
  const valid = isConnectable && (
    c.connectionMode === ConnectionMode.Strict
      ? (isTarget && handleType === 'source') || (!isTarget && handleType === 'target')  // strict: dir enforced
      : handleNodeId !== c.fromNodeId || handleId !== c.fromHandleId                     // loose: just no self-loop
  );
  result.isValid  = valid && c.isValidConnection(connection);   // user predicate last word
  result.toHandle = getHandle(handleNodeId, handleType, handleId, c.nodeLookup, c.connectionMode, true);
  return result;
}
```

### onPointerUp — commit or cancel
```ts
function onPointerUp(event) {
  if ('touches' in event && event.touches.length > 0) return;   // ignore until last finger lifts
  if (connectionStarted) {
    if ((closestHandle || resultHandleDomNode) && connection && isValid) p.onConnect?.(connection); // CREATE EDGE
    const { inProgress, ...state } = previous;
    const final = { ...state, toPosition: previous.toHandle ? previous.toPosition : null };
    p.onConnectEnd?.(event, final);
    if (p.edgeUpdaterType) p.onReconnectEnd?.(event, final);     // reconnection variant
  }
  p.cancelConnection(); cancelAnimationFrame(autoPanId);
  doc.removeEventListener('mousemove', onPointerMove); doc.removeEventListener('mouseup', onPointerUp);
  doc.removeEventListener('touchmove', onPointerMove); doc.removeEventListener('touchend', onPointerUp);
}
```

### getClosestHandle (geometry)
```ts
// iterate connectableEnd handles in nodeLookup; keep the one whose center is nearest the pointer
// AND within connectionRadius; skip the from-handle's own node per connectionMode.
function getClosestHandle(pointerWorld, radius, nodeLookup, fromHandle) {
  let closest = null, minDist = Infinity;
  for (const node of nodeLookup.values()) {
    for (const handle of [...(node.internals.handleBounds?.source ?? []),
                          ...(node.internals.handleBounds?.target ?? [])]) {
      const cx = node.internals.positionAbsolute.x + handle.x + handle.width/2;
      const cy = node.internals.positionAbsolute.y + handle.y + handle.height/2;
      const d = Math.hypot(cx - pointerWorld.x, cy - pointerWorld.y);
      if (d <= radius && d < minDist) { minDist = d; closest = { ...handle, nodeId: node.id, x: cx, y: cy }; }
    }
  }
  return closest;
}
```

## Data contracts

```ts
enum Position { Left='left', Top='top', Right='right', Bottom='bottom' }
const oppositePosition = { left:'right', right:'left', top:'bottom', bottom:'top' };
enum ConnectionMode { Strict='strict', Loose='loose' }

type Connection = { source: string; sourceHandle: string|null;
                    target: string; targetHandle: string|null };

type ConnectionInProgress = {
  inProgress: true; isValid: boolean|null;
  from: XYPosition; fromHandle: Handle; fromPosition: Position; fromNode: InternalNode;
  to: XYPosition; toHandle: Handle|null; toPosition: Position; toNode: InternalNode|null;
  pointer: XYPosition;
};

type OnPointerDownParams = {
  connectionMode: ConnectionMode; connectionRadius: number;
  handleId: string|null; nodeId: string; isTarget: boolean;
  edgeUpdaterType?: 'source'|'target';                 // set when reconnecting an existing edge
  domNode: Element; nodeLookup: Map<string, InternalNode>; lib: string; flowId: string;
  autoPanOnConnect: boolean; autoPanSpeed?: number; dragThreshold?: number; // default 1
  panBy(d: XYPosition): void; cancelConnection(): void; updateConnection(c): void;
  getTransform(): Transform; getFromHandle(): Handle|null;
  isValidConnection?(c: Connection): boolean;          // default () => true
  onConnectStart?; onConnect?; onConnectEnd?; onReconnectEnd?;
  handleDomNode?: Element|null;
};
```

DOM contract the handles MUST satisfy (the hit-test reads these):
- class `${lib}-flow__handle`, plus dynamic classes `connectable` and `connectableend`.
- attributes `data-nodeid`, `data-handleid`, and a `data-id="${flowId}-${nodeId}-${handleId}-${type}"`, and a class identifying type (`source`/`target`).

## Dependencies & assumptions

- No d3. Just pointer/touch + `document.elementFromPoint`.
- A node lookup carrying per-node `handleBounds` (positions+sizes of each handle in node-local coords) and absolute node position.
- The viewport transform + `panBy` for auto-pan ([[pan-zoom-canvas--from-xyflow]]).
- A place to store the in-progress connection (`updateConnection`/`cancelConnection`) and a renderer that draws it ([[edge-path-algorithms--from-xyflow]]).
- `getHostForElement` to support shadow DOM (falls back to `document`).

## To port this, you need:

- [ ] Handle DOM elements carrying the classes + `data-*` attributes above (the validity check reads the DOM, not just geometry).
- [ ] `handleBounds` per node so `getClosestHandle` can measure distances.
- [ ] A transient connection-state slot + a renderer for the live wire and final edge.
- [ ] Decide strict vs loose `connectionMode` and supply `isValidConnection` for app rules (e.g. type compatibility, max-1-incoming).
- [ ] Viewport transform + `panBy` if you want auto-pan to off-screen targets.

## Gotchas

- **DOM hit-test must win over geometric closest** — without `elementFromPoint` priority the wire snaps to neighbors when you're clearly aiming at one dot.
- **Listen on `document`/shadow host, not the node** — the pointer leaves the node immediately; node-scoped listeners drop the gesture.
- **Both `connectable` AND `connectableend`** classes required on the target, so apps can disable drop targets live.
- **Normalize the connection direction** before emitting, so the app always gets canonical `source→target` regardless of which end you grabbed.
- **Multitouch guard on pointerup** (`touches.length > 0` → ignore) prevents a second finger from committing early.
- **`isConnectionValid(hasCloseHandle, ruleValid)`**: invalid (red wire) only matters when there's actually a candidate handle; in empty space it's neither valid nor invalid (`null`).
- **Drag threshold uses squared distance** to skip a sqrt; default 1px so a plain click doesn't draw a phantom wire.

## Origin (reference only)

- `packages/system/src/xyhandle/XYHandle.ts` — `onPointerDown`, `isValidHandle`.
- `packages/system/src/xyhandle/utils.ts` — `getClosestHandle`, `getHandle`, `getHandleType`, `isConnectionValid`.
- `packages/system/src/utils/` — `getEventPosition`, `getHostForElement`, `getHandlePosition`, `pointToRendererPoint`, `rendererPointToPoint`, `calcAutoPan`.
- Repo: https://github.com/xyflow/xyflow (MIT).
