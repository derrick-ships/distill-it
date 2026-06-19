# Animated Pointer Guidance (build spec) — distilled from clicky

## Summary
A transparent, click-through overlay window per display hosts a SwiftUI `BlueCursorView` (a glowing blue triangle). It follows the mouse with a spring; when a detected element location arrives, it flies there along a timer-driven quadratic Bézier arc (leaning into the tangent, pulsing in scale), points + shows a bubble, then returns to following. Three classes: `OverlayWindow` (the NSWindow), `OverlayWindowManager` (lifecycle, one window per screen), `BlueCursorView` (the animated SwiftUI content). `CompanionManager` converts the detector's display-local point into a global screen point and publishes it; `WindowPositionManager` holds the multi-monitor coordinate helpers.

## Core logic (inlined)

### The overlay window — transparent, click-through, all-Spaces, never-key

```swift
class OverlayWindow: NSWindow {
    init(screen: NSScreen) {
        super.init(contentRect: screen.frame, styleMask: .borderless, backing: .buffered, defer: false)
        self.isOpaque = false
        self.backgroundColor = .clear
        self.level = .screenSaver                 // above normal app windows
        self.ignoresMouseEvents = true            // click-through HUD
        self.collectionBehavior = [.canJoinAllSpaces, .stationary, .fullScreenAuxiliary]
        self.isReleasedWhenClosed = false
        self.hasShadow = false
        self.hidesOnDeactivate = false
        self.setFrame(screen.frame, display: true)
        if let s = NSScreen.screens.first(where: { $0.frame == screen.frame }) {
            self.setFrameOrigin(s.frame.origin)
        }
    }
    override var canBecomeKey: Bool { false }     // purely decorative
    override var canBecomeMain: Bool { false }
}
```

### Manager — one window+view per screen, fade-out on hide

```swift
@MainActor
class OverlayWindowManager {
    private var overlayWindows: [OverlayWindow] = []
    var hasShownOverlayBefore = false

    func showOverlay(onScreens screens: [NSScreen], companionManager: CompanionManager) {
        hideOverlay()
        let isFirstAppearance = !hasShownOverlayBefore
        hasShownOverlayBefore = true
        for screen in screens {
            let window = OverlayWindow(screen: screen)
            let contentView = BlueCursorView(screenFrame: screen.frame,
                                             isFirstAppearance: isFirstAppearance,
                                             companionManager: companionManager)
            let hosting = NSHostingView(rootView: contentView)
            hosting.frame = screen.frame
            window.contentView = hosting
            overlayWindows.append(window)
            window.orderFrontRegardless()
        }
    }
    func hideOverlay() {
        for w in overlayWindows { w.orderOut(nil); w.contentView = nil }
        overlayWindows.removeAll()
    }
    func fadeOutAndHideOverlay(duration: TimeInterval = 0.4) {
        let windows = overlayWindows; overlayWindows.removeAll()
        NSAnimationContext.runAnimationGroup({ ctx in
            ctx.duration = duration
            ctx.timingFunction = CAMediaTimingFunction(name: .easeIn)
            for w in windows { w.animator().alphaValue = 0 }
        }, completionHandler: {
            for w in windows { w.orderOut(nil); w.contentView = nil }
        })
    }
    func isShowingOverlay() -> Bool { !overlayWindows.isEmpty }
}
```

### BlueCursorView — state, body, navigation modes

