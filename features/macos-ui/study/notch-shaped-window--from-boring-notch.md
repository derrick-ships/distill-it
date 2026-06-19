# Notch-Shaped Always-On-Top Window — from [boring.notch](https://github.com/TheBoredTeam/boring.notch)

> Domain: [[_domain]] · Source: https://github.com/TheBoredTeam/boring.notch · NotebookLM: <add link>

## What it does
It draws a floating panel shaped exactly like the MacBook notch, parks it at the top-center of the screen, and keeps it visible *everywhere* — over fullscreen apps, on every Space (desktop), and even on the lock screen — while never stealing focus or showing up in screen recordings (if you want). It looks like part of the hardware notch, but it's a real window the app fully controls.

## Why it exists
macOS doesn't give apps a normal way to own the notch region or to draw a window that floats above the menu bar across all Spaces and fullscreen. A regular `NSWindow`, even at a high level, disappears when you switch to a fullscreen app or another desktop. The job-to-be-done is "make our UI feel like it lives in the notch, always there, above everything, without grabbing focus." Achieving that requires reaching past the public AppKit API into private window-server (CoreGraphics SkyLight / CGS) functions — which is the hard, interesting engineering here.

## How it actually works
1. **A borderless non-activating panel.** The window is an `NSPanel` subclass with style mask `[.borderless, .nonactivatingPanel, .utilityWindow, .hudWindow]`, clear background, no shadow, not movable, and `canBecomeKey`/`canBecomeMain` both `false` — so it floats and never takes focus.
2. **Collection behavior for ubiquity.** `collectionBehavior = [.fullScreenAuxiliary, .stationary, .canJoinAllSpaces, .ignoresCycle]` — visible in fullscreen, doesn't slide during Space transitions, present on every Space, skipped by Cmd-` cycling. Window `level` is `.mainMenu + 3` (above the menu bar).
3. **The private CGS space — the real trick.** AppKit's collection behavior alone isn't enough to sit reliably above everything. The app creates a private CoreGraphics "space" via undocumented `CGSSpace*` functions (bound with `@_silgen_name`), sets it to the absolute maximum compositor level (`Int32.max`), and inserts the notch window into it. Every notch window becomes a member of this always-on-top space.
4. **The notch silhouette.** `NotchShape` is a SwiftUI `Shape` that traces the pill-with-flat-top outline using quad curves (default top corner radius 6, bottom 14), so the content visually matches the hardware notch.
5. **Correct sizing & placement.** The notch's width is derived from the screen's `auxiliaryTopLeftArea`/`auxiliaryTopRightArea` (the status-bar regions bracketing the physical notch); its height from `safeAreaInsets.top` (or menu-bar height on notch-less external displays). The window is centered on the full screen width and pinned to the top.
6. **Lock-screen path.** A second mechanism (`BoringNotchSkyLightWindow` + the `SkyLightWindow` package) delegates the window into the SkyLight compositor space so it can appear *over the lock screen* — a separate compositor context the CGS space can't reach. It's toggled on `com.apple.screenIsLocked`/`Unlocked` notifications.
7. **Multi-display & lifecycle.** Optionally one window per screen (keyed by a per-display UUID from `CGDisplayCreateUUIDFromDisplayID`); rebuilt on `didChangeScreenParametersNotification`.

## The non-obvious parts
- **`flag = 0x1` in `CGSSpaceCreate` is load-bearing.** A code comment warns that any other value makes Finder draw desktop icons *on top of* the space. Pure undocumented-API folklore you'd never guess.
- **Two layering systems run in parallel, for two contexts.** The CGS space (level `Int32.max`) handles the normal desktop + Spaces + fullscreen. SkyLight handles the lock screen, which is a different compositor the CGS approach can't touch. You need both to be "always visible, even locked."
- **`@_silgen_name` vs `dlopen`.** The CGS functions are bound at link time by symbol name (`@_silgen_name`) as if they had a header; the SkyLight removal function is loaded at *runtime* via `dlopen`/`dlsym` from `/System/Library/PrivateFrameworks/SkyLight.framework`. Two different ways to call private C, chosen per stability.
- **It centers on full screen width, not the notch's X.** The window spans and centers across the whole screen; the *content* clips to the notch because the notch width was computed from the auxiliary areas. Simpler than trying to position a tiny window exactly over the notch.
- **`sharingType = .none`** hides the window from screen-recording/`CGWindowList` capture when the user enables that privacy toggle.
- **The non-SkyLight `BoringNotchWindow` may be vestigial** — the factory always instantiates the SkyLight subclass in the code read.

## Related
- [[system-hud-replacement--from-boring-notch]] — renders its HUD inside this window.
- [[multi-provider-media-control--from-boring-notch]] — the music UI shown in this window.
- See also: [[local-first-architecture--from-open-design]] — another macOS/desktop integration pattern.
