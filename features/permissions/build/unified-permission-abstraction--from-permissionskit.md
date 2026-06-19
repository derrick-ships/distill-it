# Unified Permission Abstraction (build spec) — distilled from PermissionsKit

## Summary

Build one abstract `Permission` base class that normalizes every native platform permission API onto a single shape: a `status` getter returning one of four states, a `request(completion:)` method, derived `authorized`/`denied`/`notDetermined` booleans, and a shared `openSettingPage()`. Each concrete permission (camera, notification, location, …) subclasses it and implements only `status` + `request`, translating the OS-specific API into the common vocabulary. Sub-flavored permissions (calendar full/write, location whenInUse/always, notification option sets) carry their configuration *inside* an associated-value `Kind` enum case so the public type count stays small.

## Core logic (inlined)

**The four-state status model** (the normalization target — every native enum maps onto this):

```swift
@objc public enum Status: Int, CustomStringConvertible {
    case authorized
    case denied
    case notDetermined
    case notSupported   // permission doesn't exist on this OS/platform
}
```

**The Kind enum** — flat cases for simple permissions, associated values for sub-flavored ones:

```swift
public enum Kind {
    case camera
    case notification(access: Set<NotificationAccess>)
    case photoLibrary
    case microphone
    case calendar(access: CalendarAccess)   // .full | .write
    case contacts
    case reminders
    case speech
    case location(access: LocationAccess)   // .whenInUse | .always
    case motion
    case mediaLibrary
    case bluetooth
    case tracking
    case faceID
    case siri
    case health
}

public enum CalendarAccess { case full, write }
public enum LocationAccess { case whenInUse, always }
public enum NotificationAccess {
    case badge, sound, alert, carPlay, criticalAlert,
         providesAppNotificationSettings, provisional,
         announcement, timeSensitive
}
```

**The abstract base class** — common behavior written once; the two real blanks are `kind`, `status`, `request`:

```swift
open class Permission {
    // Subclasses MUST override these three:
    open var kind: Permission.Kind { preconditionFailure("override") }
    open var status: Permission.Status { preconditionFailure("override") }
    open func request(completion: @escaping () -> Void) {
        preconditionFailure("This method must be overridden.")
    }

    // Derived once, never re-implemented by subclasses:
    open var authorized: Bool     { status == .authorized }
    open var denied: Bool         { status == .denied }
    open var notDetermined: Bool  { status == .notDetermined }

    // Identical for every permission — send user to Settings to reverse a denial:
    open func openSettingPage() {
        DispatchQueue.main.async {
            guard let url = URL(string: UIApplication.openSettingsURLString) else { return }
            if UIApplication.shared.canOpenURL(url) {
                UIApplication.shared.open(url, completionHandler: nil)
            }
        }
    }
}
```

**A simple concrete subclass (Camera)** — the canonical "map the native enum, bounce completion to main" template:

```swift
// import AVFoundation
public override var status: Permission.Status {
    switch AVCaptureDevice.authorizationStatus(for: .video) {
    case .authorized:    return .authorized
    case .denied:        return .denied
    case .notDetermined: return .notDetermined
    case .restricted:    return .denied     // collapse restricted -> denied (no actionable difference)
    @unknown default:    return .denied
    }
}

public override func request(completion: @escaping () -> Void) {
    AVCaptureDevice.requestAccess(for: .video) { _ in
        DispatchQueue.main.async { completion() }   // ALWAYS hop to main
    }
}
```

**A sub-flavored subclass reads its associated value** (notification example) to decide what to ask for:

```swift
public override func request(completion: @escaping () -> Void) {
    let center = UNUserNotificationCenter.current()
    switch kind {
    case .notification(let access):
        let options = UNAuthorizationOptions(access.map { $0.userNotificationAuthorizationOptions })
        center.requestAuthorization(options: options) { _, _ in
            DispatchQueue.main.async { completion() }
        }
    default: fatalError()
    }
}
```

