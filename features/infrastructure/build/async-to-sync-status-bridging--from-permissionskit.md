# Async-to-Sync Status Bridging (build spec) — distilled from PermissionsKit

## Summary

Expose a *synchronous* getter over a system API that only answers *asynchronously*, by parking the calling thread on a `DispatchSemaphore` until the async callback (run on a different queue) delivers its result. Use this to keep a uniform synchronous interface (`status` is a plain property) even when one or two backing APIs are callback-only. For delegate-based APIs (no callback to wrap), use the sibling pattern: anchor the delegate in a static property so it survives the async round-trip, then nil it out in the completion.

## Core logic (inlined)

**Semaphore bridge (notification status — the canonical form):**

```swift
private func fetchAuthorizationStatus() -> UNAuthorizationStatus? {
    var notificationSettings: UNNotificationSettings?
    let semaphore = DispatchSemaphore(value: 0)

    // CRITICAL: dispatch the async work to a DIFFERENT queue than the one we block.
    DispatchQueue.global().async {
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            notificationSettings = settings
            semaphore.signal()            // wake the parked thread
        }
    }

    semaphore.wait()                      // park here until signal()
    return notificationSettings?.authorizationStatus
}

public override var status: Permission.Status {
    guard let s = fetchAuthorizationStatus() else { return .notDetermined }
    switch s {
    case .authorized:    return .authorized
    case .denied:        return .denied
    case .notDetermined: return .notDetermined
    case .provisional:   return .authorized   // treat soft-grants as authorized
    case .ephemeral:     return .authorized
    @unknown default:    return .denied
    }
}
```

**Static-anchor bridge (location — delegate-based, no callback to wrap):**

```swift
// A CLLocationManager delegate is deallocated the moment nothing strongly references it,
// which would abort the authorization round-trip. Anchor it in a static slot for the
// request's lifetime, then release it.
final class LocationWhenInUseHandler: NSObject, CLLocationManagerDelegate {
    static var shared: LocationWhenInUseHandler?
    private let manager = CLLocationManager()
    private var completion: (() -> Void)?

    func requestPermission(completion: @escaping () -> Void) {
        self.completion = completion
        manager.delegate = self
        manager.requestWhenInUseAuthorization()
    }
    func locationManagerDidChangeAuthorization(_ m: CLLocationManager) {
        completion?()      // fired when the user answers
    }
}

// caller:
LocationWhenInUseHandler.shared = LocationWhenInUseHandler()
LocationWhenInUseHandler.shared?.requestPermission {
    DispatchQueue.main.async {
        completion()
        LocationWhenInUseHandler.shared = nil   // release the anchor AFTER completion
    }
}
```

**Location status must match the requested level** (don't report `.always` authorized when only `.whenInUse` was granted):

```swift
// for .location(access: .whenInUse):
return (clStatus == .authorizedWhenInUse) ? .authorized : .denied
// for .location(access: .always):
return (clStatus == .authorizedAlways) ? .authorized : .denied
```

## Data contracts

- **Semaphore**: `DispatchSemaphore(value: 0)`. Initial 0 ⇒ `wait()` blocks until a matching `signal()`. Exactly one `signal()` per `wait()`.
- **Result variable**: written inside the async callback, read after `wait()` returns. The wait/signal pair provides the happens-before ordering that makes the cross-thread read safe.
- **Static anchor**: `static var shared: Handler?` — non-nil for the duration of one request, set back to `nil` inside the completion. One in-flight request per handler type at a time.
- **Status mapping**: provisional/ephemeral notification grants → `.authorized`; location grant must equal requested access level or → `.denied`.

## Dependencies & assumptions

- `Dispatch` (`DispatchSemaphore`, `DispatchQueue.global()`). Foundation. The relevant system framework (`UserNotifications`, `CoreLocation`).
- Assumes the bridged query is *fast* (a settings/status read), so the bounded block is negligible.
- Assumes the async callback is guaranteed to fire exactly once (true for `getNotificationSettings`). If a callback might not fire, add `wait(timeout:)` or you hang forever.

## To port this, you need:
- [ ] A semaphore-bridge helper for each callback-only status API you must expose synchronously.
- [ ] A guarantee the async work runs on a **different** queue from the one you block (else deadlock).
- [ ] A static-anchor handler for each delegate-only API, released in the completion.
- [ ] A status mapping that folds the native enum onto your normalized states (see [[permissions/unified-permission-abstraction--from-permissionskit]]).
- [ ] A rule to never call the blocking getter on the main thread in hot paths.

## Gotchas

- **Same-queue deadlock is the killer bug.** If you `DispatchQueue.global().async` *and* `wait()` on the *same* serial queue, the callback can never run because the queue is blocked waiting for it. The pattern works only because the async dispatch targets a different (concurrent global) queue than the caller. This is the one thing people copy wrong.
- **No timeout = potential permanent hang.** If the system callback never fires (rare, but possible under odd states), `semaphore.wait()` blocks forever and freezes whatever thread called it. For untrusted callbacks use `wait(timeout: .now() + N)` and treat timeout as `notDetermined`/`denied`.
- **Don't call the blocking getter on the main thread repeatedly.** Each call can stall the run loop for the duration of the system query → UI hitches. Cache, or read off-main.
- **Releasing the static anchor too early aborts the request.** Set `shared = nil` only *inside* the completion, after the answer arrives — not right after kicking off the request.
- **Provisional/ephemeral are real states.** Mapping them to `.authorized` is a product choice (they *can* deliver notifications); if your UX needs to distinguish "full" from "provisional," don't collapse them.
- **One in-flight request per static handler.** A second request while the first is pending overwrites `shared` and orphans the first. Guard or queue if concurrent requests are possible.

## Origin (reference only)

Repo: https://github.com/sparrowcode/PermissionsKit · `Sources/NotificationPermission/NotificationPermission.swift` (`fetchAuthorizationStatus()` semaphore bridge), `Sources/LocationPermission/LocationPermission.swift` + `Sources/LocationPermission/Handlers/` (static-anchor delegate pattern). MIT, Sparrow Code LTD.
