# Domain: onboarding

The first-run experience: the moments between "app just launched for the first time" and "user understands what this thing is and has granted it everything it needs to work." Covers first-launch detection, permission priming, and the orchestrated "aha-moment" demo that shows — rather than tells — what the product does.

## What this domain is about

A freshly installed app has to cross three gaps before it's useful: the user doesn't know what it does, hasn't granted the OS permissions it needs, and hasn't experienced the core loop. Onboarding is the choreography that closes all three. The recurring problems are: detecting "is this the first run?" durably (a `UserDefaults`/localStorage flag that survives relaunch), **priming** OS permission prompts so the scary system dialogs land in a context the user already trusts (explain *why* before triggering the request, request them in a sensible order, and recover gracefully when one is denied or later revoked), and engineering an **aha-moment** — often a short looping demo video or an in-product guided animation — that makes the value obvious in seconds.

## Key pattern: prime, then demo, then activate

The strongest first-runs separate three phases: (1) **priming copy** that sets expectations and earns trust before any system dialog ("nothing runs in the background; we only act when you press the hotkey"); (2) a **permission checklist** the user works through, with per-permission Grant buttons that trigger the native prompt first and fall back to opening System Settings on retry, plus tolerance for permissions being revoked later; and (3) an **aha-moment demo** — a video or scripted in-app animation — that plays only once the user is "all set," is gated behind the first-run flag, and can be replayed on demand. The demo is the payoff that converts a permission chore into delight.

## Features in this domain

- [[first-launch-video-onboarding--from-clicky]] — first-run gated by a `hasCompletedOnboarding` UserDefaults flag; a trust-building permission checklist (Microphone, Accessibility, Screen Recording, Screen Content) with native-prompt-then-Settings fallbacks; and an aha-moment where a streaming demo video floats next to an animated companion cursor that types "hey! i'm clicky" — replayable via a "Watch Onboarding Again" button.
