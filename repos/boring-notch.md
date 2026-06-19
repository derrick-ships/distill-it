# boring.notch

**Source:** https://github.com/TheBoredTeam/boring.notch
**Product:** A macOS (SwiftUI, macOS 14+) app that turns the MacBook notch into a dynamic control center — music controls + visualizer, a custom HUD replacing Apple's volume/brightness OSD, a drag-and-drop file shelf, calendar/reminders, live activities, and more. ~9.7k stars.
**Distilled:** 2026-06-18

## What this repo actually is
A mature, mostly-Swift native macOS app. The genuinely reusable engineering is in how it reaches *past* public AppKit to integrate with the system: private CoreGraphics/SkyLight window "spaces" to float the notch UI above everything (and over the lock screen), `CGEventTap` interception to take over the media keys, and a unified media-control layer spanning AppleScript apps, a private MediaRemote framework (bridged through a Perl `dlopen` subprocess), and a companion app's local web API. Private/display APIs that don't survive sandboxing are isolated in an XPC helper.

## Features distilled

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Notch-shaped always-on-top window | macos-ui | [study](../features/macos-ui/study/notch-shaped-window--from-boring-notch.md) | [build](../features/macos-ui/build/notch-shaped-window--from-boring-notch.md) |
| Multi-provider media / now-playing control | media-control | [study](../features/media-control/study/multi-provider-media-control--from-boring-notch.md) | [build](../features/media-control/build/multi-provider-media-control--from-boring-notch.md) |
| System HUD replacement (volume/brightness/backlight) | macos-ui | [study](../features/macos-ui/study/system-hud-replacement--from-boring-notch.md) | [build](../features/macos-ui/build/system-hud-replacement--from-boring-notch.md) |

## Distill notes / gaps
- All primary Swift sources for these three slices were read verbatim (window/CGSSpace, media controllers + the Perl adapter, MediaKeyInterceptor/VolumeManager/BrightnessManager/HUD views).
- GAPS noted in the build docs: the external `Lakr233/SkyLightWindow` package internals; the `XPCHelperClient` brightness/backlight *private API identity* (lives in the XPC helper, not read); `BoringViewCoordinator.toggleSneakPeek` internals; the bundled `MediaRemoteAdapter.framework`'s internal MediaRemote call graph; `AppleScriptHelper`/`ImageService`. Each is flagged "verify before relying."

## Not yet distilled (candidates)
- **Drag-and-drop file shelf** (`components/Shelf/*`) — persistence, thumbnails, QuickLook, AirDrop/share, clean MVVM service split.
- **XPC privileged helper** (`BoringNotchXPCHelper/*`, `XPCHelperClient/*`) — the brightness/backlight private-API host (the missing half of the HUD feature).
- **Metal audio visualizer** (`metal/visualizer.metal`, `components/Music/MusicVisualizer.swift`).
- **EventKit calendar/reminders** (`managers/CalendarManager.swift`, `Providers/CalendarServiceProviding.swift`).
- **Battery/charging live activity** (`managers/BatteryActivityManager.swift`, `Live activities/BoringBattery.swift`).
