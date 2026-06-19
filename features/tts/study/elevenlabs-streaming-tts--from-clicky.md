# ElevenLabs Streaming TTS — from [clicky](https://github.com/farzaa/clicky)

> Domain: [[tts]] · Source: https://github.com/farzaa/clicky · NotebookLM:

## What it does
Takes the text of Claude's reply and turns it into spoken audio using ElevenLabs, then plays it through the Mac's speakers. This is the "voice" of the companion — after Claude answers a question about your screen, this is what reads the answer aloud.

## Why it exists
clicky is a voice-first companion: you talk to it, it talks back. ElevenLabs gives natural-sounding speech, and a small fast model is chosen so the reply comes back quickly. As with the Claude calls, the ElevenLabs API key must never live in the app, so the request is routed through a Cloudflare Worker proxy that holds the key.

## How it actually works
- It's a small `@MainActor` Swift class built with a proxy URL (the Worker's `/tts` route). The app never sees the ElevenLabs key or the voice-id-bearing endpoint — those live on the Worker.
- To speak, it POSTs a JSON body containing the text, the model id `eleven_flash_v2_5` (ElevenLabs' low-latency model), and voice settings (`stability: 0.5`, `similarity_boost: 0.75`). It asks for `audio/mpeg` back via the `Accept` header.
- It awaits the **entire** audio response as one `Data` blob, then hands that to an `AVAudioPlayer` and calls `play()`. The player is stored on the instance so it isn't deallocated mid-playback.
- It exposes `isPlaying` and a `stopPlayback()` that stops the player and drops the reference.

## The non-obvious parts
- **Despite the file comment claiming it "streams" so playback can begin early, the actual code does not stream playback.** It calls `session.data(for:)`, which waits for the full response, then plays. There is no chunked audio buffering and no progressive playback. (If you need true low-latency streaming, this is the spot to change.)
- **No sentence-by-sentence chunking.** The whole reply text is sent in one request. There's no splitting on punctuation to start audio sooner.
- **The voice id is not in the Swift code at all** — because the request goes to a proxy, the endpoint (which in the direct ElevenLabs API is `/v1/text-to-speech/{voiceId}/stream`) and the chosen voice live on the Worker side. The app only sends text + model + voice_settings.
- **It's cancellation-aware**: it checks `Task.checkCancellation()` after the network call but before playing, so a cancelled request won't suddenly blurt audio.
- Short timeouts (30s request / 60s resource) reflect that this is meant to be a quick call for a single utterance.

## Related
- [[ai-integration/streaming-claude-screen-context--from-clicky]] (produces the reply text this speaks; both share the same Cloudflare Worker base URL)
- [[media-processing/push-to-talk-streaming-transcription--from-clicky]] (the input side of the voice loop — speech-to-text — that this mirrors on the output side)
- [[canvas-interaction/screen-element-localization--from-clicky]] (the spoken reply may accompany an on-screen pointer to the referenced element)
- [[credential-management/cloudflare-worker-key-proxy--from-clicky]] (the proxy that injects the real ElevenLabs key so the app never holds it)
