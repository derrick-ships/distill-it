# Unified Permission Abstraction — from [PermissionsKit](https://github.com/sparrowcode/PermissionsKit)

> Domain: [[_domain]] · Source: https://github.com/sparrowcode/PermissionsKit · NotebookLM: <link once added>

## What it does

Apple ships a different, inconsistent API for every single permission your app might ask for. Camera lives in `AVFoundation` and answers synchronously. Notifications live in `UserNotifications` and only answer through an async callback. Location lives in `CoreLocation` and only answers through a *delegate* — an object you have to keep alive while it waits. Contacts, Calendar, Photos, Health, Siri, Tracking — each one is its own little world with its own enum of states, its own request method, its own quirks.

PermissionsKit hides all of that behind **one shape**. Every permission — there are 18 of them — looks identical from the outside:

- Ask the same way: `Permission.camera.request { /* done */ }`
- Check the same way: `if Permission.camera.authorized { ... }`
- Get back the same four answers every time: **authorized, denied, notDetermined, notSupported.**

You learn the pattern once and it works for Bluetooth, Health, Siri, and everything else. That's the whole product.

## Why it exists

Permission handling is the unglamorous plumbing every iOS app needs and everyone hates writing. The native APIs are inconsistent enough that developers re-learn them on every project, copy-paste old code, and still get the edge cases wrong (the async ones especially). It's also genuinely risky territory: ask for a permission clumsily, or at the wrong moment, and the user taps "Don't Allow" — and on iOS that's usually *permanent* until they dig into Settings. So a clean, uniform, hard-to-misuse wrapper has real value: it reduces a recurring tax to a one-liner, and it makes the "what do I do when they say no" flow consistent too (every permission can open the Settings page the same way).

The business angle for the maintainer (Sparrow Code) is classic open-source developer-tooling: be the default, well-documented, trusted name for a chore everyone has. The payoff is reputation and funnel, not direct revenue.

## How it actually works

The heart of it is a single abstract base class called `Permission`. Think of it as a contract that says: "every permission must be able to tell me its **status**, and must be able to **request** itself." The base class itself can't do either — it doesn't know whether it's a camera or a microphone — so those two things are left blank for subclasses to fill in. If you ever call them on the raw base class, it deliberately crashes with "this method must be overridden," which is the framework's way of refusing to ship a half-built permission.

Everything *common* lives on the base class so it's written once:

- The convenience booleans `authorized`, `denied`, `notDetermined` are just shortcuts that compare `status` to one of the four cases. Subclasses never re-implement these.
- `openSettingPage()` — the universal "send the user to Settings to fix a denial" — is identical for every permission, so it lives here too. It hops to the main thread, builds the special Settings URL, and opens it.
- Human-readable names for debugging and UI.

Then each permission is a small subclass that fills in the two blanks by **translating** the native API into the common language:

- **Camera** (the simple case): its `status` asks `AVCaptureDevice` for the camera authorization and maps Apple's four states onto our four. Apple's "restricted" (e.g. parental controls) gets folded into "denied," because from the app's point of view the outcome is the same — you can't use the camera. Its `request` calls Apple's `requestAccess` and, when the system finishes, bounces the completion callback to the main thread so your UI code is safe to run.
- **Notification** (the awkward case): Apple only tells you the notification status through an async callback, but our `status` is supposed to be a plain property you can read instantly. PermissionsKit bridges that gap (described in its own note — see Related). It also threads through *which* notification capabilities you want (badge, sound, alert, critical alerts, time-sensitive, etc.) via a set of options.
- **Location** (the stateful case): location won't answer through a simple callback at all — it answers through a delegate object that must stay alive until the system responds. PermissionsKit parks that delegate in a static "shared" slot so it doesn't get garbage-collected mid-request, then clears the slot once the answer arrives. It also carefully distinguishes "when in use" from "always," refusing to report "always" as authorized if the user only granted "when in use."

The clever bit that makes the uniform API possible is the **Kind** enum. Most permissions are just a flat case (`.camera`, `.microphone`), but the ones with sub-flavors carry their configuration *inside* the case: `.calendar(access: .full or .write)`, `.location(access: .whenInUse or .always)`, `.notification(access: {badge, sound, alert, …})`. So a single type can express "calendar, write-only" or "location, always" without exploding into a dozen separate permission names. The right subclass reads that attached value to decide exactly what to ask the OS for.

## The non-obvious parts

- **"Restricted" collapses into "denied" on purpose.** Apple distinguishes a user-denial from a system-restriction (parental controls, MDM). PermissionsKit erases that distinction in its public status because the *app's* options are identical either way — there's nothing actionable about the difference, so exposing it would just be noise.
- **The four-state model includes `notSupported`.** This matters for cross-platform: the same code runs on watchOS or tvOS where a given permission may not exist at all. "Not supported here" is a first-class answer, not an error or a crash.
- **It refuses to half-exist.** Calling `request()` or `status` on the base class is a hard `preconditionFailure`. That's a deliberate design choice: it turns "you forgot to implement this permission" from a silent runtime no-op into an immediate, obvious crash during development.
- **Access levels live inside the Kind, not as separate permissions.** This is the decision that keeps the public surface small. Instead of `CalendarFullPermission` and `CalendarWritePermission` as two types, there's one `.calendar(access:)`. The granularity is data, not new classes.
- **Every async answer is bounced back to the main thread.** Every `request` completion is wrapped in `DispatchQueue.main.async`. This is a quiet but important safety net — permission callbacks fire on arbitrary queues, and developers almost always want to update UI in them, which must happen on main.
- **Location's "always vs when-in-use" guard.** Reporting authorized only when the *granted* level matches the *requested* level prevents a subtle bug where an app thinks it has background location but actually only has foreground.

## Related

- [[async-to-sync-status-bridging--from-permissionskit]] — the DispatchSemaphore trick that lets notification/location expose `status` as an instant property despite Apple's async-only APIs. It's the mechanism that makes this uniform abstraction possible.
- [[modular-permission-packaging--from-permissionskit]] — how the 18 permissions are split into separate importable modules so you only compile the ones you ask for.
- See also: [[privacy/pattern-based-secret-redaction--from-asyar]] — a different corner of the same "respect the user's data" domain (redaction vs. consent).
