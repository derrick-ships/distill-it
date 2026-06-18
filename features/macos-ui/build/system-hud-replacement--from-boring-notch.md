# System HUD Replacement (build spec) — distilled from boring.notch

## Summary
Intercept the volume/brightness/keyboard-backlight keys at the HID level with a `CGEventTap`, suppress macOS's default OSD by *consuming* the event (return `nil`), perform the change yourself (volume via public CoreAudio; brightness/backlight via a private API in an XPC helper), then render your own HUD with an auto-hide timer. macOS 14+, Swift. Requires Accessibility permission for the tap.

## Core logic (inlined)

### Event tap + suppression — `MediaKeyInterceptor.swift`
```swift
private let kSystemDefinedEventType = CGEventType(rawValue: 14)!   // NX_SYSDEFINED (not in public enum)
let mask = CGEventMask(1 << kSystemDefinedEventType.rawValue)
eventTap = CGEvent.tapCreate(
    tap: .cghidEventTap,          // HID source — before window server; catches system keys
    place: .headInsertEventTap,
    options: .defaultTap,         // MUST be .defaultTap (not .listenOnly) to be able to drop events
    eventsOfInterest: mask,
    callback: { proxy, type, event, refcon in /* -> handleEvent */ },
    userInfo: ...)
let src = CFMachPortCreateRunLoopSource(nil, eventTap, 0)
CFRunLoopAddSource(CFRunLoopGetMain(), src, .commonModes)
CGEvent.tapEnable(tap: eventTap, enable: true)

private func handleEvent(_ cgEvent: CGEvent) -> Unmanaged<CGEvent>? {
    // parse NSEvent from cgEvent; decode key + state; act on key-down
    handleKeyPress(...)
    return nil          // <-- consume: default OSD HUD never fires
}
```

### Decoding the key (NSEvent.data1 bit fields)
```swift
// NSEvent type .systemDefined, subtype 8
let keyCode   = (data1 & 0xFFFF_0000) >> 16
let stateByte = (data1 & 0x0000_FF00) >> 8     // 0xA = down, 0xB = up
// NXKeyType: soundUp=0, soundDown=1, brightnessUp=2, brightnessDown=3, mute=7,
//            keyboardBrightnessUp=21, keyboardBrightnessDown=22
// act only on key-down
```

### Volume — public CoreAudio — `VolumeManager.swift`
```swift
// default output device:
AudioObjectGetPropertyData(kAudioObjectSystemObject, &addr(kAudioHardwarePropertyDefaultOutputDevice), …)
// read/write scalar volume:
var addr = AudioObjectPropertyAddress(mSelector: kAudioDevicePropertyVolumeScalar,
                                      mScope: kAudioDevicePropertyScopeOutput,
                                      mElement: kAudioObjectPropertyElementMain)   // fallback: channels 1–4 averaged
AudioObjectGetPropertyData(deviceID, &addr, 0, nil, &size, &vol)
AudioObjectSetPropertyData(deviceID, &addr, 0, nil, size, &newVol)
// mute: kAudioDevicePropertyMute ; external-change listener: AudioObjectAddPropertyListenerBlock
// software-mute fallback: save level -> set 0 -> restore on unmute
```

### Brightness / keyboard backlight — private API behind XPC — `BrightnessManager.swift`
```swift
// NOT called in-process. Delegated to the XPC helper:
await XPCHelperClient.shared.currentScreenBrightness()
await XPCHelperClient.shared.setScreenBrightness(target)
await XPCHelperClient.shared.currentKeyboardBrightness()
await XPCHelperClient.shared.setKeyboardBrightness(target)
await XPCHelperClient.shared.requestAccessibilityAuthorization()
// the actual private API (DisplayServices/IOKit/CoreDisplay) lives in the helper process — NOT in these files (gap)
```

### HUD trigger + auto-hide
```swift
// after each change:
BoringViewCoordinator.shared.toggleSneakPeek(status: true, type: .volume /* .brightness/.backlight */, value: CGFloat(target))
// auto-hide (same pattern in each manager):
let visibleDuration: TimeInterval = 1.2
var shouldShowOverlay: Bool { Date().timeIntervalSince(lastChangeAt) < visibleDuration }   // lastChangeAt stamped per change
```

