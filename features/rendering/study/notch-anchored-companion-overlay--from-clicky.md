# Notch-Anchored Companion Overlay — from [clicky](https://github.com/farzaa/clicky)

> Domain: [[_domain]] · Source: https://github.com/farzaa/clicky · NotebookLM:

## What it does
Clicky is a menu-bar-only macOS app (no Dock icon, no real window). It paints itself onto the screen in two completely different surfaces:

1. **A drop-down control panel** that appears _under the menu bar_ when you click the menu-bar icon. It's a small dark rounded card (Loom-style) holding the permission checklist, model picker, and Start button. It's "anchored to the notch area" in the everyday sense: it hangs directly beneath the menu bar icon, which on modern MacBooks lives in the same strip as the camera housing / notch.

2. **A full-screen, transparent, click-through overlay** that covers the _entire_ display — edge to edge, including the notch/housing region and the menu bar — on which a little glowing blue triangle "companion cursor" floats next to your real mouse pointer. This overlay is where the personality lives: the companion follows your cursor, says hi, flies off to point at on-screen elements, and shows the onboarding video.

## Why it exists
The author wanted a companion that feels like it lives _on top of your whole computer_, not inside a window. A normal app window can't draw over the menu bar or into the notch strip, can't span every Space, and would steal focus. To get a friendly always-present helper that never interrupts what you're doing, Clicky uses borderless transparent windows at very high window levels with mouse events disabled, so the blue cursor can appear anywhere — even up by the notch — without ever blocking a click.

## How it actually works
**The menu-bar dock.** An `NSStatusItem` (square length) is added to the system status bar with a hand-drawn triangle icon (the same rotated triangle as the companion cursor, so the menu-bar glyph matches the personality). Clicking it toggles a custom borderless `NSPanel`. The panel is positioned by reading the status item button's window frame and placing the panel just below it: horizontally centered on the icon, 4px gap under the menu bar, height auto-sized to the SwiftUI content. So the panel literally drops out of the menu bar / notch strip.

**Why a panel, not a popover.** The panel is a `.nonactivatingPanel` so it doesn't steal focus from whatever app you're in, but a custom `KeyablePanel` subclass overrides `canBecomeKey` to `true` so the email text field can still be typed into. It floats (`.level = .floating`), is fully transparent (`isOpaque = false`, clear background, no shadow at the window level — the shadow is drawn in SwiftUI), joins all Spaces, and survives full-screen apps. A global mouse monitor dismisses it on outside-click — with a deliberate 0.3s delay and an "are permissions still pending / is a system dialog up" guard so the panel doesn't vanish the instant macOS pops a permission prompt.

**The full-screen companion overlay.** A separate borderless `OverlayWindow` (one per screen) is sized to the whole `screen.frame`. It is `isOpaque = false`, `.clear` background, `level = .screenSaver` (above menus and the Dock), `ignoresMouseEvents = true` (pure click-through — you interact with apps underneath as if it weren't there), spans all Spaces and is `.stationary`, and refuses to become key or main so it never grabs focus. Inside it, a SwiftUI `BlueCursorView` uses `.ignoresSafeArea()` so its canvas extends fully into the notch/housing area and under the menu bar. The blue triangle is drawn at the live mouse position (offset +35x/+25y so it sits like a buddy beside the real cursor), updated by a 60fps timer reading `NSEvent.mouseLocation`. Because the overlay covers everything and ignores safe-area insets, the companion can rest or fly right up next to the notch with nothing clipping it.

**Multi-screen.** `OverlayWindowManager.showOverlay(onScreens:)` loops `NSScreen.screens` and creates one overlay window + one `BlueCursorView` per display. Each view checks `screenFrame.contains(NSEvent.mouseLocation)` every frame and only draws the cursor on the screen the mouse is actually on, converting global screen coordinates into per-screen SwiftUI (top-left origin, flipped Y) coordinates.

## The non-obvious parts
- **There is no literal notch-detection code.** Clicky does **not** read `safeAreaInsets`, `auxiliaryTopLeftArea`, or any "notch rectangle" API. The "housing/notch is used" effect comes from two design choices: (a) the control panel drops out of the menu-bar strip where the notch sits, and (b) the full-screen overlay deliberately `ignoresSafeArea()` and runs at `screenSaver` level so the companion can occupy the notch region instead of being pushed below it. The magic is "ignore the notch entirely and draw over it," not "measure the notch and dock to it."
- **Two different window levels for two jobs.** The panel is `.floating` (normal-ish, focusable card); the overlay is `.screenSaver` (above the menu bar, untouchable). Mixing these up would either let the panel get buried or make the overlay block clicks.
- **`KeyablePanel` exists only so the email field works** — a `.nonactivatingPanel` normally can't become key, which would make text input impossible.
- **The status-item icon is hand-drawn with `NSBezierPath`**, rotated 35°, `isTemplate = true` so macOS tints it for light/dark menu bars — matching the in-overlay companion triangle exactly.
- **Click-outside dismissal is intentionally laggy** (0.3s) and skips dismissal while permissions are ungranted and the app isn't active, so granting a permission (which raises a system dialog) doesn't accidentally close the setup panel.

## Related
- [[onboarding/first-launch-video-onboarding--from-clicky]] (the overlay surface here is exactly where the first-launch demo video and "hey! i'm clicky" intro are presented)
- [[canvas-interaction/animated-pointer-guidance--from-clicky]] (the blue triangle's fly-to-element / point-at-target behavior that lives inside this same overlay)
- [[media-processing/screen-capture-self-exclusion--from-clicky]] (the companion must not appear in its own screenshots — relevant because this overlay draws over everything)
