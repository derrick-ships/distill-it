# Notch-Anchored Companion Overlay (build spec) — distilled from clicky

## Summary
A menu-bar-only macOS (AppKit + SwiftUI) app with two transparent surfaces: (1) a borderless `NSPanel` that drops out of the menu-bar/notch strip beneath an `NSStatusItem`, hosting setup UI; and (2) a per-screen, full-screen, borderless, click-through `OverlayWindow` at `.screenSaver` level that uses `.ignoresSafeArea()` to draw a companion cursor over the entire display — including the notch/housing area and the menu bar. No `safeAreaInsets`/notch-rect API is used; the "notch usage" is achieved by anchoring the panel under the menu bar and by ignoring safe area in the overlay.

## Core logic (inlined)

### App entry — menu-bar-only, no Dock icon
```swift
// leanring_buddyApp.swift
import ServiceManagement
import SwiftUI
import Sparkle

@main
struct leanring_buddyApp: App {
    @NSApplicationDelegateAdaptor(CompanionAppDelegate.self) var appDelegate
    var body: some Scene {
        // Empty Settings scene satisfies SwiftUI; never shown because LSUIElement=true.
        Settings { EmptyView() }
    }
}

@MainActor
final class CompanionAppDelegate: NSObject, NSApplicationDelegate {
    private var menuBarPanelManager: MenuBarPanelManager?
    private let companionManager = CompanionManager()

    func applicationDidFinishLaunching(_ notification: Notification) {
        UserDefaults.standard.register(defaults: ["NSInitialToolTipDelay": 0])
        menuBarPanelManager = MenuBarPanelManager(companionManager: companionManager)
        companionManager.start()
        // Auto-open the panel only if setup is incomplete.
        if !companionManager.hasCompletedOnboarding || !companionManager.allPermissionsGranted {
            menuBarPanelManager?.showPanelOnLaunch()
        }
        registerAsLoginItemIfNeeded()  // SMAppService.mainApp.register()
    }
}
```
> `LSUIElement` / accessory (no Dock icon, no app menu) is set in Info.plist — it is NOT set in code. `AppBundleConfiguration.swift` is only a typed Info.plist string reader (`Bundle.main.object(forInfoDictionaryKey:)` with a direct-plist-load fallback, trimming whitespace, nil on empty); it contains no activation-policy code.

