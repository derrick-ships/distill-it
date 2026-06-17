# Edge Path Algorithms (build spec) — distilled from xyflow

## Summary

Three pure, dependency-free functions that turn two points + their facing `Position`s into an SVG path `d` string and a label anchor: `getBezierPath` (cubic curve), `getSmoothStepPath` (orthogonal route with rounded corners; `borderRadius:0` ⇒ sharp "Step"), and `getStraightPath`. Each returns `[path, labelX, labelY, offsetX, offsetY]`. No DOM, no framework — drop into any SVG canvas. **`getBezierPath` is verbatim from source; smoothstep is reconstructed faithfully** (semantics + constants confirmed against source).

## Core logic (inlined)

### Shared
```ts
enum Position { Left='left', Top='top', Right='right', Bottom='bottom' }
```

### getBezierPath (VERBATIM)
```ts
function calculateControlOffset(distance, curvature) {
  if (distance >= 0) return 0.5 * distance;
  return curvature * 25 * Math.sqrt(-distance);   // the "loop-around gracefully" trick
}

function getControlWithCurvature({ pos, x1, y1, x2, y2, c }) {
  switch (pos) {
    case Position.Left:   return [x1 - calculateControlOffset(x1 - x2, c), y1];
    case Position.Right:  return [x1 + calculateControlOffset(x2 - x1, c), y1];
    case Position.Top:    return [x1, y1 - calculateControlOffset(y1 - y2, c)];
    case Position.Bottom: return [x1, y1 + calculateControlOffset(y2 - y1, c)];
  }
}

function getBezierEdgeCenter({ sourceX, sourceY, targetX, targetY,
                              sourceControlX, sourceControlY, targetControlX, targetControlY }) {
  // point on a cubic bezier at t=0.5  ->  weights 1/8, 3/8, 3/8, 1/8
  const centerX = sourceX*0.125 + sourceControlX*0.375 + targetControlX*0.375 + targetX*0.125;
  const centerY = sourceY*0.125 + sourceControlY*0.375 + targetControlY*0.375 + targetY*0.125;
  const offsetX = Math.abs(centerX - sourceX);
  const offsetY = Math.abs(centerY - sourceY);
  return [centerX, centerY, offsetX, offsetY];
}

function getBezierPath({ sourceX, sourceY, sourcePosition = Position.Bottom,
                        targetX, targetY, targetPosition = Position.Top, curvature = 0.25 }) {
  const [sCX, sCY] = getControlWithCurvature({ pos: sourcePosition, x1: sourceX, y1: sourceY, x2: targetX, y2: targetY, c: curvature });
  const [tCX, tCY] = getControlWithCurvature({ pos: targetPosition, x1: targetX, y1: targetY, x2: sourceX, y2: sourceY, c: curvature });
  const [labelX, labelY, offsetX, offsetY] = getBezierEdgeCenter({
    sourceX, sourceY, targetX, targetY, sourceControlX: sCX, sourceControlY: sCY, targetControlX: tCX, targetControlY: tCY });
  return [
    `M${sourceX},${sourceY} C${sCX},${sCY} ${tCX},${tCY} ${targetX},${targetY}`,
    labelX, labelY, offsetX, offsetY,
  ];
}
```

### getStraightPath (trivial)
```ts
function getStraightPath({ sourceX, sourceY, targetX, targetY }) {
  const [labelX, labelY, offsetX, offsetY] =
    [ (sourceX+targetX)/2, (sourceY+targetY)/2, Math.abs(targetX-sourceX)/2, Math.abs(targetY-sourceY)/2 ];
  return [`M${sourceX},${sourceY} L${targetX},${targetY}`, labelX, labelY, offsetX, offsetY];
}
```

