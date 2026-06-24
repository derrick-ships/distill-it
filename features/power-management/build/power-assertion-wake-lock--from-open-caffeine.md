# Power-Assertion Wake Lock (build spec) — distilled from open-caffeine

## Summary
Prevent macOS idle sleep for a chosen duration, with a live countdown and an optional low-battery cutoff. Built so the assert/release lifecycle is leak-proof and fully unit-testable: the one OS call is hidden behind a protocol; all policy is plain Swift.

## Core logic (inlined)

**1. The OS seam.** One protocol over the two IOKit calls; the live impl is the only OS-touching code.
```swift
protocol PowerAssertionAPI {
    func create(type: String, reason: String, id: inout IOPMAssertionID) -> IOReturn
    func release(id: IOPMAssertionID) -> IOReturn
}
struct IOKitPowerAssertionAPI: PowerAssertionAPI {
    func create(type: String, reason: String, id: inout IOPMAssertionID) -> IOReturn {
        IOPMAssertionCreateWithName(type as CFString,
            IOPMAssertionLevel(kIOPMAssertionLevelOn), reason as CFString, &id)
    }
    func release(id: IOPMAssertionID) -> IOReturn { IOPMAssertionRelease(id) }
}
```

**2. Assertion type = a product choice.**
```swift
enum SleepAssertionKind {            // .displayAndSystem keeps screen+system; .systemOnly lets screen sleep
    case displayAndSystem, systemOnly
    var ioKitAssertionType: String {
        switch self {
        case .displayAndSystem: return kIOPMAssertPreventUserIdleDisplaySleep
        case .systemOnly:       return kIOPMAssertPreventUserIdleSystemSleep
        }
    }
}
```

**3. Leak-proof lifecycle object.** Re-acquire releases first; deinit always releases; a failed release still goes inactive.
```swift
final class SleepAssertion {
    private var assertionID = IOPMAssertionID(0)
    private(set) var isActive = false
    private let api: PowerAssertionAPI
    private let kind: () -> SleepAssertionKind        // read live so a pref change applies on re-acquire
    deinit { release() }
    func acquire() throws {
        if isActive { release() }
        var newID: IOPMAssertionID = 0
        let r = api.create(type: kind().ioKitAssertionType, reason: reason, id: &newID)
        guard r == kIOReturnSuccess else { throw SleepAssertionError.ioReturnFailure(r) }
        assertionID = newID; isActive = true
    }
    func release() {
        guard isActive else { return }
        _ = api.release(id: assertionID)             // even if this fails, go inactive
        assertionID = 0; isActive = false
    }
}
```

**4. Session = assertion + timer + derived countdown.**
```swift
enum SessionState {
    case idle, active(duration: Duration, startedAt: Date)
    func remaining(now: Date) -> TimeInterval? {     // nil for Forever, 0 once elapsed
        guard case .active(let d, let s) = self, let total = d.timeInterval else { return nil }
        return max(0, total - now.timeIntervalSince(s))
    }
}
// start: try assertion.acquire(); state = .active(duration, clock()); schedule one-shot Timer -> stop(.expired)
// stop:  expiryTimer.invalidate(); assertion.release(); state = .idle
// clock is injected (() -> Date) so timing is testable.
```

**5. Battery cutoff (separate watcher).** Pure parser + thin reader + threshold compare.
```swift
enum BatterySnapshotParser {                          // pure, fully tested
    static func parse(_ descs: [[String: AnyObject]]) -> (hasBattery: Bool, percent: Int) {
        for d in descs {
            if let maxCap = d[kIOPSMaxCapacityKey] as? Int, let cur = d[kIOPSCurrentCapacityKey] as? Int, maxCap > 0 {
                return (true, Int(Double(cur)/Double(maxCap)*100))
            }
        }
        return (false, 0)
    }
}
// SystemBatteryProvider (excluded from coverage): IOPSCopyPowerSourcesInfo -> IOPSCopyPowerSourcesList
//   -> IOPSGetPowerSourceDescription -> BatterySnapshotParser.parse
// BatteryMonitor.evaluate(): let s = provider.currentBattery(); if threshold()>0 && s.hasBattery && s.percent<threshold() { onLow() }
// Observe live with IOPSNotificationCreateRunLoopSource(callback, context) on the main runloop; the C callback
//   must be capture-free, so pass self via Unmanaged opaque context and bridge back inside the trampoline.
```

## Data contracts
- `IOPMAssertionID` (UInt32). `IOReturn` (Int32); success == `kIOReturnSuccess`.
- IOPS power-source description dict keys: `kIOPSMaxCapacityKey`, `kIOPSCurrentCapacityKey` (Ints).

## Dependencies & assumptions
- `IOKit.pwr_mgt` (assertions) and `IOKit.ps` (power sources). Foundation `Timer`/`RunLoop`. No special entitlement needed; works in a hardened-runtime app.
- macOS only. The pattern (hold a named OS resource, release on deinit, drive from a timer/threshold) ports to any platform with a sleep-inhibit API (Windows `SetThreadExecutionState`, Linux systemd-inhibit).

## To port this, you need:
- [ ] An injectable seam over the OS sleep-inhibit call (so the lifecycle is testable).
- [ ] A session object that owns a one-shot timer and an injected clock.
- [ ] Derived-countdown state (store start+duration, compute remaining).
- [ ] (Optional) a battery reader split into a pure parser + thin OS fetch + threshold compare.

## Gotchas
- **Leaks keep the Mac awake forever.** Always release on deinit and on every stop path; re-acquire must release the prior id first.
- **Pick the right assertion type.** `PreventUserIdleSystemSleep` does NOT keep the display on; `PreventUserIdleDisplaySleep` keeps both.
- **The IOPS notification callback is a C function pointer** — it must be capture-free; pass `self` via an `Unmanaged` opaque context and bridge back inside the trampoline.
- Releasing an already-released / zero id is harmless but guard `isActive` to avoid noise.

## Origin (reference only)
`OpenCaffeine/Services/SleepAssertion.swift`, `Models/SleepAssertionKind.swift`, `Services/SystemAdapters.swift`, `Services/CaffeineSession.swift`, `Models/SessionState.swift`, `Models/Duration.swift`, `Services/BatteryMonitor.swift`, `Services/SystemBatteryProvider.swift`.