### Menu-bar status item + drop-down panel (the "notch dock")
```swift
// MenuBarPanelManager.swift
import AppKit
import SwiftUI

extension Notification.Name {
    static let clickyDismissPanel = Notification.Name("clickyDismissPanel")
}

// Must subclass: a .nonactivatingPanel cannot normally become key, which would
// break the email TextField. Overriding canBecomeKey re-enables text input.
private class KeyablePanel: NSPanel {
    override var canBecomeKey: Bool { true }
}

@MainActor
final class MenuBarPanelManager: NSObject {
    private var statusItem: NSStatusItem?
    private var panel: NSPanel?
    private var clickOutsideMonitor: Any?
    private let companionManager: CompanionManager
    private let panelWidth: CGFloat = 320
    private let panelHeight: CGFloat = 380

    private func createStatusItem() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        guard let button = statusItem?.button else { return }
        button.image = makeClickyMenuBarIcon()   // hand-drawn rotated triangle
        button.image?.isTemplate = true          // auto-tint for light/dark menu bar
        button.action = #selector(statusItemClicked)
        button.target = self
    }

    func showPanelOnLaunch() {
        // delay so the status item has appeared before we measure its frame
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { self.showPanel() }
    }

    private func createPanel() {
        let view = CompanionPanelView(companionManager: companionManager).frame(width: panelWidth)
        let hostingView = NSHostingView(rootView: view)
        hostingView.frame = NSRect(x: 0, y: 0, width: panelWidth, height: panelHeight)
        hostingView.wantsLayer = true
        hostingView.layer?.backgroundColor = .clear

        let p = KeyablePanel(
            contentRect: NSRect(x: 0, y: 0, width: panelWidth, height: panelHeight),
            styleMask: [.borderless, .nonactivatingPanel],   // no focus steal
            backing: .buffered, defer: false
        )
        p.isFloatingPanel = true
        p.level = .floating
        p.isOpaque = false
        p.backgroundColor = .clear
        p.hasShadow = false                       // shadow drawn in SwiftUI instead
        p.hidesOnDeactivate = false
        p.isExcludedFromWindowsMenu = true
        p.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        p.isMovableByWindowBackground = false
        p.titleVisibility = .hidden
        p.titlebarAppearsTransparent = true
        p.contentView = hostingView
        panel = p
    }

    // Anchor the panel beneath the menu-bar icon (i.e. out of the notch strip).
    private func positionPanelBelowStatusItem() {
        guard let panel, let buttonWindow = statusItem?.button?.window else { return }
        let statusItemFrame = buttonWindow.frame
        let gapBelowMenuBar: CGFloat = 4
        // auto-size height to SwiftUI content rather than fixed panelHeight
        let fittingSize = panel.contentView?.fittingSize ?? CGSize(width: panelWidth, height: panelHeight)
        let actualPanelHeight = fittingSize.height
        let panelOriginX = statusItemFrame.midX - (panelWidth / 2)        // center under icon
        let panelOriginY = statusItemFrame.minY - actualPanelHeight - gapBelowMenuBar
        panel.setFrame(NSRect(x: panelOriginX, y: panelOriginY, width: panelWidth, height: actualPanelHeight), display: true)
    }

    private func showPanel() {
        if panel == nil { createPanel() }
        positionPanelBelowStatusItem()
        panel?.makeKeyAndOrderFront(nil)
        panel?.orderFrontRegardless()
        installClickOutsideMonitor()
    }

    // Outside-click dismissal with a delay + guard so granting a permission
    // (which raises a system dialog) doesn't kill the setup panel.
    private func installClickOutsideMonitor() {
        clickOutsideMonitor = NSEvent.addGlobalMonitorForEvents(matching: [.leftMouseDown, .rightMouseDown]) { [weak self] _ in
            guard let self, let panel = self.panel else { return }
            if panel.frame.contains(NSEvent.mouseLocation) { return }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                guard panel.isVisible else { return }
                if !self.companionManager.allPermissionsGranted && !NSApp.isActive { return }
                self.hidePanel()
            }
        }
    }
}
```

### Full-screen click-through companion overlay (covers notch/housing)
```swift
// OverlayWindow.swift
final class OverlayWindow: NSWindow {   // (subclass; exact name per file)
    init(screen: NSScreen) {
        super.init(contentRect: screen.frame, styleMask: .borderless, backing: .buffered, defer: false)
        self.isOpaque = false
        self.backgroundColor = .clear
        self.level = .screenSaver                 // ABOVE menu bar + Dock
        self.ignoresMouseEvents = true            // pure click-through
        self.collectionBehavior = [.canJoinAllSpaces, .stationary, .fullScreenAuxiliary]
        self.isReleasedWhenClosed = false
        self.hasShadow = false
        self.hidesOnDeactivate = false
        self.setFrame(screen.frame, display: true)
    }
    override var canBecomeKey: Bool { false }     // never steal focus
    override var canBecomeMain: Bool { false }
}

@MainActor
class OverlayWindowManager {
    private var overlayWindows: [OverlayWindow] = []
    var hasShownOverlayBefore = false

    // One overlay window + one BlueCursorView per screen.
    func showOverlay(onScreens screens: [NSScreen], companionManager: CompanionManager) {
        hideOverlay()
        let isFirstAppearance = !hasShownOverlayBefore
        hasShownOverlayBefore = true
        for screen in screens {
            let window = OverlayWindow(screen: screen)
            let contentView = BlueCursorView(screenFrame: screen.frame,
                                             isFirstAppearance: isFirstAppearance,
                                             companionManager: companionManager)
            let hostingView = NSHostingView(rootView: contentView)
            hostingView.frame = screen.frame
            window.contentView = hostingView
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
        }, completionHandler: { for w in windows { w.orderOut(nil); w.contentView = nil } })
    }
}
```

