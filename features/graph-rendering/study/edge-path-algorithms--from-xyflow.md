# Edge Path Algorithms — from [xyflow](https://github.com/xyflow/xyflow)

> Domain: [[_domain]] · Source: https://github.com/xyflow/xyflow · NotebookLM: <link once added>

## What it does

These are the small math functions that decide what an edge *looks like* — the curvy line, the right-angled "step" line, or the straight line connecting two nodes — and where to put the label that sits on it. Give them the start point, the end point, and which side of each node the line leaves from, and they hand back an SVG path string plus a good spot for the label.

## Why it exists

An edge isn't just "draw a line from A to B." A good-looking edge *leaves* a node from the correct side and *arrives* at the other node from the correct side, curving or stepping gracefully in between. A line that shoots straight through the node body, or leaves from the wrong edge, looks broken. These functions encode the taste — how much to curve, where to bend, how to round corners — that makes a diagram look professional. They're also pure and dependency-free, which is why they're the most copied part of the whole library.

## How it actually works

Everything keys off two facing **directions**. Each handle has a `Position` (Left, Right, Top, Bottom), and each maps to a unit vector pointing *out* of the node. The line should leave the source along its vector and enter the target along its.

**Bezier** (the default, curvy style): it builds a cubic curve with two control points. Each control point is pushed out from its handle along that handle's facing direction. How far? If the two nodes are "facing each other nicely" (positive distance), it's half the gap. If they're awkwardly placed (the target is *behind* the source's facing direction, a negative distance), it uses a curvature-scaled square-root formula so the curve bulges out and loops around gracefully instead of kinking. The label goes at the visual center of the curve, computed as a weighted blend of the four points (the classic "midpoint of a cubic bezier" weights: ⅛, ⅜, ⅜, ⅛).

**SmoothStep / Step** (right-angle style): instead of a curve it routes an orthogonal path — only horizontal and vertical segments. It first pushes a small "gap" segment straight out of each handle (so the line doesn't start flush against the node), then figures out the corner points needed to connect them. If the handles face opposite ways it splits the route at a midpoint (the `stepPosition`, default halfway); if they face the same way or perpendicular, it picks the corner arrangement that doesn't double back. Then it walks the corner points and, at each one, draws a small rounded arc (a quadratic curve) whose radius is the `borderRadius` — but never bigger than half the shorter adjacent segment, so corners never overshoot. Set `borderRadius` to 0 and you get sharp-cornered "Step" edges. The label sits on the longest segment's midpoint.

**Straight**: literally a line from A to B, label at the midpoint. Trivial, included for completeness.

Each function returns the same shape: `[pathString, labelX, labelY, offsetX, offsetY]`. The two offsets are how far the label is from the source — handy for sizing a little background box behind the label text.

## The non-obvious parts

- **The negative-distance curvature trick.** When a node's target is *behind* its facing direction (you'd have to draw backwards), a naive control offset makes an ugly cusp. The `curvature * 25 * sqrt(-distance)` formula deliberately throws the control point further out so the edge makes a smooth loop. This one line is most of why React Flow edges look nice.
- **Label position is the bezier's true midpoint, not the chord's.** Using the ⅛/⅜/⅜/⅜ weights gives the point *on the curve* at t≈0.5, so the label sits on the line, not floating beside it.
- **Corner radius is clamped to half the segment.** Rounded corners are capped so a short segment between two bends can't produce an arc bigger than the segment itself (which would look like a tangle).
- **The "gap" before the first corner.** Step edges offset a few pixels straight out of the handle before turning, so the line visibly emerges perpendicular from the node rather than immediately angling — a small touch that reads as "intentional."
- **Pure functions, zero state.** No DOM, no React, no store. That's deliberate: they're usable in any renderer, server-side, in tests, anywhere. It's why they transplant so cleanly.
- **`stepPosition` is adjustable.** The default mid-route bend can be slid toward either end, useful when many parallel edges would otherwise overlap their corners.

## Related

- [[connection-handles--from-xyflow]] — the live "wire" during a connect drag is drawn with these same functions
- [[node-dragging--from-xyflow]] — moving a node changes the endpoints fed into these functions every frame
- See also: D3's link generators, GoJS/JointJS routers — same family of problems, different taste knobs
