# Notch-Shaped Always-On-Top Window (build spec) — distilled from boring.notch

## Summary
A borderless, non-activating `NSPanel` shaped like the MacBook notch, pinned top-center and kept visible across all Spaces, fullscreen, and the lock screen. Achieved with: AppKit collection behavior + a high window level, PLUS a private CoreGraphics (CGS/SkyLight) "space" at the maximum compositor level that the window is inserted into, PLUS a separate SkyLight-framework delegation for lock-screen visibility. Sizing comes from `NSScreen.auxiliaryTop*Area` (width) and `safeAreaInsets.top` (height). macOS 14+, Swift/SwiftUI. Uses undocumented private APIs — fragile across OS versions.

## Core logic (inlined)

### Window construction + config
```swift
let styleMask: NSWindow.StyleMask = [.borderless, .nonactivatingPanel, .utilityWindow, .hudWindow]
let window = BoringNotchSkyLightWindow(contentRect: rect, styleMask: styleMask, backing: .buffered, defer: false)
// in configureWindow():
isFloatingPanel = true
isOpaque = false
backgroundColor = .clear
titleVisibility = .hidden; titlebarAppearsTransparent = true
isMovable = false
hasShadow = false
isReleasedWhenClosed = false
level = .mainMenu + 3                         // above the menu bar
collectionBehavior = [.fullScreenAuxiliary, .stationary, .canJoinAllSpaces, .ignoresCycle]
// canBecomeKey == false, canBecomeMain == false   (never steals focus)
// sharingType = hideFromScreenRecording ? .none : .readWrite
window.orderFrontRegardless()                 // show without activating
```

### The private CGS space (the core trick) — `CGSSpace.swift`
```swift
// Private symbols bound by name (no header):
@_silgen_name("_CGSDefaultConnection") func _CGSDefaultConnection() -> CGSConnectionID
@_silgen_name("CGSSpaceCreate") func CGSSpaceCreate(_ cid: CGSConnectionID, _ flag: Int, _ options: NSDictionary?) -> CGSSpaceID
@_silgen_name("CGSSpaceSetAbsoluteLevel") func CGSSpaceSetAbsoluteLevel(_ cid: CGSConnectionID, _ space: CGSSpaceID, _ level: Int)
@_silgen_name("CGSShowSpaces") func CGSShowSpaces(_ cid: CGSConnectionID, _ spaces: NSArray)
@_silgen_name("CGSAddWindowsToSpaces") func CGSAddWindowsToSpaces(_ cid: CGSConnectionID, _ windows: NSArray, _ spaces: NSArray)
@_silgen_name("CGSRemoveWindowsFromSpaces") func CGSRemoveWindowsFromSpaces(_ cid: CGSConnectionID, _ windows: NSArray, _ spaces: NSArray)
// (+ CGSSpaceDestroy, CGSHideSpaces)

init(level: Int) {
    let flag = 0x1   // MUST be 1 — any other value lets Finder draw desktop icons over the space
    identifier = CGSSpaceCreate(_CGSDefaultConnection(), flag, nil)
    CGSSpaceSetAbsoluteLevel(_CGSDefaultConnection(), identifier, level)
    CGSShowSpaces(_CGSDefaultConnection(), [identifier])
}
// windows: Set<NSWindow> with a didSet that diffs and calls CGSAdd/RemoveWindowsToSpaces with $0.windowNumber
```
```swift
// NotchSpaceManager (singleton): notchSpace = CGSSpace(level: 2147483647 /* Int32.max */)
// After creating each window:  NotchSpaceManager.shared.notchSpace.windows.insert(window)
```

### Lock-screen via SkyLight — `BoringNotchSkyLightWindow.swift`
```swift
func enableSkyLight()  { SkyLightOperator.shared.delegateWindow(self) }    // SkyLightWindow package (Lakr233)
func disableSkyLight() { SkyLightOperator.shared.undelegateWindow(self) }
// undelegate dynamically loads the private removal symbol at runtime:
let h = dlopen("/System/Library/PrivateFrameworks/SkyLight.framework/Versions/A/SkyLight", RTLD_NOW)
typealias F = @convention(c) (Int32, CFArray, CFArray) -> Int32
let SLSRemoveWindowsFromSpaces = unsafeBitCast(dlsym(h, "SLSRemoveWindowsFromSpaces"), to: F.self)
_ = SLSRemoveWindowsFromSpaces(connection, [window.windowNumber] as CFArray, [space] as CFArray)
// toggled by DistributedNotificationCenter observers on com.apple.screenIsLocked / com.apple.screenIsUnlocked
```