### Companion view: ignores safe area so it draws into the notch region; tracks the live cursor
```swift
// OverlayWindow.swift — BlueCursorView (abridged to the positioning core)
struct BlueCursorView: View {
    let screenFrame: CGRect
    let isFirstAppearance: Bool
    @ObservedObject var companionManager: CompanionManager
    @State private var cursorPosition: CGPoint
    @State private var isCursorOnThisScreen: Bool
    @State private var timer: Timer?

    init(screenFrame: CGRect, isFirstAppearance: Bool, companionManager: CompanionManager) {
        self.screenFrame = screenFrame; self.isFirstAppearance = isFirstAppearance
        self.companionManager = companionManager
        let m = NSEvent.mouseLocation
        let localX = m.x - screenFrame.origin.x
        let localY = screenFrame.height - (m.y - screenFrame.origin.y)   // flip Y to SwiftUI top-left
        _cursorPosition = State(initialValue: CGPoint(x: localX + 35, y: localY + 25))  // buddy offset
        _isCursorOnThisScreen = State(initialValue: screenFrame.contains(m))
    }

    var body: some View {
        ZStack {
            Color.black.opacity(0.001)   // catch nothing, just a transparent canvas
            // ... welcome bubble, onboarding video, navigation bubble ...
            Triangle()
                .fill(DS.Colors.overlayCursorBlue)
                .frame(width: 16, height: 16)
                .position(cursorPosition)
            // waveform / spinner overlays keyed to voiceState
        }
        .frame(width: screenFrame.width, height: screenFrame.height)
        .ignoresSafeArea()              // <<< KEY: extends the canvas into the notch/housing + menu bar
        .onAppear { startTrackingCursor() }
    }

    // 60fps cursor follow; only the screen the mouse is on draws the buddy.
    private func startTrackingCursor() {
        timer = Timer.scheduledTimer(withTimeInterval: 0.016, repeats: true) { _ in
            let m = NSEvent.mouseLocation
            self.isCursorOnThisScreen = self.screenFrame.contains(m)
            let p = self.convertScreenPointToSwiftUICoordinates(m)
            self.cursorPosition = CGPoint(x: p.x + 35, y: p.y + 25)
        }
    }
    private func convertScreenPointToSwiftUICoordinates(_ pt: CGPoint) -> CGPoint {
        CGPoint(x: pt.x - screenFrame.origin.x,
                y: (screenFrame.origin.y + screenFrame.height) - pt.y)
    }
}
```

## Data contracts
- `MenuBarPanelManager(companionManager:)` — owns `NSStatusItem` + `NSPanel`. Panel size 320×(auto). Toggled by `statusItemClicked`; dismissed via `.clickyDismissPanel` notification or outside-click monitor.
- `OverlayWindowManager.showOverlay(onScreens: [NSScreen], companionManager:)` — creates one borderless `OverlayWindow` per screen, each hosting a `BlueCursorView`. `hasShownOverlayBefore: Bool` gates the first-run intro animation (`isFirstAppearance`).
- Companion cursor offset constants: triangle drawn at `(mouseLocalX + 35, mouseLocalY + 25)`; bubbles at `(x + 10 + width/2, y + 18)`.
- Window levels: panel `.floating`; overlay `.screenSaver`. Overlay collectionBehavior `[.canJoinAllSpaces, .stationary, .fullScreenAuxiliary]`; panel `[.canJoinAllSpaces, .fullScreenAuxiliary]`.
- Coordinate convention: AppKit global coords have bottom-left origin, Y-up. SwiftUI overlay uses top-left origin, Y-down — hence the flip in `convertScreenPointToSwiftUICoordinates`.

## Dependencies & assumptions
- AppKit (`NSStatusBar`, `NSStatusItem`, `NSPanel`, `NSWindow`, `NSEvent`, `NSHostingView`, `NSScreen`), SwiftUI, `ServiceManagement` (`SMAppService` login item), Sparkle (auto-update; disabled in source).
- Info.plist must set `LSUIElement` (a.k.a. Application is agent / `NSApplication.ActivationPolicy.accessory`) so there's no Dock icon and no app menu. This is plist-driven, not code-driven.
- A SwiftUI design system `DS.Colors` (e.g. `overlayCursorBlue`, `background`, `borderSubtle`) and a `Triangle` Shape and `.pointerCursor()` view modifier exist in the project.
- `CompanionManager` provides `allPermissionsGranted`, `hasCompletedOnboarding`, `voiceState`, `currentAudioPowerLevel`, and onboarding-video state (see onboarding feature).

