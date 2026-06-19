# Domain: macos-ui

Native macOS desktop-integration patterns — owning unusual window real estate, drawing above the system UI, and taking over system inputs/indicators — usually by reaching past public AppKit into private window-server, CoreGraphics, and event APIs.

## What this domain is about

Some macOS experiences can't be built with public AppKit alone: a window that floats above the menu bar on every Space and in fullscreen, a UI that lives in the notch, or replacing the system's volume/brightness HUD. This domain captures the techniques — private CGS/SkyLight "spaces," `CGEventTap` interception, `NSScreen` notch geometry, XPC helpers for sandbox-restricted private APIs — and, critically, the honest fragility notes (these APIs are undocumented and can break on any OS update).

## Core patterns

- **Above-everything windows**: borderless non-activating `NSPanel` + collection behavior + a private CGS space at max compositor level; a separate SkyLight path for the lock screen
- **Event interception + suppression**: a `.defaultTap` `CGEventTap` at the HID source that consumes events (return `nil`) to suppress system behavior while you handle it yourself
- **Public vs private split**: do what you can with public APIs (CoreAudio volume); quarantine private APIs (brightness/backlight) in an XPC helper to survive sandboxing
- **Notch geometry**: derive size/placement from `NSScreen.safeAreaInsets` + `auxiliaryTop{Left,Right}Area`

## Features in this domain

- [[notch-shaped-window--from-boring-notch]] — borderless `NSPanel` shaped to the notch, pinned across Spaces/fullscreen via private `CGSSpace` at `Int32.max`, with a SkyLight path for the lock screen and `auxiliaryTopArea`/`safeAreaInsets` sizing
- [[system-hud-replacement--from-boring-notch]] — `CGEventTap` at `.cghidEventTap` consuming `NX_SYSDEFINED` keys to suppress Apple's HUD; volume via public CoreAudio, brightness/backlight via a private API in an XPC helper; custom auto-hiding notch HUD
