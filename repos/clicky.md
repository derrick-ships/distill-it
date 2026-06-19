# clicky — origin index

- **Source:** https://github.com/farzaa/clicky
- **What it is:** A macOS menu-bar AI teaching companion — "an AI teacher that lives as a buddy
  next to your cursor. It can see your screen, talk to you, and even point at stuff." Push-to-talk
  voice in, Claude reasoning over a live screenshot, ElevenLabs voice out, and a blue companion
  cursor that physically flies to and points at on-screen elements.
- **Stack:** Native Swift / macOS (AppKit + SwiftUI, ScreenCaptureKit, AVFoundation, CGEvent taps,
  Accessibility) for the app; a single-file Cloudflare Worker (TypeScript) as an API-key proxy.
  APIs: Anthropic Claude (`claude-sonnet-4-6` for chat; Computer Use beta for pointing),
  AssemblyAI v3 realtime STT, ElevenLabs (`eleven_flash_v2_5`) TTS.
- **Date distilled:** 2026-06-18
- **Architecture in one line:** global push-to-talk → streaming STT → ScreenCaptureKit frame (with
  the app's own windows excluded) → Claude streams a spoken answer *and* Computer-Use coordinates →
  a transparent per-display overlay animates a companion cursor to point — all API keys hidden
  behind a Cloudflare Worker proxy.
- **Note:** the app's source directory is misspelled `leanring-buddy` upstream (preserved in the
  build docs' Origin sections).

## Features extracted
| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Screen Element Localization (Computer Use) | canvas-interaction | [study](../features/canvas-interaction/study/screen-element-localization--from-clicky.md) | [build](../features/canvas-interaction/build/screen-element-localization--from-clicky.md) |
| Animated Pointer Guidance | canvas-interaction | [study](../features/canvas-interaction/study/animated-pointer-guidance--from-clicky.md) | [build](../features/canvas-interaction/build/animated-pointer-guidance--from-clicky.md) |
| Screen Capture with Self-Exclusion | media-processing | [study](../features/media-processing/study/screen-capture-self-exclusion--from-clicky.md) | [build](../features/media-processing/build/screen-capture-self-exclusion--from-clicky.md) |
| Push-to-Talk Streaming Transcription | media-processing | [study](../features/media-processing/study/push-to-talk-streaming-transcription--from-clicky.md) | [build](../features/media-processing/build/push-to-talk-streaming-transcription--from-clicky.md) |
| Streaming Claude Screen Context | ai-integration | [study](../features/ai-integration/study/streaming-claude-screen-context--from-clicky.md) | [build](../features/ai-integration/build/streaming-claude-screen-context--from-clicky.md) |
| ElevenLabs Streaming TTS | tts | [study](../features/tts/study/elevenlabs-streaming-tts--from-clicky.md) | [build](../features/tts/build/elevenlabs-streaming-tts--from-clicky.md) |
| Cloudflare Worker API-Key Proxy | credential-management | [study](../features/credential-management/study/cloudflare-worker-key-proxy--from-clicky.md) | [build](../features/credential-management/build/cloudflare-worker-key-proxy--from-clicky.md) |
| Notch-Anchored Companion Overlay | rendering | [study](../features/rendering/study/notch-anchored-companion-overlay--from-clicky.md) | [build](../features/rendering/build/notch-anchored-companion-overlay--from-clicky.md) |
| First-Launch Video Onboarding | onboarding | [study](../features/onboarding/study/first-launch-video-onboarding--from-clicky.md) | [build](../features/onboarding/build/first-launch-video-onboarding--from-clicky.md) |

## The voice loop (how the features connect)
`push-to-talk-streaming-transcription` (hears) + `screen-capture-self-exclusion` (sees) feed
`streaming-claude-screen-context` (thinks) → `elevenlabs-streaming-tts` (speaks) and, when the user
asks "where is X", `screen-element-localization` (Computer Use) returns a coordinate that
`animated-pointer-guidance` flies the companion cursor to. Everything renders on the
`notch-anchored-companion-overlay`, and every API call is brokered by the
`cloudflare-worker-key-proxy`. First run is gated by `first-launch-video-onboarding`.