### HUD views
- `InlineHUD` (closed notch): icon + label | black notch-gap spacer | `DraggableProgressBar`.
- `OpenNotchHUD` (open notch): capsule; icon + `DraggableProgressBar` + optional `"\(Int(value*100))%"`.
- `DraggableProgressBar` (in `SystemEventIndicatorModifier.swift`): GeometryReader capsule, drag gesture → `onChange` → e.g. `VolumeManager.shared.setAbsolute(Float32(v))`.
- Icon by value range (SF Symbols): volume `speaker(.wave.1/2/3)`/`.slash`; brightness `sun.min`/`sun.max`; backlight `light.min`/`light.max`.

### Modifiers + feedback
- Option (no Shift) → `handleOptionAction`: open System Settings pane / show value-only HUD / nothing (`Defaults[.optionKeyAction]`).
- Option+Shift → fine step (÷4).
- Volume change plays bezel click `…/BezelServices.loginPlugin/Contents/Resources/volume.aiff` via `AVAudioPlayer`, gated on `NSGlobalDomain com.apple.sound.beep.feedback == 1`.

## Data contracts
- `@Published rawVolume`, `isMuted`, `lastChangeAt` (VolumeManager); `rawBrightness`, `lastChangeAt` (Brightness/KeyboardBacklight).
- HUD trigger: `BoringViewCoordinator.toggleSneakPeek(status:Bool, type:SneakContentType, value:CGFloat)`; `type ∈ {.volume,.brightness,.backlight,…}`.
- Feature gate: `Defaults[.hudReplacement]` (if false, the interceptor doesn't start). Also `Defaults[.optionKeyAction]`, `.inlineHUD`, `.showClosedNotchHUDPercentage`.

## Dependencies & assumptions
- Public: CoreGraphics event taps, CoreAudio (`AudioObject*`), AppKit/SwiftUI, `AVAudioPlayer`.
- Private: brightness/backlight APIs — isolated in an XPC helper process (not in these files).
- **Accessibility permission required** (the tap uses `.defaultTap`); the XPC helper also drives the auth prompt.

## To port this, you need:
- [ ] A `CGEventTap` at `.cghidEventTap`/`.headInsertEventTap`, `.defaultTap`, mask for `NX_SYSDEFINED (14)`, on the main run loop.
- [ ] A callback that decodes the key from `NSEvent.data1` and returns `nil` to consume (suppress the default HUD).
- [ ] Volume via CoreAudio `kAudioDevicePropertyVolumeScalar`/`Mute` (+ external-change listener + software-mute fallback).
- [ ] Brightness/backlight via the platform's private API — ideally inside a helper process to survive sandboxing.
- [ ] A HUD trigger + `lastChangeAt`/visibleDuration auto-hide, and SwiftUI HUD views with range-based icons.
- [ ] Accessibility-permission request/handling.

## Gotchas
- **Must be `.defaultTap`** — a listen-only tap can observe but cannot drop the event, so the default HUD would still show.
- **`CGEventType(rawValue: 14)`** is undocumented; the key identity is in `data1` bit fields, not a clean API.
- **Accessibility permission is mandatory** and the tap silently does nothing without it — detect and prompt.
- **Brightness needs private APIs** → keep them in a helper process; don't expect them to work from a sandboxed main app, and they may break across macOS versions (the exact symbols weren't captured here — verify).
- **Volume channel quirks** — handle missing master element 0 (average 1–4) and missing hardware mute (software fallback).
- **Re-enable the tap if disabled** — the system can disable a tap on timeout; watch for `tapDisabledByTimeout` and call `tapEnable` again (standard event-tap hygiene).

## Origin (reference only)
Repo: https://github.com/TheBoredTeam/boring.notch · Files (read verbatim): `observers/MediaKeyInterceptor.swift`, `managers/VolumeManager.swift`, `managers/BrightnessManager.swift` (contains `KeyboardBacklightManager`), `components/Live activities/{InlineHUD,SystemEventIndicatorModifier,OpenNotchHUD}.swift`. GAPS: `XPCHelperClient` private brightness/backlight API identity, `BoringViewCoordinator.toggleSneakPeek` internals, and `SneakContentType` cases not read — verify before relying.
