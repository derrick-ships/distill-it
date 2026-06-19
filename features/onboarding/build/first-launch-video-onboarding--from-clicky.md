# First-Launch Video Onboarding (build spec) — distilled from clicky

## Summary
First-run is gated by a single `UserDefaults` bool `hasCompletedOnboarding`. On launch the menu-bar setup panel auto-opens if onboarding is incomplete OR any permission is missing. The panel primes and requests four macOS permissions (Microphone, Accessibility, Screen Recording, Screen Content) with native-prompt-then-System-Settings fallbacks, collects an email, then on **Start** flips the flag, plays music, and shows a full-screen companion overlay where a blue triangle fades in, types "hey! i'm clicky", and a remote HLS demo **video** (`AVPlayer` over a Mux `.m3u8`) fades in floating beside the live cursor. Replayable via `replayOnboarding()`.

## Core logic (inlined)

### First-run flag + auto-open (App delegate)
```swift
// leanring_buddyApp.swift
func applicationDidFinishLaunching(_ notification: Notification) {
    menuBarPanelManager = MenuBarPanelManager(companionManager: companionManager)
    companionManager.start()
    if !companionManager.hasCompletedOnboarding || !companionManager.allPermissionsGranted {
        menuBarPanelManager?.showPanelOnLaunch()   // 0.3s-delayed showPanel()
    }
}
```

### Onboarding / permission state (CompanionManager)
```swift
// CompanionManager.swift
var hasCompletedOnboarding: Bool {
    get { UserDefaults.standard.bool(forKey: "hasCompletedOnboarding") }
    set { UserDefaults.standard.set(newValue, forKey: "hasCompletedOnboarding") }
}
@Published var hasSubmittedEmail: Bool = UserDefaults.standard.bool(forKey: "hasSubmittedEmail")

@Published private(set) var hasAccessibilityPermission = false
@Published private(set) var hasScreenRecordingPermission = false
@Published private(set) var hasMicrophonePermission = false
@Published private(set) var hasScreenContentPermission = false
var allPermissionsGranted: Bool {
    hasAccessibilityPermission && hasScreenRecordingPermission &&
    hasMicrophonePermission && hasScreenContentPermission
}

// Onboarding video state (the demo)
@Published var onboardingVideoPlayer: AVPlayer?
@Published var showOnboardingVideo: Bool = false
@Published var onboardingVideoOpacity: Double = 0   // (drives the 2s fade in BlueCursorView)
```

### Aha-moment trigger + replay
```swift
// CompanionManager.swift
func triggerOnboarding() {
    NotificationCenter.default.post(name: .clickyDismissPanel, object: nil)  // close panel
    hasCompletedOnboarding = true                                            // set flag NOW
    ClickyAnalytics.trackOnboardingStarted()
    startOnboardingMusic()
    overlayWindowManager.showOverlay(onScreens: NSScreen.screens, companionManager: self)
    isOverlayVisible = true
}

func replayOnboarding() {
    NotificationCenter.default.post(name: .clickyDismissPanel, object: nil)
    ClickyAnalytics.trackOnboardingReplayed()
    startOnboardingMusic()
    overlayWindowManager.hasShownOverlayBefore = false   // re-arm the first-appearance intro
    overlayWindowManager.showOverlay(onScreens: NSScreen.screens, companionManager: self)
    isOverlayVisible = true
}

func submitEmail(_ email: String) {
    let trimmed = email.trimmingCharacters(in: .whitespacesAndNewlines)
    guard !trimmed.isEmpty else { return }
    hasSubmittedEmail = true
    UserDefaults.standard.set(true, forKey: "hasSubmittedEmail")
    PostHogSDK.shared.identify(trimmed, userProperties: ["email": trimmed])
    Task {
        var request = URLRequest(url: URL(string: "https://submit-form.com/RWbGJxmIs")!)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try? JSONSerialization.data(withJSONObject: ["email": trimmed])
        _ = try? await URLSession.shared.data(for: request)
    }
}
```