## To port this, you need:
- [ ] Set `LSUIElement = true` in Info.plist (no Dock icon, no app menu).
- [ ] Create an `NSStatusItem` with a template image; toggle a borderless `.nonactivatingPanel` (subclass overriding `canBecomeKey` if it must accept text input).
- [ ] Position the panel at `statusItemButton.window.frame.midX/minY` minus the panel size and a small gap — this is what makes it "drop out of the notch strip."
- [ ] Add a global `NSEvent` mouse monitor for outside-click dismissal, with a delay + "permissions pending / app inactive" guard so system permission dialogs don't auto-close it.
- [ ] Create a per-screen borderless `NSWindow` sized to `screen.frame` with `isOpaque=false`, `.clear` background, `level = .screenSaver`, `ignoresMouseEvents = true`, `[.canJoinAllSpaces, .stationary, .fullScreenAuxiliary]`, and `canBecomeKey/Main = false`.
- [ ] Host a SwiftUI view in it with `.ignoresSafeArea()` so the canvas covers the notch/housing and menu bar.
- [ ] Track `NSEvent.mouseLocation` on a 60fps timer, convert global→per-screen-SwiftUI coords (flip Y), and only render on the screen that `contains` the mouse.
- [ ] Loop `NSScreen.screens` to support multi-monitor (one window + view per screen).

## Gotchas
- **No notch API is used.** Clicky never calls `safeAreaInsets`, `auxiliaryTopLeftArea`, or any notch-rectangle API (confirmed: absent from all six source files). The companion can sit by the notch purely because the overlay is full-screen, `screenSaver`-level, and `.ignoresSafeArea()`. If you instead want to *dock to* the notch precisely, you'd add `screen.safeAreaInsets`/`auxiliaryTopLeftArea` yourself — Clicky does not.
- A `.nonactivatingPanel` cannot become key by default → text fields won't accept input. Must subclass and override `canBecomeKey`.
- `level = .floating` for the panel vs `.screenSaver` for the overlay is deliberate: the overlay must sit above the menu bar/Dock and be untouchable; the panel must be a normal focusable card.
- Outside-click dismissal must be delayed (0.3s) and skipped while permissions are ungranted/app inactive, or the panel disappears the moment macOS shows a permission prompt triggered from inside it.
- The overlay window's `hasShadow = false`; the visible card shadow is drawn in SwiftUI (`panelBackground`), so transparency stays clean.
- 60fps `Timer` polling of `NSEvent.mouseLocation` is the cursor-follow mechanism (not an event tap) — simple and avoids needing extra event-monitor permissions for the visual follow.
- `OverlayWindowManager` is `@MainActor`; all window/HUD work runs on main.

## Origin (reference only)
- `leanring-buddy/MenuBarPanelManager.swift` — `NSStatusItem`, `KeyablePanel`, panel config + below-menu-bar positioning, outside-click monitor.
- `leanring-buddy/OverlayWindow.swift` — `OverlayWindow` (borderless, `screenSaver`, click-through), `OverlayWindowManager` (per-screen), `BlueCursorView` (`.ignoresSafeArea()`, cursor tracking).
- `leanring-buddy/leanring_buddyApp.swift` — `@main` App, `CompanionAppDelegate`, launch wiring, `SMAppService` login item.
- `leanring-buddy/CompanionPanelView.swift` — SwiftUI content of the panel (permission rows, model picker, start button).
- `leanring-buddy/WindowPositionManager.swift` — unrelated to notch; pins the (other) main window to a screen edge; provides `requestAccessibilityPermission()` / `requestScreenRecordingPermission()` statics. No safe-area/notch logic.
- `leanring-buddy/AppBundleConfiguration.swift` — Info.plist string reader only.
- Repo: https://github.com/farzaa/clicky (assume gone; all load-bearing code inlined above).
