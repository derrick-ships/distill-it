# Sparkle EdDSA Auto-Update — from [open-caffeine](https://github.com/sapsaldog/open-caffeine)

> Domain: [[_domain]] · Source: https://github.com/sapsaldog/open-caffeine · NotebookLM: <add link>

## What it does
Lets the installed Mac app update itself. It quietly checks for new versions, and when the user clicks "Check for Updates" it shows a standard "a new version is available" window, downloads the new build, verifies it is authentic, and installs it. New releases are published just by uploading a zip and pushing one XML file.

## Why it exists
A desktop app that can't update itself strands every user on whatever version they first installed. Building that mechanism by hand (download, verify, swap the running app, relaunch) is fiddly and security-sensitive. Sparkle is the de-facto macOS framework that does it; the job here is wiring it correctly and, crucially, signing every update so a tampered or spoofed download can't be installed.

## How it actually works
Three pieces: the app, the feed, and the release script.

The app embeds Sparkle and two values in its Info.plist: the URL of an "appcast" (an RSS feed of versions) and a public key. Sparkle's standard updater object reads those, periodically (and on demand) fetches the appcast, and compares versions. If there's a newer one, it downloads the linked zip and checks the zip's signature against the embedded public key before installing. The app's own code is tiny: a thin wrapper exposing "check now" and "auto-check on/off."

The feed (appcast.xml) is a small RSS file. Each release is one item with the version number, the minimum macOS it needs, and an enclosure pointing at the downloadable zip plus its length and an EdDSA signature. open-caffeine hosts this file straight from the GitHub repo (the raw file URL is the feed) and hosts the actual zips as GitHub Release assets. No server required.

The release script ties it together: it builds a Release version, zips the app, and runs Sparkle's generate_appcast tool, which signs the zip with the developer's private EdDSA key (kept in the login keychain, never in the repo) and writes the signed appcast. You then create a GitHub release with the zip and push the new appcast.xml, and every installed app picks up the update on its next check.

## The non-obvious parts
- **The signature is the whole security model.** Hosting is untrusted (a raw GitHub file, a public zip); what makes it safe is that the EdDSA signature must verify against the public key compiled into the app. Lose the private key and you can't ship updates; leak it and someone else can.
- **The feed can be a static file in the repo.** Pointing the feed URL at a raw GitHub appcast.xml means publishing an update is a push, no update server, no infra.
- **Versioning is two numbers.** Sparkle compares the build number (monotonic) to decide "newer," while showing the human short-version string. Out of sync, updates either never offer or offer endlessly.
- **The minimum-system-version gates the offer** so users on older macOS aren't pushed an update they can't run.

## Related
- [[coverage-gated-testable-core--from-open-caffeine]] — why the Sparkle wrapper is a "thin shell" excluded from the coverage gate.
- See also: any CI/CD release flow; here the deploy target is the user's machine, not a server.