### Demo video: remote HLS via AVPlayer (CONFIRMED)
```swift
// CompanionManager.swift  (setup/teardown — reconstructed from confirmed fragments)
func setupOnboardingVideo() {
    guard let videoURL = URL(string: "https://stream.mux.com/e5jB8UuSrtFABVnTHCR7k3sIsmcUHCyhtLu1tzqLlfs.m3u8")
    else { return }
    let player = AVPlayer(url: videoURL)   // HLS stream — NOT a bundled .mp4/.mov
    self.onboardingVideoPlayer = player
    player.play()
    withAnimation(.easeInOut(duration: 2.0)) { self.onboardingVideoOpacity = 1.0 }
}
func tearDownOnboardingVideo() {
    onboardingVideoPlayer?.pause()
    onboardingVideoPlayer = nil
    onboardingVideoOpacity = 0
}
```
> The `videoURL` string and the `@Published onboardingVideoPlayer/showOnboardingVideo` properties are verbatim from source. The exact body of `setupOnboardingVideo()`/`tearDownOnboardingVideo()` is reconstructed (see Gotchas) but the call sites, the AVPlayer, the Mux URL, and the opacity-driven fade are confirmed.

### The video view: chrome-less AVPlayerLayer, parented to the cursor (CONFIRMED verbatim)
```swift
// OverlayWindow.swift
private struct OnboardingVideoPlayerView: NSViewRepresentable {
    let player: AVPlayer?
    func makeNSView(context: Context) -> AVPlayerNSView {
        let view = AVPlayerNSView(); view.player = player; return view
    }
    func updateNSView(_ nsView: AVPlayerNSView, context: Context) { nsView.player = player }
}

private class AVPlayerNSView: NSView {
    var player: AVPlayer? { didSet { playerLayer.player = player } }
    private let playerLayer = AVPlayerLayer()
    override init(frame: NSRect) {
        super.init(frame: frame)
        wantsLayer = true
        playerLayer.videoGravity = .resizeAspectFill
        layer?.addSublayer(playerLayer)
    }
    required init?(coder: NSCoder) { fatalError() }
    override func layout() { super.layout(); playerLayer.frame = bounds }
}
```

### Intro animation + video placement inside the overlay (CONFIRMED)
```swift
// OverlayWindow.swift — BlueCursorView
private let onboardingVideoPlayerWidth: CGFloat = 330
private let onboardingVideoPlayerHeight: CGFloat = 186
private let fullWelcomeMessage = "hey! i'm clicky"

// In body: video floats beside the live cursor, click-through, fades via opacity.
OnboardingVideoPlayerView(player: companionManager.onboardingVideoPlayer)
    .frame(width: onboardingVideoPlayerWidth, height: onboardingVideoPlayerHeight)
    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    .shadow(color: Color.black.opacity(0.4 * companionManager.onboardingVideoOpacity), radius: 12, x: 0, y: 6)
    .opacity(isCursorOnThisScreen ? companionManager.onboardingVideoOpacity : 0)
    .position(
        x: cursorPosition.x + 10 + (onboardingVideoPlayerWidth / 2),
        y: cursorPosition.y + 18 + (onboardingVideoPlayerHeight / 2)
    )
    .animation(.easeInOut(duration: 2.0), value: companionManager.onboardingVideoOpacity)
    .allowsHitTesting(false)

// Welcome typing → then start the video:
private func startWelcomeAnimation() {
    withAnimation(.easeIn(duration: 0.4)) { self.bubbleOpacity = 1.0 }
    var currentIndex = 0
    Timer.scheduledTimer(withTimeInterval: 0.03, repeats: true) { timer in
        guard currentIndex < self.fullWelcomeMessage.count else {
            timer.invalidate()
            DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) { self.bubbleOpacity = 0.0 }
            DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) {
                self.showWelcome = false
                self.companionManager.setupOnboardingVideo()   // <<< demo video begins
            }
            return
        }
        let i = self.fullWelcomeMessage.index(self.fullWelcomeMessage.startIndex, offsetBy: currentIndex)
        self.welcomeText.append(self.fullWelcomeMessage[i]); currentIndex += 1
    }
}

// onAppear first-run gate: fade cursor in over 2s, then begin welcome typing.
.onAppear {
    if isFirstAppearance && isCursorOnThisScreen {
        withAnimation(.easeIn(duration: 2.0)) { self.cursorOpacity = 1.0 }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
            self.bubbleOpacity = 0.0; startWelcomeAnimation()
        }
    } else { self.cursorOpacity = 1.0 }
}
.onDisappear { companionManager.tearDownOnboardingVideo() }
```