```swift
enum BuddyNavigationMode { case followingCursor, navigatingToTarget, pointingAtTarget }

// key state
@State private var cursorPosition: CGPoint
@State private var triangleRotationDegrees: Double = -35.0
@State private var buddyFlightScale: CGFloat = 1.0
@State private var buddyNavigationMode: BuddyNavigationMode = .followingCursor
@State private var navigationAnimationTimer: Timer?
@State private var timer: Timer?                       // cursor-follow timer
@State private var cursorPositionWhenNavigationStarted: CGPoint = .zero
@State private var isReturningToCursor: Bool = false
@ObservedObject var companionManager: CompanionManager
// let screenFrame: CGRect  (passed in at init — THIS screen's frame)

// body — the triangle:
Triangle()
    .fill(DS.Colors.overlayCursorBlue)                 // Color(hex:"#3380FF")
    .frame(width: 16, height: 16)
    .rotationEffect(.degrees(triangleRotationDegrees))
    .shadow(color: DS.Colors.overlayCursorBlue, radius: 8 + (buddyFlightScale - 1.0) * 20, x: 0, y: 0)
    .scaleEffect(buddyFlightScale)
    .opacity(/* visible only on this screen + idle/responding */ cursorOpacity)
    .position(cursorPosition)
    .animation(buddyNavigationMode == .followingCursor
               ? .spring(response: 0.2, dampingFraction: 0.6, blendDuration: 0)
               : nil,                                  // nil during flight: don't fight the timer
               value: cursorPosition)
```

### Tie-in: react to detected location, convert coords, kick off flight

```swift
.onChange(of: companionManager.detectedElementScreenLocation) { newLocation in
    guard let screenLocation = newLocation,
          let displayFrame = companionManager.detectedElementDisplayFrame else { return }
    // only THIS screen's view reacts to elements on its display
    guard screenFrame.contains(CGPoint(x: displayFrame.midX, y: displayFrame.midY))
          || displayFrame == screenFrame else { return }
    startNavigatingToElement(screenLocation: screenLocation)
}

// global AppKit (bottom-left) screen point -> this window's SwiftUI (top-left) local point
private func convertScreenPointToSwiftUICoordinates(_ p: CGPoint) -> CGPoint {
    let x = p.x - screenFrame.origin.x
    let y = (screenFrame.origin.y + screenFrame.height) - p.y
    return CGPoint(x: x, y: y)
}

private func startNavigatingToElement(screenLocation: CGPoint) {
    guard !showWelcome || welcomeText.isEmpty else { return }
    let targetInSwiftUI = convertScreenPointToSwiftUICoordinates(screenLocation)
    let offsetTarget = CGPoint(x: targetInSwiftUI.x + 8, y: targetInSwiftUI.y + 12) // sit beside element
    let clampedTarget = CGPoint(
        x: max(20, min(offsetTarget.x, screenFrame.width  - 20)),
        y: max(20, min(offsetTarget.y, screenFrame.height - 20)))
    cursorPositionWhenNavigationStarted = convertScreenPointToSwiftUICoordinates(NSEvent.mouseLocation)
    buddyNavigationMode = .navigatingToTarget
    isReturningToCursor = false
    animateBezierFlightArc(to: clampedTarget) {
        guard self.buddyNavigationMode == .navigatingToTarget else { return }
        self.startPointingAtElement()   // arrival: point + bubble
    }
}
```

### The flight — quadratic Bézier, smoothstep, tangent rotation, sine scale pulse

```swift
private func animateBezierFlightArc(to destination: CGPoint, onComplete: @escaping () -> Void) {
    navigationAnimationTimer?.invalidate()
    let startPosition = cursorPosition
    let endPosition = destination
    let dx = endPosition.x - startPosition.x, dy = endPosition.y - startPosition.y
    let distance = hypot(dx, dy)

    let flightDurationSeconds = min(max(distance / 800.0, 0.6), 1.4)   // 0.6s..1.4s by distance
    let frameInterval = 1.0 / 60.0
    let totalFrames = Int(flightDurationSeconds / frameInterval)
    var currentFrame = 0

    let mid = CGPoint(x: (startPosition.x + endPosition.x)/2, y: (startPosition.y + endPosition.y)/2)
    let arcHeight = min(distance * 0.2, 80.0)
    let controlPoint = CGPoint(x: mid.x, y: mid.y - arcHeight)         // lift control point UP -> bow

    navigationAnimationTimer = Timer.scheduledTimer(withTimeInterval: frameInterval, repeats: true) { _ in
        currentFrame += 1
        if currentFrame > totalFrames {
            self.navigationAnimationTimer?.invalidate(); self.navigationAnimationTimer = nil
            self.cursorPosition = endPosition; self.buddyFlightScale = 1.0
            onComplete(); return
        }
        let p = Double(currentFrame) / Double(totalFrames)
        let t = p * p * (3.0 - 2.0 * p)                                // smoothstep ease-in-out
        let u = 1.0 - t
        let bx = u*u*startPosition.x + 2*u*t*controlPoint.x + t*t*endPosition.x
        let by = u*u*startPosition.y + 2*u*t*controlPoint.y + t*t*endPosition.y
        self.cursorPosition = CGPoint(x: bx, y: by)
        // tangent (Bézier derivative) -> rotate triangle to face travel, +90 for nose orientation
        let tx = 2*u*(controlPoint.x - startPosition.x) + 2*t*(endPosition.x - controlPoint.x)
        let ty = 2*u*(controlPoint.y - startPosition.y) + 2*t*(endPosition.y - controlPoint.y)
        self.triangleRotationDegrees = atan2(ty, tx) * (180.0 / .pi) + 90.0
        // size pulse peaks at arc midpoint
        self.buddyFlightScale = 1.0 + sin(p * .pi) * 0.3              // up to 1.3x
    }
}
```