### getSmoothStepPath (reconstructed — matches source semantics)
```ts
const handleDirections = {
  [Position.Left]:   { x: -1, y: 0 },
  [Position.Right]:  { x:  1, y: 0 },
  [Position.Top]:    { x:  0, y: -1 },
  [Position.Bottom]: { x:  0, y:  1 },
};

// rounded corner at point b between a and c (quadratic arc); size never exceeds half a segment
function getBend(a, b, c, size) {
  const bendSize = Math.min(distance(a, b) / 2, distance(b, c) / 2, size);
  const { x, y } = b;
  // straight-through (collinear) -> no bend
  if ((a.x === x && x === c.x) || (a.y === y && y === c.y)) return `L${x} ${y}`;
  if (a.y === y) {                         // horizontal into b, then vertical out
    const xDir = a.x < c.x ? -1 : 1, yDir = c.y < y ? -1 : 1;
    return `L ${x + bendSize * xDir},${y}Q ${x},${y} ${x},${y + bendSize * yDir}`;
  }
  const xDir = c.x < x ? -1 : 1, yDir = a.y < c.y ? -1 : 1;
  return `L ${x},${y + bendSize * yDir}Q ${x},${y} ${x + bendSize * xDir},${y}`;
}
const distance = (a, b) => Math.hypot(b.x - a.x, b.y - a.y);

function getPoints({ source, sourcePosition = Position.Bottom, target, targetPosition = Position.Top,
                    center, offset = 20, stepPosition = 0.5 }) {
  const sourceDir = handleDirections[sourcePosition];
  const targetDir = handleDirections[targetPosition];
  const sourceGapped = { x: source.x + sourceDir.x * offset, y: source.y + sourceDir.y * offset };
  const targetGapped = { x: target.x + targetDir.x * offset, y: target.y + targetDir.y * offset };
  const dir = getDirection({ source: sourceGapped, sourcePosition, target: targetGapped });
  const dirAccessor = dir.x !== 0 ? 'x' : 'y';     // primary routing axis
  const currDir = dir[dirAccessor];

  let points = [], centerX, centerY;
  const sourceGapPoint = { x: sourceGapped.x, y: sourceGapped.y };
  const targetGapPoint = { x: targetGapped.x, y: targetGapped.y };
  const gapX = Math.abs(targetGapped.x - sourceGapped.x);
  const gapY = Math.abs(targetGapped.y - sourceGapped.y);

  if (sourceDir[dirAccessor] * targetDir[dirAccessor] === -1) {   // OPPOSITE facing -> split route
    centerX = center?.x ?? sourceGapped.x + (targetGapped.x - sourceGapped.x) * stepPosition;
    centerY = center?.y ?? sourceGapped.y + (targetGapped.y - sourceGapped.y) * stepPosition;
    //          [verticalSplit]                                   [horizontalSplit]
    const verticalSplit   = [ {x:centerX, y:sourceGapped.y}, {x:centerX, y:targetGapped.y} ];
    const horizontalSplit = [ {x:sourceGapped.x, y:centerY}, {x:targetGapped.x, y:centerY} ];
    points = sourceDir[dirAccessor] === currDir ? verticalSplit : horizontalSplit;
  } else {                                                        // SAME / perpendicular
    const sourceTarget = [ { x: sourceGapped.x, y: targetGapped.y } ];
    const targetSource = [ { x: targetGapped.x, y: sourceGapped.y } ];
    points = (sourceDir[dirAccessor] === currDir)
      ? (dirAccessor === 'x' ? sourceTarget : targetSource)
      : (dirAccessor === 'x' ? targetSource : sourceTarget);
    if (sourcePosition === targetPosition) {  // same side: choose arrangement avoiding doubling back
      points = dirAccessor === 'x'
        ? (source.x <= target.x ? sourceTarget : targetSource)
        : (source.y <= target.y ? targetSource : sourceTarget);
    }
    centerX = points[0]?.x ?? (source.x + target.x)/2;
    centerY = points[0]?.y ?? (source.y + target.y)/2;
  }

  const pathPoints = [ source, sourceGapPoint, ...points, targetGapPoint, target ];
  return [pathPoints, centerX, centerY, gapX, gapY];
}

function getSmoothStepPath({ sourceX, sourceY, sourcePosition = Position.Bottom,
                            targetX, targetY, targetPosition = Position.Top,
                            borderRadius = 5, center = {}, offset = 20, stepPosition = 0.5 }) {
  const [points, labelX, labelY, offsetX, offsetY] = getPoints({
    source: { x: sourceX, y: sourceY }, sourcePosition,
    target: { x: targetX, y: targetY }, targetPosition,
    center, offset, stepPosition,
  });
  const path = points.reduce((res, p, i) => {
    let seg;
    if (i > 0 && i < points.length - 1) seg = getBend(points[i-1], p, points[i+1], borderRadius);
    else seg = `${i === 0 ? 'M' : 'L'}${p.x} ${p.y}`;
    return res + seg;
  }, '');
  return [path, labelX, labelY, offsetX, offsetY];
}
// getStepPath = getSmoothStepPath with borderRadius: 0
```

