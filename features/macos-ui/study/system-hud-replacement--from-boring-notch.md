# System HUD Replacement (volume/brightness/backlight) — from [boring.notch](https://github.com/TheBoredTeam/boring.notch)

> Domain: [[_domain]] · Source: https://github.com/TheBoredTeam/boring.notch · NotebookLM: <add link>

## What it does
When you press the volume, brightness, or keyboard-backlight keys, macOS's big translucent HUD square never appears — instead the change shows up as a sleek indicator inside the notch. The app intercepts the key, performs the actual system change itself, and draws its own HUD. To the user it feels like Apple's HUD got a tasteful redesign that lives in the notch.

## Why it exists
Apple's default volume/brightness HUD is a large square in the middle of the screen — visually heavy and not something apps can restyle. A notch app wants those system changes to surface *in the notch*, consistent with the rest of its UI. The job-to-be-done is "take over the media keys: suppress Apple's HUD, still actually change the volume/brightness, and render our own indicator." The hard parts are intercepting the keys early enough to stop the default HUD, and performing brightness/backlight changes (which need private APIs).

## How it actually works
1. **Intercept at the HID level.** A `CGEventTap` is installed at `.cghidEventTap` / `.headInsertEventTap` listening for system-defined events (`CGEventType(rawValue: 14)`, i.e. `NX_SYSDEFINED` — the events media/function keys generate). The tap runs on the main run loop.
2. **Suppress by consuming.** The tap callback returns `nil` instead of the event. Because it's a `.defaultTap` (not listen-only), returning `nil` *deletes* the event from the stream — so macOS never processes the key and the default OSD HUD never fires. There's no separate "disable system HUD" call; suppression *is* the consumption.
3. **Decode which key.** The event is read as an `NSEvent` (`.systemDefined`, subtype 8); the key code and up/down state are unpacked from `data1` bit fields (e.g. soundUp=0, soundDown=1, brightnessUp=2, brightnessDown=3, mute=7, keyboardBrightnessUp=21, down=22). Only key-down is acted on.
4. **Perform the change:**
   - **Volume** — pure public CoreAudio: find the default output device, read/write `kAudioDevicePropertyVolumeScalar` (and `kAudioDevicePropertyMute`) via `AudioObjectGetPropertyData`/`SetPropertyData`. It even listens for *external* volume changes and has a software-mute fallback (save level, set 0, restore).
   - **Brightness / keyboard backlight** — these need private APIs, so the calls are delegated to a separate **XPC helper process** (`XPCHelperClient.setScreenBrightness`, `.setKeyboardBrightness`). The private API itself lives in the helper, out of the sandboxed main app.
5. **Show + auto-hide the HUD.** After changing the value, the manager calls `BoringViewCoordinator.toggleSneakPeek(type: .volume/.brightness/.backlight, value:)`, which makes the notch render a HUD view (`InlineHUD` when closed, `OpenNotchHUD` when open) with an SF-Symbol icon picked by value range and a draggable progress bar. A `lastChangeAt` timestamp + a 1.2-second window drives the auto-hide.

## The non-obvious parts
- **Suppression is just "return `nil`."** No `OSDUIHelper` poking, no `defaults write`, no private entitlement — a `.defaultTap` that drops the event before the system's media-key handler sees it. Elegant and the whole trick.
- **`CGEventType(rawValue: 14)` (`NX_SYSDEFINED`) isn't in the public enum** — it's a stable but undocumented constant you have to construct by raw value. The actual key identity lives in `NSEvent.data1` bit fields, not in any tidy API.
- **The tap must be at `.cghidEventTap` / `.headInsertEventTap`** — the HID source, *before* the window server, which is why it catches system keys that bypass normal app key handling. It also means the app needs **Accessibility permission**, and a listen-only tap wouldn't be able to suppress.
- **Volume is public, brightness is private — hence the split.** Volume rides entirely on CoreAudio public APIs. Brightness/backlight require private display/IOKit calls, so they're quarantined in an XPC helper to survive sandboxing (the helper also owns the accessibility-auth prompt).
- **Software mute fallback** — if the device lacks a hardware mute property, it fakes mute by zeroing and restoring the scalar volume; and when master element 0 is absent it averages channels 1–4.
- **Modifier nuance** — Option (no Shift) can open the relevant System Settings pane or show a value-only HUD; Option+Shift makes adjustments fine-grained (step ÷4). Volume up/down can also play the system bezel click sound, gated on the user's beep-feedback setting.

## Related
- [[notch-shaped-window--from-boring-notch]] — the window the HUD draws inside.
- [[multi-provider-media-control--from-boring-notch]] — sibling integration; media volume vs. system volume.
- See also: [[local-first-architecture--from-open-design]] — another desktop/system-integration pattern.
