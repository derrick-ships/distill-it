# Domain: graph-rendering

The pure geometry that turns "two points with facing directions" into a drawable SVG path between nodes — bezier curves, orthogonal step routes with rounded corners, and straight lines — plus where to place the edge label. No DOM, no framework, no state: just functions from numbers to an SVG `d` string.

## What this domain is about

Once a graph editor knows where two handles are (`sourceX/Y`, `targetX/Y`) and which way each faces (`Position.Left/Right/Top/Bottom`), it must draw a line that *leaves* the source in its facing direction, *arrives* at the target in its facing direction, and looks good. Three standard styles:

- **Bezier** — a single cubic curve; control points pushed out along each handle's facing direction by a curvature-scaled offset.
- **SmoothStep / Step** — an orthogonal (right-angle) route; SmoothStep rounds the corners with quadratic arcs, Step uses sharp corners (borderRadius = 0).
- **Straight** — a literal line; label at the midpoint.

Each returns `[pathString, labelX, labelY, offsetX, offsetY]`. These are the single highest-leverage transplant targets in xyflow: zero dependencies, ~150 lines, drop into any SVG canvas.

## Common patterns

- **Direction vectors.** Each `Position` maps to a unit vector; the path math is symmetric in those vectors.
- **Label at the curve center.** Bezier uses the t≈0.5 weighted average of the four control points; step uses the longest segment's midpoint.
- **Return offsets too.** `offsetX/offsetY` (distance from source to label) let callers size the label background box.

## Features in this domain

- [[edge-path-algorithms--from-xyflow]] — `getBezierPath`, `getSmoothStepPath`, `getStraightPath` and their label-position helpers, fully inlined