### Cursor following + return-flight cancel (60Hz timer)

```swift
private func startTrackingCursor() {
    timer = Timer.scheduledTimer(withTimeInterval: 0.016, repeats: true) { _ in
        let m = NSEvent.mouseLocation
        self.isCursorOnThisScreen = self.screenFrame.contains(m)
        // only the RETURN flight is cancelable by mouse movement (>100px)
        if self.buddyNavigationMode == .navigatingToTarget && self.isReturningToCursor {
            let cur = self.convertScreenPointToSwiftUICoordinates(m)
            let d = hypot(cur.x - self.cursorPositionWhenNavigationStarted.x,
                          cur.y - self.cursorPositionWhenNavigationStarted.y)
            if d > 100 { cancelNavigationAndResumeFollowing() }
            return
        }
        if self.buddyNavigationMode != .followingCursor { return }   // forward flight/pointing: ignore mouse
        let s = self.convertScreenPointToSwiftUICoordinates(m)
        self.cursorPosition = CGPoint(x: s.x + 35, y: s.y + 25)      // park down-right of cursor
    }
}
```

### CompanionManager — detector point → global point → published

```swift
@Published var detectedElementScreenLocation: CGPoint?   // GLOBAL AppKit point
@Published var detectedElementDisplayFrame: CGRect?
@Published var detectedElementBubbleText: String?

// after parsing the AI result (note: this path scales from screenshot PIXELS, not the
// detector's point output — clicky has two equivalent map paths; the math is the same shape):
let clampedX = max(0, min(pointCoordinate.x, screenshotWidth))
let clampedY = max(0, min(pointCoordinate.y, screenshotHeight))
let displayLocalX = clampedX * (displayWidth / screenshotWidth)
let displayLocalY = clampedY * (displayHeight / screenshotHeight)
let appKitY = displayHeight - displayLocalY                       // flip top-left -> bottom-left
let globalLocation = CGPoint(x: displayLocalX + displayFrame.origin.x,   // display-local -> global
                             y: appKitY      + displayFrame.origin.y)
detectedElementScreenLocation = globalLocation
detectedElementDisplayFrame  = displayFrame

// multi-monitor screen selection for the capture:
let targetScreenCapture: CompanionScreenCapture? = {
    if let n = parseResult.screenNumber, n >= 1 && n <= screenCaptures.count { return screenCaptures[n-1] }
    return screenCaptures.first(where: { $0.isCursorScreen })
}()

// enable/disable overlay:
func setClickyCursorEnabled(_ enabled: Bool) {
    isClickyCursorEnabled = enabled
    if enabled {
        overlayWindowManager.hasShownOverlayBefore = true
        overlayWindowManager.showOverlay(onScreens: NSScreen.screens, companionManager: self)
        isOverlayVisible = true
    } else { overlayWindowManager.hideOverlay(); isOverlayVisible = false }
}
```

### WindowPositionManager — multi-monitor helpers

```swift
extension NSScreen {
    var displayID: CGDirectDisplayID {
        deviceDescription[NSDeviceDescriptionKey("NSScreenNumber")] as? CGDirectDisplayID ?? 0
    }
}
// AX (top-left) -> NSScreen (bottom-left):  nsY = screenFrame.maxY - axY - height
```