`getDirection` picks the dominant axis between the gapped source/target (sign of the larger delta), returning `{x:±1,y:0}` or `{x:0,y:±1}`.

## Data contracts

```ts
type GetBezierPathParams = { sourceX; sourceY; sourcePosition?: Position;
  targetX; targetY; targetPosition?: Position; curvature?: number /*0.25*/ };

type GetSmoothStepPathParams = { sourceX; sourceY; sourcePosition?: Position;
  targetX; targetY; targetPosition?: Position;
  borderRadius?: number /*5*/; center?: {x?:number;y?:number}; offset?: number /*20*/;
  stepPosition?: number /*0.5*/ };

// ALL return: [ path: string, labelX: number, labelY: number, offsetX: number, offsetY: number ]
```

Defaults that matter: `curvature 0.25`, `borderRadius 5`, `offset 20` (gap out of handle), `stepPosition 0.5` (mid-route bend), source default `Bottom`, target default `Top`.

## Dependencies & assumptions

- **None.** Pure functions of numbers → string. No d3, no DOM.
- Coordinates are whatever space you draw in (typically world/flow coords inside a `<g transform>`); the functions don't care.
- Caller supplies the handle anchor points and their `Position`. Those come from node geometry (size + handle side).

## To port this, you need:

- [ ] Source/target anchor coordinates and each handle's side (`Position`).
- [ ] An `<svg><path d={path}/>` (or canvas equivalent) to render the returned string.
- [ ] Optional: a label element placed at `labelX/labelY`, sized using `offsetX/offsetY`.
- [ ] Nothing else — copy the functions as-is.

## Gotchas

- **Curvature sign matters.** The `curvature*25*sqrt(-distance)` branch only triggers for negative distance (target behind the handle's facing direction). Drop it and back-facing edges develop ugly cusps.
- **Label uses the t=0.5 bezier weights (1/8,3/8,3/8,1/8)** — not the straight midpoint — so it sits *on* the curve. Don't "simplify" to the chord midpoint.
- **Clamp the corner radius to half the shorter adjacent segment** (`getBend`'s `Math.min`), or short segments produce arcs larger than themselves and the route tangles.
- **The 20px `offset` gap is load-bearing aesthetically** — it makes the line emerge perpendicular from the node. Zero offset looks like the line clips the node.
- **`borderRadius: 0` is how you get sharp Step edges** — there is no separate algorithm, Step === SmoothStep with radius 0.
- **Collinear points get an `L`, not a `Q`** in `getBend` — feeding a degenerate triangle to the quadratic would draw a kink.
- Positions default to `Bottom`/`Top`; if your nodes connect left↔right, pass `Right`/`Left` explicitly or the curve leaves the wrong side.

## Origin (reference only)

- `packages/system/src/utils/edges/bezier-edge.ts` — `getBezierPath`, `getBezierEdgeCenter` (verbatim above).
- `packages/system/src/utils/edges/smoothstep-edge.ts` — `getSmoothStepPath`, `getPoints`, `getBend`, `getDirection`.
- `packages/system/src/utils/edges/straight-edge.ts` — `getStraightPath`.
- Repo: https://github.com/xyflow/xyflow (MIT). These are exported publicly from `@xyflow/react` / `@xyflow/system`.
