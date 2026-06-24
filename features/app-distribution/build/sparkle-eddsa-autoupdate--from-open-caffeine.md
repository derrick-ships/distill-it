# Sparkle EdDSA Auto-Update (build spec) — distilled from open-caffeine

## Summary
Make a macOS app self-update with cryptographically verified releases, using Sparkle, an EdDSA-signed appcast, and zero update server (appcast + binaries hosted on GitHub).

## Core logic (inlined)

**1. Dependency** (SPM): `https://github.com/sparkle-project/Sparkle` (Sparkle 2.x).

**2. Info.plist keys** (the entire app-side config):
```xml
<key>SUEnableAutomaticChecks</key><true/>
<key>SUFeedURL</key><string>https://raw.githubusercontent.com/OWNER/REPO/main/appcast.xml</string>
<key>SUPublicEDKey</key><string>diEC25Ttj2TyM4Q2jRGKiGJrNnMOlhKrfkfVbIIxjSc=</string>  <!-- your EdDSA public key -->
```

**3. The updater wrapper** (thin shell; this is all the app code):
```swift
import Sparkle
@MainActor final class UpdaterService {
    static let shared = UpdaterService()
    private let controller: SPUStandardUpdaterController
    private init() {
        controller = SPUStandardUpdaterController(startingUpdater: true,
                        updaterDelegate: nil, userDriverDelegate: nil)
    }
    func checkForUpdates() { controller.checkForUpdates(nil) }          // wire to a "Check for Updates" menu item
    var canCheckForUpdates: Bool { controller.updater.canCheckForUpdates }
    var automaticallyChecksForUpdates: Bool {
        get { controller.updater.automaticallyChecksForUpdates }
        set { controller.updater.automaticallyChecksForUpdates = newValue }
    }
}
```

**4. appcast.xml schema** (one item per release; the edSignature is produced by signing):
```xml
<rss xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle" version="2.0"><channel>
  <title>App Name</title>
  <item>
    <title>1.0.2</title>
    <pubDate>Mon, 08 Jun 2026 21:54:29 -0600</pubDate>
    <sparkle:version>3</sparkle:version>                      <!-- build number, MONOTONIC: drives "is newer" -->
    <sparkle:shortVersionString>1.0.2</sparkle:shortVersionString>
    <sparkle:minimumSystemVersion>26.0</sparkle:minimumSystemVersion>
    <enclosure url="https://github.com/OWNER/REPO/releases/download/v1.0.2/App-1.0.2.zip"
               length="3708446" type="application/octet-stream"
               sparkle:edSignature="0V_GPc9B...JMm-oq3-tKY9vkoDw=="/>
  </item>
</channel></rss>
```

**5. Release/signing flow** (Scripts/release.sh, condensed to prose + key commands):
- One-time: Sparkle's `generate_keys` makes an EdDSA keypair. The PRIVATE key goes in the login Keychain (or a CI secret); the PUBLIC key string goes into Info.plist (SUPublicEDKey). Never store the private key in the repo.
- Build Release: `xcodebuild ... -configuration Release build`.
- Zip: `ditto -c -k --sequesterRsrc --keepParent "App.app" "dist/App-VERSION.zip"`.
- Sign + write feed: `generate_appcast --download-url-prefix "https://github.com/OWNER/REPO/releases/download/vVERSION/" dist/` — this signs each zip with the Keychain private key and writes a signed `dist/appcast.xml`. Copy it to the repo root.
- Publish: tag a GitHub release vVERSION, upload the zip as an asset, then commit and push the new appcast.xml. The pushed appcast.xml at the raw URL IS the feed.

## Data contracts
- `sparkle:version` (Int build number, monotonic) vs `shortVersionString` (display). `enclosure.length` = exact zip byte size. `sparkle:edSignature` = base64 EdDSA signature of the zip.

## Dependencies & assumptions
- Sparkle 2.x (SPM). `generate_appcast` / `generate_keys` ship in Sparkle's artifacts after first build. EdDSA private key in login Keychain or a CI secret.
- Hosting: any static host for appcast.xml + a place to put zips. Raw GitHub + Releases works with zero infra.
- For distribution beyond your own machines, also Developer-ID code-sign + notarize the app. That is separate from Sparkle's EdDSA signature: Gatekeeper trust vs update authenticity.

## To port this, you need:
- [ ] Sparkle dependency + `SPUStandardUpdaterController` wired to a menu action.
- [ ] An EdDSA keypair; public key in Info.plist, private key kept secret.
- [ ] A hosted appcast.xml (can be a repo file) and hosted zips.
- [ ] A release script that builds, zips with `ditto`, and runs `generate_appcast`.

## Gotchas
- **Monotonic build numbers.** If the build number does not strictly increase, updates will not be offered (or will re-offer forever).
- **EdDSA signature is not code signing.** EdDSA proves the update is from you; Gatekeeper still needs Developer-ID signing + notarization for non-dev users.
- **`length` must match** the served file exactly, or Sparkle rejects it.
- Sandboxed apps need extra Sparkle XPC setup; the simple path assumes a non-sandboxed (hardened-runtime) app.
- The raw-GitHub feed is CDN-cached; allow a few minutes after pushing appcast.xml.

## Origin (reference only)
`OpenCaffeine/Services/UpdaterService.swift`, `Models/UpdateChannel.swift`, `OpenCaffeine/Info.plist`, `appcast.xml`, `Scripts/release.sh`, `project.yml` (Sparkle SPM dep).
