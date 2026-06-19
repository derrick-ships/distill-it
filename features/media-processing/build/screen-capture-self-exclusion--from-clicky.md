# Screen Capture with Self-Exclusion (build spec) — distilled from clicky

## Summary
A `@MainActor enum` utility that captures every connected display as JPEG via ScreenCaptureKit, **excluding all of the app's own windows** so an AI never sees the app's overlays. Returns one struct per display, cursor-screen first, each labeled with its multi-monitor position. Single-frame capture (`SCScreenshotManager.captureImage`), not a stream.

## Core logic (inlined)

```swift
import AppKit
import ScreenCaptureKit

struct CompanionScreenCapture {
    let imageData: Data
    let label: String
    let isCursorScreen: Bool
    let displayWidthInPoints: Int
    let displayHeightInPoints: Int
    let displayFrame: CGRect
    let screenshotWidthInPixels: Int
    let screenshotHeightInPixels: Int
}

@MainActor
enum CompanionScreenCaptureUtility {

    static func captureAllScreensAsJPEG() async throws -> [CompanionScreenCapture] {
        // Keep desktop windows; only on-screen windows considered.
        let content = try await SCShareableContent.excludingDesktopWindows(false, onScreenWindowsOnly: true)

        guard !content.displays.isEmpty else {
            throw NSError(domain: "CompanionScreenCapture", code: -1,
                          userInfo: [NSLocalizedDescriptionKey: "No display available for capture"])
        }

        let mouseLocation = NSEvent.mouseLocation  // AppKit coords (bottom-left origin)

        // SELF-EXCLUSION: every window owned by THIS app, matched by bundle id.
        let ownBundleIdentifier = Bundle.main.bundleIdentifier
        let ownAppWindows = content.windows.filter { window in
            window.owningApplication?.bundleIdentifier == ownBundleIdentifier
        }

        // Map SCDisplay.displayID -> NSScreen so we can use AppKit-coordinate frames.
        // SCDisplay.frame is CG coords (top-left); NSScreen.frame & NSEvent.mouseLocation
        // are AppKit (bottom-left). On multi-display the Y origins differ -> cursor checks break.
        var nsScreenByDisplayID: [CGDirectDisplayID: NSScreen] = [:]
        for screen in NSScreen.screens {
            if let screenNumber = screen.deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? CGDirectDisplayID {
                nsScreenByDisplayID[screenNumber] = screen
            }
        }

        // Cursor screen sorts first.
        let sortedDisplays = content.displays.sorted { displayA, displayB in
            let frameA = nsScreenByDisplayID[displayA.displayID]?.frame ?? displayA.frame
            let frameB = nsScreenByDisplayID[displayB.displayID]?.frame ?? displayB.frame
            let aContainsCursor = frameA.contains(mouseLocation)
            let bContainsCursor = frameB.contains(mouseLocation)
            if aContainsCursor != bContainsCursor { return aContainsCursor }
            return false
        }

        var capturedScreens: [CompanionScreenCapture] = []

        for (displayIndex, display) in sortedDisplays.enumerated() {
            let displayFrame = nsScreenByDisplayID[display.displayID]?.frame
                ?? CGRect(x: display.frame.origin.x, y: display.frame.origin.y,
                          width: CGFloat(display.width), height: CGFloat(display.height))
            let isCursorScreen = displayFrame.contains(mouseLocation)

            // FILTER: capture this display, blank out our own windows.
            let filter = SCContentFilter(display: display, excludingWindows: ownAppWindows)

            // CONFIG: cap long edge at 1280px, preserve aspect ratio.
            let configuration = SCStreamConfiguration()
            let maxDimension = 1280
            let aspectRatio = CGFloat(display.width) / CGFloat(display.height)
            if display.width >= display.height {
                configuration.width = maxDimension
                configuration.height = Int(CGFloat(maxDimension) / aspectRatio)
            } else {
                configuration.height = maxDimension
                configuration.width = Int(CGFloat(maxDimension) * aspectRatio)
            }

            // SINGLE-FRAME capture (not a stream).
            let cgImage = try await SCScreenshotManager.captureImage(
                contentFilter: filter,
                configuration: configuration
            )

            // ENCODE: JPEG @ 0.8 quality.
            guard let jpegData = NSBitmapImageRep(cgImage: cgImage)
                    .representation(using: .jpeg, properties: [.compressionFactor: 0.8]) else {
                continue
            }

            let screenLabel: String
            if sortedDisplays.count == 1 {
                screenLabel = "user's screen (cursor is here)"
            } else if isCursorScreen {
                screenLabel = "screen \(displayIndex + 1) of \(sortedDisplays.count) — cursor is on this screen (primary focus)"
            } else {
                screenLabel = "screen \(displayIndex + 1) of \(sortedDisplays.count) — secondary screen"
            }

            capturedScreens.append(CompanionScreenCapture(
                imageData: jpegData,
                label: screenLabel,
                isCursorScreen: isCursorScreen,
                displayWidthInPoints: Int(displayFrame.width),
                displayHeightInPoints: Int(displayFrame.height),
                displayFrame: displayFrame,
                screenshotWidthInPixels: configuration.width,
                screenshotHeightInPixels: configuration.height
            ))
        }

        guard !capturedScreens.isEmpty else {
            throw NSError(domain: "CompanionScreenCapture", code: -2,
                          userInfo: [NSLocalizedDescriptionKey: "Failed to capture any screen"])
        }

        return capturedScreens
    }
}
```