### Permission rows: native-prompt-then-Settings (CONFIRMED)
```swift
// CompanionPanelView.swift — order shown: Microphone, Accessibility, Screen Recording, then Screen Content (only if recording granted)

// Microphone
let status = AVCaptureDevice.authorizationStatus(for: .audio)
if status == .notDetermined {
    AVCaptureDevice.requestAccess(for: .audio) { _ in }
} else if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone") {
    NSWorkspace.shared.open(url)
}

// Accessibility — system trust prompt first; "Find App" reveals app in Finder (unsigned dev builds)
WindowPositionManager.requestAccessibilityPermission()
WindowPositionManager.revealAppInFinder()
WindowPositionManager.openAccessibilitySettings()

// Screen Recording — native prompt first, then Settings (copy: "Quit and reopen after granting")
WindowPositionManager.requestScreenRecordingPermission()

// Screen Content (ScreenCaptureKit) — row only rendered when hasScreenRecordingPermission == true
companionManager.requestScreenContentPermission()
```

### Priming copy + state-driven panel (CONFIRMED, abridged)
```swift
// CompanionPanelView.swift — permissionsCopySection chooses message by state:
//  • all granted + onboarded  -> "Hold Control+Option to talk."
//  • all granted, no email    -> "Drop your email to get started." / "If I keep building this, I'll keep you in the loop."
//  • all granted (pre-Start)  -> "You're all set. Hit Start to meet Clicky."
//  • onboarded but revoked    -> "Some permissions were revoked. Grant all four below to keep using Clicky."
//  • fresh (nothing granted)  -> "Hi, I'm Farza. This is Clicky." + trust note:
//      "Nothing runs in the background. Clicky will only take a screenshot when you press the hot key..."

// Start flow: email TextField -> submitEmail(emailInput); after email -> "Start" button -> companionManager.triggerOnboarding()
// Footer (only when hasCompletedOnboarding): "Watch Onboarding Again" -> companionManager.replayOnboarding()
```

## Data contracts
- `UserDefaults` keys (verbatim): `"hasCompletedOnboarding"`, `"hasSubmittedEmail"`, `"isClickyCursorEnabled"`, `"selectedClaudeModel"`, `"hasScreenContentPermission"`.
- `allPermissionsGranted = accessibility && screenRecording && microphone && screenContent` (all four required).
- Demo video: HLS `AVPlayer(url:)` over `https://stream.mux.com/e5jB8UuSrtFABVnTHCR7k3sIsmcUHCyhtLu1tzqLlfs.m3u8`; size 330×186; corner radius 10; positioned at `(cursor.x + 10 + 165, cursor.y + 18 + 93)`; fades via `onboardingVideoOpacity` over 2.0s; `allowsHitTesting(false)`.
- Intro: cursor fades in 2.0s → "hey! i'm clicky" typed at 0.03s/char → +2.5s → `setupOnboardingVideo()`.
- `OverlayWindowManager.hasShownOverlayBefore` gates `isFirstAppearance` (intro plays); `replayOnboarding()` resets it to `false`.
- Email submission: PostHog `identify(email)` + POST `{"email": ...}` to `https://submit-form.com/RWbGJxmIs`.

## Dependencies & assumptions
- AVKit/AVFoundation (`AVPlayer`, `AVPlayerLayer`, `AVCaptureDevice`), AppKit, SwiftUI, `UserDefaults`, PostHog SDK, `ScreenCaptureKit` (Screen Content), `NSWorkspace` deep links to System Settings.
- Network access on first run (video is streamed, not bundled).
- `WindowPositionManager` provides static `requestAccessibilityPermission()`, `requestScreenRecordingPermission()`, `revealAppInFinder()`, `openAccessibilitySettings()`.
- Runs on the full-screen companion overlay described in [[rendering/notch-anchored-companion-overlay--from-clicky]].