### Notch sizing — `getClosedNotchSize(screen)`
```swift
// WIDTH: bracket the physical notch using the status-bar auxiliary areas
if let l = screen.auxiliaryTopLeftArea?.width, let r = screen.auxiliaryTopRightArea?.width {
    notchWidth = screen.frame.width - l - r + 4
}
// HEIGHT:
if screen.safeAreaInsets.top > 0 {            // has a notch
    // matchRealNotchSize -> screen.safeAreaInsets.top
    // matchMenuBar       -> screen.frame.maxY - screen.visibleFrame.maxY
    // default            -> Defaults[.notchHeight]
} else {                                       // external/no-notch display
    // matchMenuBar -> menu-bar height ; default -> Defaults[.nonNotchHeight]
}
```

### Positioning + per-display
```swift
window.setFrameOrigin(NSPoint(
    x: screenFrame.origin.x + screenFrame.width/2 - window.frame.width/2,   // centered on full width
    y: screenFrame.origin.y + screenFrame.height - window.frame.height))    // top
// multi-display: one window per screen keyed by displayUUID (CGDisplayCreateUUIDFromDisplayID -> CFUUIDCreateString, cached);
// rebuild on NSApplication.didChangeScreenParametersNotification
```

### Notch shape
`NotchShape: Shape, Animatable` — quad-curve path: topCornerRadius 6, bottomCornerRadius 14; pill-with-flat-top silhouette.

## Data contracts
- Global: `windowSize = CGSize(640, 210)` (openNotchSize.height 190 + shadowPadding 20).
- `CGSSpace` level: `2147483647` (Int32.max). CGS connection ids are `UInt`, space ids `UInt64`.
- Windows tracked in `AppDelegate.windows: [String /*displayUUID*/ : NSWindow]` (or a single `window`).

## Dependencies & assumptions
- macOS 14+ (Sonoma). Public: AppKit (`NSPanel`, `NSScreen`, `collectionBehavior`), `NSHostingView` for SwiftUI content.
- Private: CoreGraphics `CGSSpace*` (via `@_silgen_name`); `SkyLight.framework` `SLSRemoveWindowsFromSpaces` (via `dlopen`/`dlsym`); the `SkyLightWindow` Swift package (`github.com/Lakr233/SkyLightWindow`) for the enable path.
- `safeAreaInsets.top`/`auxiliaryTopLeftArea` require a notched display to be meaningful; external displays fall back to menu-bar math.

## To port this, you need:
- [ ] A borderless non-activating `NSPanel`, clear/no-shadow, `canBecomeKey/Main = false`, high level, the 4-flag `collectionBehavior`.
- [ ] The CGS space wrapper (the 6–8 `@_silgen_name` symbols) + a manager that creates one space at `Int32.max` and inserts windows by `windowNumber`. **Use `flag = 0x1`.**
- [ ] (Lock screen) the SkyLight delegation path + `dlopen` of `SLSRemoveWindowsFromSpaces`, toggled on screen lock/unlock notifications.
- [ ] Notch sizing from `auxiliaryTop*Area` (width) + `safeAreaInsets.top` (height), with a no-notch fallback.
- [ ] A `Shape` for the notch outline; embed SwiftUI via `NSHostingView`.
- [ ] Per-display handling keyed by display UUID; rebuild on screen-param changes.

## Gotchas
- **All of this is private API** — `CGSSpace*` and `SkyLight` symbols are undocumented and can break on any macOS update. Gate by OS version; degrade gracefully.
- **`flag = 0x1`** is mandatory in `CGSSpaceCreate` or Finder icons render over your space.
- **CGS space ≠ window level.** The AppKit `level` matters for normal stacking, but cross-Space/fullscreen ubiquity comes from the CGS absolute level — they're separate concepts; you need the space.
- **Lock screen is a different compositor** — CGS won't reach it; that's why the separate SkyLight path exists.
- **Screen-recording visibility** — set `sharingType = .none` to hide it if desired.
- **No code signing/entitlement detail captured** for the private-API calls — verify what the app declares before relying.

## Origin (reference only)
Repo: https://github.com/TheBoredTeam/boring.notch · Files (read verbatim): `components/Notch/{BoringNotchWindow,BoringNotchSkyLightWindow,NotchShape}.swift`, `managers/NotchSpaceManager.swift`, `private/CGSSpace.swift`, `extensions/NSScreen+UUID.swift`, `boringNotchApp.swift`, `sizing/matters.swift`. GAP: `SkyLightOperator.delegateWindow` internals live in the external `Lakr233/SkyLightWindow` package (not read); `BoringViewModel`/`ContentView`/`DragDetector` not read.
