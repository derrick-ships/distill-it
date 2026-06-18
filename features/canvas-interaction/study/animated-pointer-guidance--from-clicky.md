# Animated Pointer Guidance — from [clicky](https://github.com/farzaa/clicky)

> Domain: [[_domain]] · Source: https://github.com/farzaa/clicky · NotebookLM:

## What it does
clicky paints a little glowing blue triangle "buddy" on top of everything on your screen. Normally it trails your mouse cursor with a soft springy lag. When clicky figures out where the element you asked about is, the buddy peels away from the cursor and *flies* there along a graceful curved arc — leaning into the direction of travel and pulsing larger mid-flight — then arrives, points at the element, and shows a speech bubble. When it's done it flies back to following your cursor. This is the part of clicky people fall in love with: it feels like a tiny character physically walking you to the answer.

## Why it exists
A voice assistant that says "click the button in the top right" is forgettable. A character that visibly *swoops over and points at the exact button* is delightful and unambiguous. The arc, the lean, and the size-pulse exist purely to make a cursor feel alive and intentional rather than teleporting. It is the visible payoff of the (invisible) coordinate detection.

## How it actually works
- **A transparent click-through window per display.** clicky puts a borderless, fully transparent `NSWindow` over each screen at the screen-saver window level, with mouse events ignored so it never steals clicks. It rides along across all Spaces and full-screen apps. One window per monitor; each hosts a SwiftUI `BlueCursorView`.
- **Following mode.** A 60Hz timer reads the global mouse location and parks the buddy a little down-and-right of the cursor (offset +35x, +25y). A gentle spring animation gives it the trailing-lag feel.
- **The flight.** When the detected element's location arrives (a published property the view watches), the buddy switches to "navigating" mode and runs a hand-rolled, timer-driven **quadratic Bézier arc**: it computes a control point lifted *above* the midpoint of start→end, so the path bows upward like a thrown object. Flight time scales with distance (0.6s–1.4s). Smoothstep easing makes it ease-in-ease-out. The triangle continuously rotates to face the tangent of the curve (so it always "leans" the way it's going), and a sine pulse swells it up to 1.3x at the arc's midpoint before settling back.
- **Arrival & return.** On arrival it points and shows a bubble, then later flies back. During the *return* flight only, if you jiggle the mouse more than 100px it cancels and snaps back to following you. During the *forward* flight it ignores you and finishes the gesture.
- **Tying to detection.** The detector returns a display-local bottom-left point; clicky converts that to a global screen point (adding the display's frame origin), then each per-screen view converts the global point into its own SwiftUI top-left local space before flying. A small offset (+8x, +12y) and screen-edge clamping (20px padding) keep the buddy *beside* the element, not on top of it.

## The non-obvious parts
- **The window can never become key or main.** Both are overridden to return false, so the overlay is purely decorative and never grabs focus — essential for a click-through HUD.
- **Two different animation systems coexist.** Following uses SwiftUI's implicit `.spring(response: 0.2, dampingFraction: 0.6)`. The flight bypasses SwiftUI animation entirely and drives `cursorPosition` frame-by-frame with a `Timer` at 1/60s, because it needs precise control of position, rotation, and scale together along a curve. The view's `.animation(...)` is deliberately set to `nil` while navigating so SwiftUI doesn't fight the manual updates.
- **Coordinate origin flips twice on the way in.** macOS screen coords are bottom-left; SwiftUI within the window is top-left; the per-screen converter does `y = (frame.origin.y + frame.height) - screenPoint.y` and subtracts the frame origin for x.
- **Multi-monitor is handled by geometry, not routing.** Every screen has its own overlay and its own `BlueCursorView`. Each view only reacts if the detected element's display frame belongs to *its* screen, so the buddy flies on the correct monitor.
- **The "lean."** Rotation comes from the analytic tangent (derivative) of the Bézier curve, plus a +90° offset to orient the triangle's nose. This is why it looks like it's banking into the turn.
- **The glow scales with the pulse.** The shadow radius grows with `buddyFlightScale`, so the buddy visibly brightens as it accelerates mid-arc.
- **It politely waits to disappear.** When disabled, it doesn't vanish instantly — a background task waits for TTS playback to stop and for the pointed-at location to clear, pauses a beat, then fades out over 0.4s with ease-in.

## Related
- [[screen-element-localization--from-clicky]] (produces the target point this flies to; this feature is its visible output)
- [[media-processing/screen-capture-self-exclusion--from-clicky]] (the overlay must be excluded from capture so the buddy isn't screenshotted and fed back to Claude)
- [[ai-integration/streaming-claude-screen-context--from-clicky]] (the speech bubble text shown on arrival comes from the same answer pipeline)