## To port this, you need:
- [ ] A durable first-run flag (`UserDefaults`/equivalent); auto-open setup if `!completed || !allPermissionsGranted`.
- [ ] State-driven priming copy that explains *why* before each system permission dialog.
- [ ] Per-permission Grant buttons: trigger the native prompt when `notDetermined`, deep-link to System Settings otherwise; a "Find App" escape hatch for unsigned builds.
- [ ] Progressive disclosure: only show the Screen Content row after Screen Recording is granted; require all four for `allPermissionsGranted`.
- [ ] An email gate (optional) before the Start button.
- [ ] On Start: set the completed flag immediately, dismiss the setup UI, start music, show the demo surface.
- [ ] An aha-moment demo: fade in the companion, type a greeting, then fade in a chrome-less video player parented to the live cursor with `allowsHitTesting(false)`.
- [ ] Use an `AVPlayerLayer`-backed `NSViewRepresentable` (not SwiftUI `VideoPlayer`) for a controls-less click-through video.
- [ ] A "Watch Onboarding Again" affordance that re-arms the first-appearance intro and re-shows the overlay.
- [ ] Tolerate revocation: re-open setup with a "permissions revoked" message when `!allPermissionsGranted` post-onboarding.

## Gotchas
- **The onboarding video WAS CONFIRMED in code** (not inferred): `@Published var onboardingVideoPlayer: AVPlayer?`, `showOnboardingVideo`, the Mux `.m3u8` URL string, `OnboardingVideoPlayerView`/`AVPlayerNSView`, the cursor-relative `.position`, the 2.0s opacity fade, `setupOnboardingVideo()` call from `startWelcomeAnimation()`, and `tearDownOnboardingVideo()` on disappear are all verbatim from `CompanionManager.swift` and `OverlayWindow.swift`.
- **Reconstructed vs confirmed:** the exact *bodies* of `setupOnboardingVideo()` / `tearDownOnboardingVideo()` / `startOnboardingMusic()` were not fully fetched verbatim — they're reconstructed above from the confirmed property names, the Mux URL, the call sites, and the opacity-fade behavior. The signatures and effects are correct; line-for-line internals may differ slightly.
- **No bundled video file.** It's a remote HLS stream → first-run onboarding requires network. There is no `.mp4`/`.mov` asset.
- **Flag is set on Start, not on completion** — quitting mid-demo won't re-trigger auto-play; only explicit replay re-shows it.
- **Screen Recording needs a relaunch** (per the UI copy "Quit and reopen after granting") — macOS often won't honor the new grant until restart.
- **Don't use SwiftUI `VideoPlayer`** — it ships playback controls and a focusable surface; the click-through, chrome-less feel requires the raw `AVPlayerLayer` wrapper.
- The setup panel's outside-click dismissal is deliberately delayed/guarded so triggering a permission dialog from a Grant button doesn't close the panel (see the rendering feature).

## Origin (reference only)
- `leanring-buddy/CompanionManager.swift` — `hasCompletedOnboarding`/`hasSubmittedEmail` flags, `triggerOnboarding()`, `replayOnboarding()`, `submitEmail()`, permission properties, `onboardingVideoPlayer` + Mux URL.
- `leanring-buddy/CompanionPanelView.swift` — state-driven priming copy, four permission rows + request calls, email/Start UI, "Watch Onboarding Again" footer.
- `leanring-buddy/OverlayWindow.swift` — `OnboardingVideoPlayerView`/`AVPlayerNSView`, cursor-parented video placement, `startWelcomeAnimation()` → `setupOnboardingVideo()`, `isFirstAppearance` onAppear gate, `tearDownOnboardingVideo()` onDisappear.
- `leanring-buddy/leanring_buddyApp.swift` — launch-time auto-open gate.
- Repo: https://github.com/farzaa/clicky (assume gone; load-bearing code inlined above).
