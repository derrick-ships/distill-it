# Domain: app-distribution

Getting a desktop app, and its future updates, onto users' machines: signing releases, publishing a feed, and letting the installed app update itself safely.

## What this domain is about
Web apps redeploy invisibly; desktop apps don't. Shipping a Mac/Windows app means producing a signed artifact, hosting it, publishing an update feed, and wiring the installed binary to check that feed and apply verified updates. The engineering is in the trust chain (cryptographic signatures) and the release automation, not the UI.

## Key design principle
Updates must be cryptographically verified end to end. The app ships a public key; each release is signed with the matching private key; the updater refuses anything that doesn't verify. Hosting can be dumb (a static file behind a CDN); the signature is what makes it safe.

## Features in this domain
- [[sparkle-eddsa-autoupdate--from-open-caffeine]] — self-updating macOS app via Sparkle with EdDSA-signed releases and a GitHub-hosted appcast.