## Data contracts

- **`Status`**: `{ authorized | denied | notDetermined | notSupported }`. This is the only status vocabulary the rest of your app ever sees. Every native authorization enum (AVAuthorizationStatus, UNAuthorizationStatus, CLAuthorizationStatus, PHAuthorizationStatus, CNAuthorizationStatus, …) gets switch-mapped onto these four. Default unknown/restricted → `denied`.
- **`Kind`**: identity + configuration in one value. Simple permission = bare case; configurable permission = case with an associated `Access` value/set. Subclasses read `kind` to branch.
- **`request(completion: @escaping () -> Void)`**: fire-and-forget; no granted-bool is surfaced (caller re-reads `status` afterward if it cares). Completion always delivered on the main thread.
- **Status getter**: synchronous. For native APIs that are async-only, bridge them (see [[infrastructure/async-to-sync-status-bridging--from-permissionskit]]) so this contract holds.

## Dependencies & assumptions

- Swift; per-permission native frameworks (`AVFoundation`, `UserNotifications`, `CoreLocation`, `Contacts`, `EventKit`, `Photos`, `HealthKit`, `CoreMotion`, `MediaPlayer`, `CoreBluetooth`, `AppTrackingTransparency`, `LocalAuthentication`, `Intents`, `Speech`).
- `openSettingPage()` is UIKit-only (`UIApplication`) — gate it with `#if canImport(UIKit)` for macOS/watchOS.
- Each native permission requires its Info.plist usage-description key (e.g. `NSCameraUsageDescription`, `NSContactsUsageDescription`). The library can't add these for you.
- Assumes the caller re-reads `status` after `request` rather than relying on a granted flag.

## To port this, you need:
- [ ] A base type with three overridable members (`kind`, `status`, `request`) that crash if not overridden.
- [ ] A 4-case `Status` enum and a mapping from each native authorization enum onto it (fold restricted/unknown → denied; add `notSupported` for absent-on-platform).
- [ ] A `Kind` enum where sub-flavored permissions carry an associated `Access` value/set instead of spawning new subclasses.
- [ ] Derived `authorized`/`denied`/`notDetermined` on the base, never per-subclass.
- [ ] A shared "open settings" affordance (platform-gated).
- [ ] Every `request` completion wrapped in a main-thread dispatch.
- [ ] Info.plist usage keys for every permission you wire up.

## Gotchas

- **Forgetting the Info.plist usage key = instant crash** when the OS prompt is triggered. This is the #1 integration failure; it's on the consumer, not the library.
- **iOS denials are sticky.** Once denied, re-`request()` is a no-op (no prompt). The only recovery is `openSettingPage()`. Build your UX around "denied → deep-link to Settings," not "ask again."
- **`restricted` ≠ `denied` semantically** (restriction is system/parental, not user choice) but PermissionsKit deliberately maps both to `denied` because the app's options are identical. If your product genuinely needs to distinguish them, don't copy this collapse.
- **Main-thread bounce is mandatory.** Native permission callbacks fire on arbitrary queues; UI updates in them without the `DispatchQueue.main.async` wrapper cause undefined behavior / crashes.
- **Location's granted-level must match requested-level.** Don't report `.authorized` for `.always` when the user only granted `.whenInUse` — check both the CLAuthorizationStatus *and* the requested access in `kind`.
- **`@objc enum` requires `Int` raw values** if you need Objective-C interop; drop `@objc` for pure-Swift.
- **Don't read a (potentially blocking) `status` on the main thread in a hot loop** — see the bridging spec.

## Origin (reference only)

Repo: https://github.com/sparrowcode/PermissionsKit · `Sources/PermissionsKit/Permission.swift` (base class + `Status`/`Kind`/`*Access` enums), `Sources/CameraPermission/CameraPermission.swift` (simple subclass), `Sources/NotificationPermission/NotificationPermission.swift` (sub-flavored subclass). MIT, Sparrow Code LTD.