## Data contracts
- `BlueCursorView.init(screenFrame: CGRect, isFirstAppearance: Bool, companionManager: CompanionManager)`.
- Watched inputs: `companionManager.detectedElementScreenLocation: CGPoint?` (global AppKit) and `detectedElementDisplayFrame: CGRect?`. Setting the location to a non-nil value triggers a flight on the matching screen's view.
- `OverlayWindowManager.showOverlay(onScreens: [NSScreen], companionManager:)`, `hideOverlay()`, `fadeOutAndHideOverlay(duration: TimeInterval = 0.4)`.
- Design tokens (DesignSystem.swift): `DS.Colors.overlayCursorBlue = Color(hex:"#3380FF")`; animation durations `fast=0.15, normal=0.25, slow=0.4`.

## Dependencies & assumptions
- macOS, AppKit + SwiftUI (`NSHostingView`). No third-party deps.
- Mouse position via `NSEvent.mouseLocation` (global, bottom-left). 60Hz `Timer`s on the main run loop.
- Assumes one overlay per `NSScreen`; each view knows only its own `screenFrame`.
- Relies on [[screen-element-localization--from-clicky]] for the target point (display-local), and on CompanionManager to globalize it.
- The overlay should be excluded from screen capture (see [[media-processing/screen-capture-self-exclusion--from-clicky]]).

## To port this, you need:
- [ ] A borderless, transparent, click-through, top-most window per display that cannot become key/main and joins all Spaces.
- [ ] A 60Hz mouse-follow loop that parks the pointer at an offset from the cursor with a soft spring.
- [ ] A manual (non-implicit-animation) quadratic Bézier flight: distance-scaled duration (0.6–1.4s), smoothstep `t = p²(3-2p)`, control point lifted by `min(dist*0.2, 80)`, tangent-based rotation (+90°), sine scale pulse to 1.3x.
- [ ] A state machine: followingCursor / navigatingToTarget / pointingAtTarget, with cancel-on-mouse-move only during the return leg (>100px).
- [ ] Coordinate plumbing: detector display-local point → global (add display frame origin, flip Y) → per-view SwiftUI local (subtract origin, flip Y again).
- [ ] Per-screen routing so only the view on the element's display flies.
- [ ] A graceful fade-out (0.4s ease-in) that waits for TTS/location-clear before hiding.

## Gotchas
- **Override `canBecomeKey`/`canBecomeMain` to false** or the HUD steals focus. `ignoresMouseEvents = true` makes it click-through; `.screenSaver` level keeps it on top.
- **Set `.animation(... value: cursorPosition)` to `nil` while flying** — SwiftUI's implicit spring will fight the per-frame timer updates and stutter.
- **Y axis flips twice**: bottom-left global → top-left SwiftUI per window, easy to invert. Control point is `mid.y - arcHeight` because lower Y is UP in SwiftUI's top-left space.
- **Don't cancel the forward flight** — only the return flight listens to mouse movement; cancel threshold is 100px from where navigation started.
- **The buddy sits BESIDE the element** (+8x,+12y) and is clamped 20px inside screen edges so it never points from off-screen.
- Each screen gets its own `BlueCursorView`; without the `displayFrame`-contains guard, every monitor's buddy would fly at once.
- Glow radius is tied to scale (`8 + (scale-1)*20`) — drop that and the flight loses its "energy" feel.

## Origin (reference only)
clicky — `leanring-buddy/OverlayWindow.swift` (`OverlayWindow`, `OverlayWindowManager`, `BlueCursorView`, `BuddyNavigationMode`, `Triangle`), `leanring-buddy/CompanionManager.swift` (coordinate globalization + `detectedElement*` published props + `setClickyCursorEnabled`), `leanring-buddy/WindowPositionManager.swift` (`NSScreen.displayID`, AX↔NSScreen flips), `leanring-buddy/DesignSystem.swift` (`overlayCursorBlue`, animation durations). Repo: https://github.com/farzaa/clicky (misspelled `leanring-buddy` dir).
