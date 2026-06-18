# First-Launch Video Onboarding — from [clicky](https://github.com/farzaa/clicky)

> Domain: [[_domain]] · Source: https://github.com/farzaa/clicky · NotebookLM:

## What it does
The very first time you open Clicky, the menu-bar panel pops open by itself and walks you through setup: a friendly note from the author, a checklist of four macOS permissions to grant, and an email box. Once everything's granted and you hit **Start**, the panel closes and the screen comes alive — a little glowing blue triangle (the companion cursor) fades in next to your real pointer, types out "hey! i'm clicky," and then a short demo **video** fades in floating right beside the cursor, showing the product in action. Background music plays. Afterward you can re-watch the whole thing any time via "Watch Onboarding Again."

## Why it exists
Clicky needs four scary OS permissions (microphone, accessibility, screen recording, screen-content capture) before it can do anything, and the concept ("a voice companion that watches your screen") sounds invasive. So the first-run does two jobs: it _earns trust_ with plain-spoken copy ("Nothing runs in the background... I can't do much there champ") before triggering each system dialog, and it delivers an _aha-moment_ — the talking cursor plus a demo video — that makes the payoff obvious the instant setup is done. Showing the product beats describing it.

## How it actually works
**First-run detection.** A single `UserDefaults` boolean, `hasCompletedOnboarding`, is the gate. On launch the app auto-opens the setup panel only if `!hasCompletedOnboarding || !allPermissionsGranted`. The flag is flipped to `true` the moment the user presses Start (inside `triggerOnboarding()`), so the demo only ever auto-plays once.

**The setup panel.** The panel (a dark Loom-style card under the menu-bar icon) shows different copy depending on state: a personal intro when nothing's granted; a live permission checklist; then "Drop your email to get started"; then "You're all set. Hit Start to meet Clicky." Each permission has its own row with a green "Granted" dot or a "Grant" button.

**Permission priming + requests.** Four permissions, requested individually from their rows:
- **Microphone** — `AVCaptureDevice.requestAccess(for: .audio)` if `notDetermined`, otherwise deep-links to the Microphone pane in System Settings.
- **Accessibility** — `WindowPositionManager.requestAccessibilityPermission()` (triggers the system trust prompt first; opens Settings on retry; also offers a "Find App" button that reveals the app in Finder for unsigned dev builds).
- **Screen Recording** — `WindowPositionManager.requestScreenRecordingPermission()` (native prompt first, then Settings). Copy warns "Quit and reopen after granting."
- **Screen Content** — `requestScreenContentPermission()` (ScreenCaptureKit), and this row only appears _after_ screen recording is granted.

**Email gate.** Before Start appears, the user submits an email; `submitEmail()` flips `hasSubmittedEmail`, identifies them in PostHog, and POSTs the address to a form endpoint.

**The aha-moment sequence.** `triggerOnboarding()` dismisses the panel, sets `hasCompletedOnboarding = true`, starts onboarding music, and shows the full-screen companion overlay on every screen. Inside the overlay's `BlueCursorView`, on first appearance: the blue triangle fades in over 2s, then types "hey! i'm clicky" character-by-character (~30ms/char). When that finishes, after a short beat it calls `setupOnboardingVideo()`, which loads an `AVPlayer` and fades the video in (2s ease). The video (330×186, rounded corners, drop shadow) is **positioned relative to the live cursor** — to the right and just below — so it travels with the companion. It's `allowsHitTesting(false)` so it never blocks clicks. When the overlay disappears, `tearDownOnboardingVideo()` releases the player.

**Replay.** `replayOnboarding()` resets `hasShownOverlayBefore = false` and re-shows the overlay, so the intro animation + video plays again from the "Watch Onboarding Again" footer button.

## The non-obvious parts
- **The demo video is a remote HLS stream, not a bundled file.** It loads from a Mux URL (`https://stream.mux.com/<id>.m3u8`) via `AVPlayer`. There is no `.mp4`/`.mov` in the bundle — so onboarding needs network on first run.
- **The video is parented to the cursor, not the screen.** Its `.position` is computed from `cursorPosition` (`x + 10 + width/2`, `y + 18 + height/2`), so it floats beside the moving companion rather than sitting in a fixed box. This is what makes the "moving mouse/cursor demo" feel alive.
- **`hasCompletedOnboarding` is set the instant Start is pressed**, before the demo finishes — so even if the user quits mid-demo, it won't auto-replay. Replay is explicit only.
- **The video player is a hand-rolled `NSViewRepresentable`** wrapping an `AVPlayerLayer` (`videoGravity = .resizeAspectFill`) — not SwiftUI's `VideoPlayer` — to get a chrome-less, controls-less, click-through surface.
- **Permissions tolerate revocation.** If you granted them once then turned one off, the panel re-opens on next launch (`!allPermissionsGranted`) with "Some permissions were revoked. Grant all four below."
- **The Screen Content row is progressive** — hidden until Screen Recording is granted, because it depends on it.

## Related
- [[rendering/notch-anchored-companion-overlay--from-clicky]] (the demo video and "hey! i'm clicky" intro are presented on that full-screen transparent overlay)
- [[canvas-interaction/animated-pointer-guidance--from-clicky]] (the same companion cursor that delivers the onboarding intro)
- [[media-processing/screen-capture-self-exclusion--from-clicky]] (the Screen Recording / Screen Content permissions primed here power the screenshot feature)
