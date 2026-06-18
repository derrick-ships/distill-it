# Push-to-Talk Streaming Transcription — from [clicky](https://github.com/farzaa/clicky)

> Domain: [[_domain]] · Source: https://github.com/farzaa/clicky · NotebookLM:

## What it does
Lets the user hold a global keyboard shortcut (default **ctrl + option**) from anywhere on the Mac, speak, and release — and turns that speech into text in real time. While the key is held, the microphone streams to a speech-to-text service that returns words as you talk (partial results), and on release it commits a clean final transcript into the app's text box (and optionally auto-sends it). The transcription backend is pluggable: AssemblyAI's realtime WebSocket is the default, with Apple's on-device Speech and OpenAI's audio API as drop-in alternates chosen by config.

## Why it exists
clicky is a voice companion you talk to while working. It needs a "walkie-talkie" interaction — hold to speak, release to send — that works even when clicky isn't the focused app, so the user never has to click into it first. That requires a *system-wide* hotkey, not an in-app one. And because no single transcription service is best for everyone (cost, privacy, accuracy, offline), the author abstracted the backend behind a protocol so any of three providers can be swapped via an Info.plist setting without touching the rest of the app.

## How it actually works
There are four moving parts:

**1. The global hotkey monitor.** A listen-only system event tap (CGEvent tap) watches all keyboard events Mac-wide. Because the default shortcut is *modifier-only* (ctrl + option, no letter), it watches "modifier keys changed" events: when both ctrl and option become held it fires "pressed," when either lifts it fires "released." It's listen-only so it never swallows the keystroke from other apps. The shortcut definition also supports letter-based combos like "ctrl + option + space," which instead watch key-down/key-up of the space key (key code 49) while the modifiers are held.

**2. The dictation manager.** On "pressed" it asks for mic permission (de-duplicating rapid presses so macOS doesn't pop the permission sheet twice), opens a transcription session with the chosen provider, then starts an `AVAudioEngine` and installs a "tap" on the microphone input that hands every audio buffer to the session. It also computes a live audio level (RMS) from each buffer to drive a waveform animation. On "released" it stops the engine, asks the session for a final transcript, and starts a fallback timer in case the final never arrives. Partial transcripts update the draft text live; the final one is committed and optionally submitted.

**3. The provider protocol.** Any backend implements two protocols: one for the provider (name, whether it needs speech-recognition permission, whether it's configured, and a method to start a streaming session) and one for the live session (append an audio buffer, request the final transcript, cancel, and declare how long to wait for the final before giving up). A factory reads an Info.plist key to pick the preferred provider and falls back gracefully if it isn't configured.

**4. The AssemblyAI realtime backend.** Before each session it fetches a short-lived token from a Cloudflare Worker proxy (so the real API key never ships in the app), then opens a WebSocket to AssemblyAI's v3 streaming endpoint with query params declaring 16kHz PCM16 audio. Microphone buffers are converted to 16kHz mono 16-bit PCM and sent as binary frames. AssemblyAI sends back JSON "turn" messages with partial then formatted-final text; the session stitches turns together in order to build the running transcript. On release it sends a "ForceEndpoint" message to flush the final turn, then "Terminate."

## The non-obvious parts
- **Modifier-only shortcuts need `flagsChanged`, not keyDown.** Holding ctrl+option produces no key-down event — only modifier-flag-change events. The monitor tracks a "was it pressed last time?" flag to convert the stream of flag changes into clean pressed/released transitions.
- **The event tap must be listen-only** (`.listenOnly`), or it would intercept keystrokes from every app. It also re-enables itself if macOS disables it after a timeout.
- **Don't restart the tap while a key is held.** A permission poller calls `start()` periodically; restarting resets the "pressed" flag and would kill the live waveform mid-speech, so `start()` is a no-op if the tap already exists.
- **Three different "final transcript" deadlines stack.** The session has an internal 1.4s grace period after ForceEndpoint to receive the formatted turn; the dictation manager has a separate ~2.8s fallback in case the session never delivers; and each provider declares its own fallback delay (AssemblyAI 2.8s, Apple 1.8s, OpenAI 8.0s because it's a slow batch POST).
- **AssemblyAI sends each turn twice** — once unformatted (raw), once formatted (punctuation/casing). The session stores turns by order and lets the formatted version overwrite the unformatted, but never the reverse.
- **One shared URLSession across all WebSocket sessions.** Creating/destroying a URLSession per session corrupts the OS connection pool and causes "Socket is not connected" errors on rapid reconnects.
- **The three providers are fundamentally different shapes** behind the same protocol: AssemblyAI streams over WebSocket (true realtime), Apple Speech feeds buffers to on-device `SFSpeechRecognizer` (realtime, offline), and OpenAI *accumulates* all buffers into a WAV file and POSTs it once at the end (not realtime — hence the 8s fallback).

## Related
- [[screen-capture-self-exclusion--from-clicky]] (the other half of the voice companion: that captures *what the user sees*, this captures *what the user says*)
- [[ai-integration/streaming-claude-screen-context--from-clicky]] (the transcribed text + screenshots become the AI prompt)
- [[tts/elevenlabs-streaming-tts--from-clicky]] (speaks the AI's reply — closes the voice loop)
- [[credential-management/cloudflare-worker-key-proxy--from-clicky]] (the proxy that mints the short-lived AssemblyAI token so the API key stays server-side)
