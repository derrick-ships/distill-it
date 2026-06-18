# ElevenLabs Streaming TTS (build spec) — distilled from clicky

## Summary
A tiny `@MainActor` Swift `ElevenLabsTTSClient` that POSTs reply text to a Cloudflare Worker `/tts` proxy, receives MP3 audio as one `Data` blob, and plays it via `AVAudioPlayer`. Model `eleven_flash_v2_5`; voice settings `stability 0.5 / similarity_boost 0.75`. Despite the "streaming" naming, playback is **buffered/whole-response**, not progressive. No per-sentence chunking. Voice id and real endpoint live on the proxy.

## Core logic (inlined)
```swift
import AVFoundation
import Foundation

@MainActor
final class ElevenLabsTTSClient {
    private let proxyURL: URL
    private let session: URLSession

    /// Held so audio finishes even if the caller drops its reference.
    private var audioPlayer: AVAudioPlayer?

    init(proxyURL: String) {
        self.proxyURL = URL(string: proxyURL)!     // e.g. https://<worker>/tts
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 30
        configuration.timeoutIntervalForResource = 60
        self.session = URLSession(configuration: configuration)
    }

    /// Sends `text` to ElevenLabs (via proxy) and plays the resulting audio. Cancellation-safe.
    func speakText(_ text: String) async throws {
        var request = URLRequest(url: proxyURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("audio/mpeg", forHTTPHeaderField: "Accept")   // expect MP3 back

        let body: [String: Any] = [
            "text": text,
            "model_id": "eleven_flash_v2_5",                // low-latency ElevenLabs model
            "voice_settings": [
                "stability": 0.5,
                "similarity_boost": 0.75
            ]
            // NOTE: no voice_id and no output_format here — both are decided on the proxy/Worker.
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        // Whole-response fetch (NOT chunked). Waits for the full audio.
        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw NSError(domain: "ElevenLabsTTS", code: -1,
                          userInfo: [NSLocalizedDescriptionKey: "Invalid response"])
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            let errorBody = String(data: data, encoding: .utf8) ?? "Unknown error"
            throw NSError(domain: "ElevenLabsTTS", code: httpResponse.statusCode,
                userInfo: [NSLocalizedDescriptionKey: "TTS API error (\(httpResponse.statusCode)): \(errorBody)"])
        }

        try Task.checkCancellation()   // don't blurt audio if the turn was cancelled mid-flight

        let player = try AVAudioPlayer(data: data)   // AVAudioPlayer decodes MP3 from the full buffer
        self.audioPlayer = player
        player.play()
        print("🔊 ElevenLabs TTS: playing \(data.count / 1024)KB audio")
    }

    var isPlaying: Bool { audioPlayer?.isPlaying ?? false }

    func stopPlayback() {
        audioPlayer?.stop()
        audioPlayer = nil
    }
}
```

### How it's constructed and called (orchestration)
```swift
// In CompanionManager — same Worker base URL as the Claude client:
private static let workerBaseURL = "https://<worker-name>.<subdomain>.workers.dev"
private lazy var elevenLabsTTSClient = ElevenLabsTTSClient(proxyURL: "\(Self.workerBaseURL)/tts")

// After Claude's reply is assembled:
try await elevenLabsTTSClient.speakText(spokenText)
voiceState = .responding
```

## Data contracts
- **Request** (`POST <worker>/tts`):
  - Headers: `Content-Type: application/json`, `Accept: audio/mpeg`.
  - Body:
    ```json
    { "text": "<reply text>",
      "model_id": "eleven_flash_v2_5",
      "voice_settings": { "stability": 0.5, "similarity_boost": 0.75 } }
    ```
- **Response**: raw MP3 bytes (`audio/mpeg`) as the HTTP body. Non-2xx → body is UTF-8 error text.
- **Proxy responsibility**: the Worker maps this to the real ElevenLabs streaming endpoint
  `POST https://api.elevenlabs.io/v1/text-to-speech/{voiceId}/stream`, injects `xi-api-key`, picks the `voiceId` and any `output_format`, and pipes audio back.
- **Public API**: `speakText(_:) async throws`, `isPlaying: Bool`, `stopPlayback()`.

## Dependencies & assumptions
- `AVFoundation` (`AVAudioPlayer`) — decodes a complete MP3 buffer; it is NOT a streaming player.
- Swift concurrency (`async/await`, `Task.checkCancellation()`); class is `@MainActor`.
- A Worker/proxy that holds the ElevenLabs key + voice id and returns MP3.
- Assumes the response fits in memory and arrives within 30s (request timeout).

## To port this, you need:
- [ ] A proxy `/tts` endpoint that injects `xi-api-key`, chooses the voice id, hits `/v1/text-to-speech/{voiceId}/stream`, and returns MP3 bytes.
- [ ] An async HTTP call that buffers the full audio response (or, if you want real streaming, a chunked reader feeding a streaming audio engine).
- [ ] The exact body above (`text`, `model_id`, `voice_settings`); set `Accept: audio/mpeg`.
- [ ] A player that decodes the returned format (`AVAudioPlayer(data:)` for MP3) held in a retained property.
- [ ] A cancellation check between fetch and play.
- [ ] `isPlaying` / `stopPlayback` controls so the orchestrator can interrupt.

## Gotchas
- **The "streaming" in the filename is aspirational** — this implementation buffers the entire response before playing. The file comment ("playback begins before full audio is generated") does NOT match the code. For true low latency you'd need `URLSession.bytes` + `AVAudioEngine`/`AVAudioPlayerNode` and likely per-sentence requests.
- **No sentence chunking** — the whole reply goes in one call, so first audio waits on the full synthesis.
- **Must retain the `AVAudioPlayer`** in a property; a local-only player deallocates and playback dies instantly.
- **Voice id is not in the client** — if you point this directly at ElevenLabs it will fail (no key, no voice in the URL). It only works against a proxy.
- `Task.checkCancellation()` is after the network call but before `play()` — a cancelled task still pays for the synthesis network round-trip; it just won't play.
- `eleven_flash_v2_5` is chosen specifically for latency; swapping to a higher-quality model increases time-to-first-audio.

## Origin (reference only)
- `leanring-buddy/ElevenLabsTTSClient.swift` (entire class — inlined above in full).
- `leanring-buddy/CompanionManager.swift` (construction via `workerBaseURL`/`/tts`, call site `speakText`).
- Repo: https://github.com/farzaa/clicky (assume gone — everything needed is inlined above).