## Data contracts
- **Input:** none (reads live system state — displays, windows, mouse location, own bundle id).
- **Output:** `[CompanionScreenCapture]`, **cursor-screen first**. Each item:
  - `imageData: Data` — JPEG, long edge ≤ 1280px, quality 0.8.
  - `label: String` — one of three forms (single screen / cursor screen / secondary).
  - `isCursorScreen: Bool`.
  - `displayWidthInPoints` / `displayHeightInPoints: Int` — from **NSScreen.frame** (AppKit points).
  - `displayFrame: CGRect` — **AppKit coords (bottom-left origin)**, same system as `NSEvent.mouseLocation`.
  - `screenshotWidthInPixels` / `screenshotHeightInPixels: Int` — the `SCStreamConfiguration` dimensions actually used.
- **Throws:** `NSError` domain `"CompanionScreenCapture"`, code `-1` (no display) or `-2` (nothing captured); plus any ScreenCaptureKit error from `captureImage`.

## Dependencies & assumptions
- macOS 14+ (ScreenCaptureKit `SCScreenshotManager.captureImage`, `SCContentFilter(display:excludingWindows:)`).
- Frameworks: `AppKit`, `ScreenCaptureKit`.
- **Screen Recording permission** must be granted (System Settings → Privacy & Security → Screen Recording), or `SCShareableContent` returns empty/throws.
- Must run on `@MainActor` (uses `NSEvent.mouseLocation`, `NSScreen.screens`).
- Assumes the app has a stable `Bundle.main.bundleIdentifier` and that all overlay windows belong to the same app process.

## To port this, you need:
- [ ] ScreenCaptureKit available + Screen Recording entitlement/permission granted at runtime.
- [ ] A way to identify "your own" windows. Here: `window.owningApplication?.bundleIdentifier == Bundle.main.bundleIdentifier`. If your overlays run in a separate helper process, match that process's bundle id instead.
- [ ] The `displayID → NSScreen` lookup if you do ANY cursor/coordinate math — do not use `SCDisplay.frame` for AppKit-coordinate comparisons.
- [ ] Decide capture cap (1280 long edge here) and image format (JPEG 0.8 here) for your AI's token/cost budget.
- [ ] Caller that pairs `imageData` + `label` into the AI prompt (cursor-first ordering is already guaranteed).

## Gotchas
- **Coordinate-system mismatch is the #1 multi-monitor bug.** `SCDisplay.frame` = top-left origin; `NSEvent.mouseLocation`/`NSScreen.frame` = bottom-left. Mixing them makes `frame.contains(mouseLocation)` silently wrong on secondary displays. The `nsScreenByDisplayID` map exists solely to avoid this.
- **Exclude by ownership, not by enumerating each overlay.** `SCContentFilter(display:excludingWindows:)` with the full set of app-owned windows means future overlays are auto-excluded.
- **`onScreenWindowsOnly: true`** — off-screen/minimized windows aren't in `content.windows`, so they can't be matched for exclusion (usually fine, since they aren't rendered anyway).
- **No display → throw, not empty array.** Caller should handle both `-1` and `-2`.
- **Single frame only.** `SCScreenshotManager.captureImage` — no stream start/stop, no `SCStreamDelegate`. Don't over-engineer a stream pipeline.
- Aspect-ratio branch handles portrait displays (rotated monitors) by capping height instead of width.

## Origin (reference only)
`leanring-buddy/CompanionScreenCaptureUtility.swift` in https://github.com/farzaa/clicky (note the repo's misspelled `leanring-buddy` directory). Verbatim as of distillation; assume upstream may disappear.
