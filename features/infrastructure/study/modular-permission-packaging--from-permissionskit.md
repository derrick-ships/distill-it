# Modular Per-Permission Packaging — from [PermissionsKit](https://github.com/sparrowcode/PermissionsKit)

> Domain: [[_domain]] · Source: https://github.com/sparrowcode/PermissionsKit · NotebookLM: <link once added>

## What it does

PermissionsKit could have shipped as one big library you import wholesale. Instead it's split into **15+ separate importable modules** — `CameraPermission`, `LocationPermission`, `NotificationPermission`, and so on — each one a standalone product you add to your project independently. If your app only needs the camera, you add `CameraPermission` and nothing else. The Bluetooth, Health, and Siri code never enters your binary.

This is true for both ways people install it: Swift Package Manager (each permission is its own *product*) and CocoaPods (each permission is its own *subspec*). Either way, the unit you depend on is "one permission," not "the whole framework."

## Why it exists

There are two real reasons, and the second one is the interesting one.

**Reason 1 — binary size.** Dead code you never call still bloats your app download. Splitting per-permission means the compiler only ever sees the permissions you actually imported, so your app stays lean.

**Reason 2 — App Review risk (the non-obvious one).** Apple's App Review scrutinizes which sensitive APIs your binary *references*, not just which it calls at runtime. If your app binary contains code that touches the HealthKit or Bluetooth or Tracking APIs, you may be expected to justify it, declare it, or face rejection — even if that code path never runs because it came bundled in a dependency. A monolithic permissions library would drag *every* sensitive API into every app that uses it, creating review headaches the developer didn't sign up for. By splitting per-permission, your binary only references the sensitive frameworks for permissions you deliberately imported. You're never on the hook for an API you don't use.

That second reason is why this isn't just tidy engineering — it's a defensive distribution strategy specific to Apple's ecosystem.

## How it actually works

Three mechanisms stack together:

**1. Separate build products.** In the Swift package manifest, every permission is declared as both a `library` product and a matching `target`. Each permission target depends on a shared core target (`PermissionsKit`) that holds the base class, the enums, and the localization resources. So the dependency graph is a hub-and-spoke: every spoke (a permission) points at the hub (the core), and the spokes don't know about each other. Importing one spoke pulls in the hub and nothing else.

**2. Conditional compilation flags.** Each target is compiled with a `-D` define naming itself — `PERMISSIONSKIT_CAMERA`, `PERMISSIONSKIT_LOCATION`, etc. — plus a shared `PERMISSIONSKIT_SPM` flag that signals "we were built via Swift Package Manager." Shared code inside the core can wrap permission-specific bits in `#if PERMISSIONSKIT_CAMERA … #endif` so that, even within the hub, only the relevant slices light up for a given build. The `PERMISSIONSKIT_SPM` flag exists because the *same source files* are also compiled under CocoaPods, where resource bundling and import paths differ; the flag lets one codebase behave correctly under both build systems.

**3. CocoaPods subspecs mirror the same split.** For teams still on CocoaPods, the podspec defines a subspec per permission (`pod 'SPPermissions/Camera'`). Same principle, different package manager: you pull in exactly the permission you name, and it depends on a shared core subspec.

The localization and shared resources live once, in the core, and are processed as bundle resources — so all permissions share one set of translated permission-name strings rather than each carrying its own.

## The non-obvious parts

- **The real prize is App Review surface area, not kilobytes.** Plenty of libraries split for size; PermissionsKit splits primarily so your binary doesn't *reference* sensitive Apple frameworks you never use. That's an ecosystem-specific motivation most cross-platform developers never think about.
- **One source tree, two build systems, reconciled by a flag.** The `PERMISSIONSKIT_SPM` define is the seam that lets identical Swift files compile correctly under both SPM and CocoaPods. It's a small thing that quietly avoids maintaining two copies of everything.
- **The hub-and-spoke keeps the core importless of UIKit-only bits where possible.** Because cross-platform targets (watchOS/tvOS) may not support some APIs, isolating each permission means a tvOS app pulling in only the permissions tvOS supports never tries to compile code for permissions it can't use.
- **Granularity is a product decision, not just a build optimization.** Shipping "one permission per module" shapes how developers think about the library — they reach for exactly what they need, which both reduces their risk and makes the library feel lightweight even though it covers 18 permissions in total.

## Related

- [[unified-permission-abstraction--from-permissionskit]] — the shared core (`Permission` base class + enums) that every one of these modules depends on; the packaging is what lets you adopt that abstraction one permission at a time.
- [[async-to-sync-status-bridging--from-permissionskit]] — lives inside the per-permission modules that need it (notification, location).
