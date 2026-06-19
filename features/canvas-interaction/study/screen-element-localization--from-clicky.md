# Screen Element Localization — from [clicky](https://github.com/farzaa/clicky)

> Domain: [[_domain]] · Source: https://github.com/farzaa/clicky · NotebookLM:

## What it does
Given a screenshot of the user's display and a spoken question ("how do I add a project?"), clicky figures out the exact on-screen pixel where the relevant UI element lives — a button, link, menu item, field, icon — and returns a single point in macOS screen coordinates. If the question is purely conceptual ("what does HTML mean?") and there is no element to point at, it returns nothing. That returned point is what the animated blue pointer then flies to and points at.

## Why it exists
clicky is a voice "learning buddy" that watches your screen and physically guides you. To guide you it has to know *where* on the screen the thing you should click actually is. Plain vision models are notoriously bad at returning accurate pixel coordinates. Anthropic's Computer Use beta, however, was specifically trained to count pixels and emit click coordinates, so clicky borrows that machinery — not to control the computer, but purely as a very accurate "point at this" detector.

## How it actually works
1. A screenshot of one display arrives (JPEG/PNG), along with that display's size in points.
2. Instead of always squishing the image to the classic 1024x768 (4:3), clicky picks whichever Anthropic-recommended Computer Use resolution is closest in aspect ratio to the real display: **1024x768 (4:3), 1280x800 (16:10, most Macs), or 1366x768 (~16:9)**. Matching the aspect ratio avoids distorting the image, which would wreck horizontal accuracy.
3. The screenshot is resized to exactly those pixel dimensions and re-encoded as JPEG at quality 0.85.
4. It POSTs to the Claude Messages API declaring the `computer` tool at the chosen resolution, with a beta header that switches on the pixel-counting training. The prompt tells Claude to "click" the relevant element, or to answer with plain text if there is no specific element.
5. Claude replies with a `tool_use` block containing `{"action":"left_click","coordinate":[x,y]}`. clicky reads the coordinate. If Claude replied with text instead, that means "no element" and clicky returns nothing.
6. The raw coordinate (in the resized image's space, top-left origin) is clamped to the valid range, scaled back up to the real display's point dimensions, and finally **flipped on the Y axis** because Computer Use uses a top-left origin while macOS/AppKit uses a bottom-left origin. The result is a single point ready to hand to the pointer animation.

## The non-obvious parts
- **The Retina trap.** The single biggest gotcha. If you resize using the obvious `NSImage.lockFocus()` path, a Retina (2x) display silently produces a bitmap at *double* the size you asked for — a "1280x800" image is really 2560x1600 pixels. Claude would then count pixels in a 2x space while you told the tool the display was 1280x800, so every coordinate comes back wrong. clicky sidesteps this by drawing into an `NSBitmapImageRep` created at exact pixel dimensions.
- **Aspect-ratio matching beats a fixed resolution.** Picking the closest-ratio resolution (rather than always 4:3) measurably improves X accuracy because the image is never stretched.
- **Two coordinate flips happen, not one.** First Computer Use's top-left → AppKit's bottom-left, and separately a screenshot-pixel → display-point scale. Getting either backwards puts the pointer in the wrong place.
- **Clamping matters.** Claude occasionally returns a coordinate a hair outside the declared dimensions; without clamping that maps to an off-screen point after scaling.
- **It's deliberately low-res.** Higher resolutions get downsampled by the API and *lose* precision, so the small declared sizes are a feature, not a limitation.

## Related
- [[animated-pointer-guidance--from-clicky]] (the point this returns is exactly what the blue pointer flies to and points at)
- [[media-processing/screen-capture-self-exclusion--from-clicky]] (provides the screenshot this consumes, with clicky's own window excluded)
- [[ai-integration/streaming-claude-screen-context--from-clicky]] (the sibling Claude call that produces the spoken answer; this one produces the location)
