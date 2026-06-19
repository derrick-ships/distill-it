# Screen Capture with Self-Exclusion — from [clicky](https://github.com/farzaa/clicky)

> Domain: [[_domain]] · Source: https://github.com/farzaa/clicky · NotebookLM:

## What it does
Takes a still screenshot of every connected display and hands the images to an AI for context — but deliberately leaves out the app's own windows (its overlays, panels, and the floating cursor companion). The AI sees only the user's actual work: their editor, browser, terminal, etc., never the assistant talking to itself. Each screenshot is JPEG-compressed and tagged with a human-readable label like "screen 2 of 3 — cursor is on this screen (primary focus)" so the AI knows which monitor the user is actually looking at.

## Why it exists
clicky is a voice-driven on-screen helper. When it asks an AI "what is the user doing right now," it screenshots the desktop. If those screenshots included clicky's own overlay windows, the AI would see its own UI elements and get confused — reasoning about its own buttons instead of the user's content, or worse, entering a feedback loop describing itself. Excluding the app's own windows keeps the AI's view clean. The multi-monitor labeling exists because on a two- or three-screen setup the AI needs to know which display matters most, and the cursor is the best signal for "where the user's attention is."

## How it actually works
It uses Apple's modern ScreenCaptureKit framework (not the old deprecated APIs). The flow:

1. **Enumerate** what's shareable on the system: all displays and all on-screen windows.
2. **Find its own windows** by asking each window "who owns you?" and matching against the app's own bundle identifier (its unique app ID). Every window owned by clicky goes into an exclusion list.
3. **Sort displays so the cursor's screen comes first.** It figures out where the mouse is and puts that monitor at the front of the list, because that screen is the user's primary focus.
4. For each display, **build a capture filter** that says "capture this whole display, but blank out these specific windows" (the app's own).
5. **Configure the capture** to cap the long edge at 1280 pixels while preserving aspect ratio — small enough to send to an AI cheaply, large enough to read.
6. **Capture a single frame** (not a video stream) and encode it as JPEG at 80% quality.
7. **Label each screenshot** with its position, total screen count, and whether the cursor is on it.

A subtle but important detail: macOS has two different coordinate systems. ScreenCaptureKit reports display positions with the origin at the top-left; AppKit (where the mouse position and the app's own overlay windows live) puts the origin at the bottom-left. On a single monitor this doesn't matter, but with a second monitor the Y-axis origins disagree and "is the cursor on this screen?" checks silently break. The code fixes this by building a lookup table from each display's ID to its AppKit screen object, then using AppKit-coordinate frames for all the cursor math.

## The non-obvious parts
- **Self-exclusion is by app ownership, not window-by-window matching.** It doesn't try to identify each overlay individually; it filters every window whose owning application is clicky. This is robust — new overlays added later are automatically excluded.
- **Coordinate-system mismatch is a real multi-monitor bug.** The whole `nsScreenByDisplayID` lookup exists purely to avoid using ScreenCaptureKit's top-left coordinates for cursor checks. Skip this and secondary-monitor cursor detection breaks.
- **It captures a single image, not a stream.** It uses `SCScreenshotManager.captureImage`, the one-shot API, so there's no stream lifecycle to manage.
- **The cursor screen is always first in the returned array**, and the label text changes based on single vs. multi-monitor and cursor presence, so downstream prompt-building can rely on ordering.
- **`excludingDesktopWindows(false, onScreenWindowsOnly: true)`** keeps desktop/wallpaper windows but only considers windows currently on screen.

## Related
- [[push-to-talk-streaming-transcription--from-clicky]] (the other half of the voice companion: this captures *what the user sees*, that captures *what the user says*)
- [[ai-integration/streaming-claude-screen-context--from-clicky]] (consumes these labeled screenshots as the AI's visual context)
- [[canvas-interaction/screen-element-localization--from-clicky]] (uses the same display frames and coordinate conversions to point at on-screen elements)
- [[tts/elevenlabs-streaming-tts--from-clicky]] (the AI's spoken reply, completing the loop)
