# Streaming Claude Screen Context — from [clicky](https://github.com/farzaa/clicky)

> Domain: [[ai-integration]] · Source: https://github.com/farzaa/clicky · NotebookLM:

## What it does
This is the heart of clicky's "voice companion" loop. You press a push-to-talk key, ask a question out loud, and the app grabs a screenshot of your screen(s), sends both the picture and your transcribed question to Claude, and gets back an answer that streams in token-by-token. The streamed answer can drive an on-screen overlay and is then spoken aloud. In short: it lets Claude *see your screen* and answer questions about whatever you are looking at, in near real time.

## Why it exists
The product is a screen-aware assistant. For that to feel responsive, the reply cannot arrive as one big blob after a long wait — it needs to start appearing immediately. So the request is made with streaming turned on, and partial text is surfaced as it arrives. A second reason it is built this way: API keys must never ship inside a macOS app binary, so every call is routed through a Cloudflare Worker that holds the real key and forwards the request to Anthropic.

## How it actually works
- The model used is Claude Sonnet (`claude-sonnet-4-6`), passed in at construction time and overridable.
- The client is constructed with a *proxy URL* rather than Anthropic's real endpoint. The app points it at a Cloudflare Worker route (e.g. `.../chat`). The Worker adds the secret API key and forwards to Anthropic. The Swift code never sees the key.
- A request is built as a standard Claude Messages payload: a `system` prompt string, a `messages` array, `max_tokens`, and `stream: true`. The current screenshot(s) go in as image content blocks — each image is base64-encoded with its media type (PNG vs JPEG) detected by sniffing the first bytes of the data, because the API rejects a request whose declared type doesn't match the real bytes. Screen captures are JPEG; pasted clipboard images are PNG. Each image is followed by a small text label (including the screen's pixel dimensions), and the user's transcribed question is the final text block.
- Prior turns are replayed into the `messages` array as alternating user/assistant entries so Claude has conversation context.
- The reply comes back as Server-Sent Events. The client reads the HTTP body as a stream of lines, ignores anything not starting with `data: `, strips that prefix, parses each line as JSON, and watches for `content_block_delta` events whose delta is a `text_delta`. Each text fragment is appended to a running string, and the *whole accumulated string so far* is handed to a callback on the main thread — so the UI always has the complete text up to that point, not just the newest fragment.
- When the stream ends, the full text and the elapsed time are returned. The orchestrator (CompanionManager) wires screenshot → speech-to-text → this call → text-to-speech, and routes both Claude and ElevenLabs through the same Worker base URL.

## The non-obvious parts
- **TLS warm-up.** The very first request carries a big image payload, and a cold TLS handshake on a large body was causing intermittent `-1200` SSL handshake failures. So on init the client fires a throwaway `HEAD` request to the host just to establish and cache a TLS session ticket. It uses a `.default` (not `.ephemeral`) URLSession specifically so the ticket is cached — but disables URL/cookie caching so no responses or credentials hit disk.
- **Media type sniffing is load-bearing**, not cosmetic. Declaring `image/jpeg` for PNG bytes (or vice versa) is a hard API rejection.
- **The callback receives the cumulative string each time**, not the delta. The UI just shows the latest string; there's no client-side concatenation needed in the view.
- **There's a non-streaming twin** (`analyzeImage`) used for quick validation calls where progressive display isn't needed — same payload shape but no `stream` flag and a smaller `max_tokens`.
- In the shipped companion flow the streaming callback is actually a no-op (`{ _ in }`) and a spinner is shown instead; the overlay's text-update path still exists and is the intended mechanism for progressive display.

## Related
- [[elevenlabs-streaming-tts--from-clicky]] (the spoken reply is produced by feeding this streamed text to ElevenLabs TTS)
- [[media-processing/push-to-talk-streaming-transcription--from-clicky]] (produces the transcribed question that becomes the user prompt)
- [[canvas-interaction/screen-element-localization--from-clicky]] (Claude's reply can embed coordinates to point at on-screen elements)
- [[credential-management/cloudflare-worker-key-proxy--from-clicky]] (the proxy that injects the real API key so the app never holds it)
