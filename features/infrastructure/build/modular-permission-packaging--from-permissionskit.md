# Modular Per-Permission Packaging (build spec) — distilled from PermissionsKit

## Summary

Ship a multi-permission (or multi-capability) library as N independently-importable modules over one shared core, so consumers compile in *only* the slices they use. The payoff on Apple platforms is twofold: smaller binaries, and — more importantly — your consumer's binary only *references* the sensitive system frameworks (HealthKit, CoreBluetooth, AppTrackingTransparency, …) for the permissions they deliberately imported, which avoids App Review scrutiny over APIs they never use. Implement as: one core target + one target/product per permission, each gated by a per-feature `-D` compile flag, mirrored across SPM products and CocoaPods subspecs from a single source tree.

## Core logic (inlined)

**Package.swift — hub-and-spoke with per-feature compile flags:**

```swift
// products: one library per permission (consumers add only what they need)
products: [
    .library(name: "CameraPermission",       targets: ["CameraPermission"]),
    .library(name: "LocationPermission",     targets: ["LocationPermission"]),
    .library(name: "NotificationPermission", targets: ["NotificationPermission"]),
    // … one per permission
],

targets: [
    // THE HUB: shared base class, Status/Kind enums, localization resources.
    .target(
        name: "PermissionsKit",
        resources: [ .process("Resources") ],     // localized permission-name strings live ONCE here
        swiftSettings: [ .define("PERMISSIONSKIT_SPM") ]
    ),

    // A SPOKE: depends only on the hub; defines its own feature flag + the shared SPM flag.
    .target(
        name: "CameraPermission",
        dependencies: [ .target(name: "PermissionsKit") ],
        swiftSettings: [
            .define("PERMISSIONSKIT_CAMERA"),
            .define("PERMISSIONSKIT_SPM")
        ]
    ),
    // … one spoke per permission, each with its own PERMISSIONSKIT_<NAME> define
]
```

**Conditional compilation inside shared code** — the hub can carry permission-specific slices that only light up when that spoke is built:

```swift
#if PERMISSIONSKIT_CAMERA
// camera-only helpers compiled only when the camera target (which defines the flag) is built
#endif
```

**The dual-build seam** — the same `.swift` files are compiled under both SPM and CocoaPods; `PERMISSIONSKIT_SPM` distinguishes them (resource-bundle lookup and import paths differ between the two):

```swift
#if PERMISSIONSKIT_SPM
let bundle = Bundle.module          // SPM-generated resource bundle
#else
let bundle = Bundle(for: SomeClass.self)   // CocoaPods-style bundle lookup
#endif
```

**The dual-build seam** — the same `.swift` files are compiled under both SPM and CocoaPods; `PERMISSIONSKIT_SPM` distinguishes them (resource-bundle lookup and import paths differ between the two).

**CocoaPods podspec — subspecs mirror the SPM products:**

```ruby
s.subspec 'Camera' do |ss|
  ss.dependency 'SPPermissions/Core'
  ss.source_files = 'Sources/CameraPermission/**/*.swift'
  ss.pod_target_xcconfig = { 'OTHER_SWIFT_FLAGS' => '-DPERMISSIONSKIT_CAMERA' }
end
# consumer: pod 'SPPermissions/Camera'
```

## Data contracts

- **Dependency graph**: strict hub-and-spoke. Spokes depend on the hub; spokes never depend on each other. Adding a permission = add one product + one target + one `-D` flag; touches nothing else.
- **Compile flags**: `PERMISSIONSKIT_<FEATURE>` (per spoke, names the feature) + `PERMISSIONSKIT_SPM` (build-system selector, present on every SPM target, absent under CocoaPods).
- **Resources**: localized strings + assets live once in the core, processed via `.process("Resources")` (SPM) / a resource_bundle (CocoaPods), looked up through the bundle seam above.

## Dependencies & assumptions

- Swift Package Manager and/or CocoaPods. One git repo, one `Sources/` tree, two manifests (`Package.swift` + `.podspec`) describing the same split.
- Assumes a meaningful "core" exists to share (base types, enums, resources). If there's no shared core, hub-and-spoke buys nothing — just ship separate packages.
- Apple-platform-specific motivation (App Review API-reference scrutiny). On non-Apple ecosystems only the binary-size argument applies, which is weaker.

## To port this, you need:
- [ ] A shared core target holding the abstraction + resources.
- [ ] One product + one target per feature, each depending *only* on the core.
- [ ] A per-feature `-D FEATURE` define on each target, plus a build-system selector define if you support more than one package manager.
- [ ] Resources centralized in the core, with a `#if`-guarded bundle lookup if you dual-build.
- [ ] A parallel manifest (podspec subspecs) if supporting CocoaPods, kept in lockstep with the SPM products.
- [ ] Docs that tell consumers to import the single feature they need, not an umbrella module.

## Gotchas

- **The App Review benefit only holds if there's NO umbrella product** that re-exports everything. The moment you offer `import PermissionsKit` that pulls all permissions, you've dragged every sensitive API back into the consumer's binary and defeated the entire point. Keep the core importless of permission-specific API references.
- **Two manifests drift.** SPM products and CocoaPods subspecs describe the same split in two files; adding a permission means editing both. A missed subspec = CocoaPods users can't get the new permission. Consider generating one from the other.
- **`Bundle.module` only exists under SPM.** Hard-coding it breaks the CocoaPods build; that's exactly why the `PERMISSIONSKIT_SPM` seam exists. Don't remove it "for simplicity."
- **Per-feature `#if` flags must be defined on every target that compiles that file.** If a shared file references `#if PERMISSIONSKIT_CAMERA` but the flag isn't defined on the target compiling it, the slice silently vanishes — no error, just missing behavior.
- **Cross-platform absence.** A spoke whose native framework doesn't exist on a target OS (e.g. some permissions on tvOS/watchOS) must be excluded from that platform, or it won't compile. Keep platform availability per-spoke, not on the umbrella.

## Origin (reference only)

Repo: https://github.com/sparrowcode/PermissionsKit · `Package.swift` (products + per-target `swiftSettings` defines), `*.podspec` (subspecs). 15+ products over a `PermissionsKit` core target. MIT, Sparrow Code LTD.
