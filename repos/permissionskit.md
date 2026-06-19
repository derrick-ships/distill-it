# permissionskit

**Source:** https://github.com/sparrowcode/PermissionsKit
**Product:** PermissionsKit (formerly SPPermissions) — a Swift framework that gives Apple-platform apps one consistent API to request 18 system permissions and check their status. Instead of learning a different inconsistent API per permission (AVFoundation for camera, UserNotifications for notifications, CoreLocation for location, …), every permission is requested the same way (`Permission.camera.request {}`) and reports one of four normalized states (authorized / denied / notDetermined / notSupported). Works with both UIKit and SwiftUI. Maintained by Sparrow Code LTD; classic open-source developer-tooling (be the trusted default for a chore everyone has).
**Stack:** Swift 5.9 (92.5%). Platforms: iOS 12+, macOS 13+, tvOS 12+, watchOS 4+, visionOS. 18 permission types: Bluetooth, Calendar (full/write), Camera, Contacts, FaceID, Health, Location (whenInUse/always), Media Library, Microphone, Motion, Notifications (option sets), Photo Library, Reminders, Siri, Speech Recognition, Tracking. Distributed via Swift Package Manager (15+ per-permission library products over a `PermissionsKit` core) and CocoaPods (per-permission subspecs). Per-permission conditional-compilation flags (`PERMISSIONSKIT_CAMERA`, …) + a `PERMISSIONSKIT_SPM` build-system seam. MIT.
**Distilled:** 2026-06-18

## Features distilled

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Unified Permission Abstraction | permissions | [study](../features/permissions/study/unified-permission-abstraction--from-permissionskit.md) | [build](../features/permissions/build/unified-permission-abstraction--from-permissionskit.md) |
| Modular Per-Permission Packaging | infrastructure | [study](../features/infrastructure/study/modular-permission-packaging--from-permissionskit.md) | [build](../features/infrastructure/build/modular-permission-packaging--from-permissionskit.md) |
| Async-to-Sync Status Bridging | infrastructure | [study](../features/infrastructure/study/async-to-sync-status-bridging--from-permissionskit.md) | [build](../features/infrastructure/build/async-to-sync-status-bridging--from-permissionskit.md) |

## Not yet distilled (candidates)

- **Per-permission status/request implementations** (`Sources/<Name>Permission/`): the remaining 15 concrete subclasses (Contacts/EventKit, Photos, HealthKit, CoreMotion, MediaPlayer, CoreBluetooth, AppTrackingTransparency, LocalAuthentication/FaceID, Intents/Siri, Speech, …). Each is a worked example of the abstraction's "map the native enum + bounce completion to main" template; the two representative ones (Camera simple, Notification/Location bridged) are inlined in the build docs. (permissions.)
- **Localization system** (`Sources/PermissionsKit/Resources/Localization/`): xliff-exported translated permission-name strings shared across all permission modules, looked up through the SPM/CocoaPods bundle seam. (infrastructure / i18n.)
- **Bluetooth & Tracking quirks**: CoreBluetooth and ATT have their own delegate/timing edge cases (ATT must be requested after app becomes active; Bluetooth status requires a live central manager) — a candidate deep-dive on platform-permission gotchas. (permissions.)

## Key takeaways

- **The product is normalization, not features.** PermissionsKit's entire value is collapsing 18 inconsistent native APIs into one shape: a synchronous `status` returning four states + a `request(completion:)` + a uniform `openSettingPage()`. Learn the pattern once, use it everywhere. The abstraction is an abstract base class whose only real blanks are `status` and `request`; everything else (derived booleans, settings deep-link) is written once.
- **Associated values keep the surface small.** Sub-flavored permissions (calendar full/write, location whenInUse/always, notification option sets) are expressed as data *inside* a `Kind` enum case rather than as separate permission classes — granularity without type explosion.
- **The packaging is a defensive App Review strategy, not just size optimization.** Splitting into per-permission modules means a consumer's binary only *references* the sensitive Apple frameworks for permissions they deliberately imported — avoiding review scrutiny over APIs they never use. This only holds because there's no umbrella product that re-exports everything.
- **Blocking a thread on purpose, safely.** To keep `status` synchronous over Apple's async-only APIs, it parks the caller on a `DispatchSemaphore` and signals from a callback dispatched to a *different* queue (the different-queue detail is the deadlock guard). Delegate-only APIs (location) use the sibling trick: anchor the delegate in a static property so it survives the round-trip, release it in the completion.
- **iOS denials are sticky → recovery is uniform.** Because a denied permission can't be re-prompted, every permission exposes the same "open Settings" affordance; the UX pattern is "denied → deep-link to Settings," never "ask again."
