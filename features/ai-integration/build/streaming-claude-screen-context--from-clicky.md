# Streaming Claude Screen Context (build spec) — distilled from clicky

## Summary
A Swift `ClaudeAPI` class that sends one or more base64 screenshots plus a text prompt to Claude's Messages API **with `stream: true`**, parses the SSE response line-by-line, and emits the cumulative response text to a `@MainActor` callback on every `text_delta`. All traffic goes through a Cloudflare Worker proxy URL (not `api.anthropic.com`) so the API key stays server-side. Model: `claude-sonnet-4-6`.

## Core logic (inlined)

### Class skeleton, init, proxy URL, session + TLS warm-up
```swift
import Foundation

class ClaudeAPI {
    private static let tlsWarmupLock = NSLock()
    private static var hasStartedTLSWarmup = false

    private let apiURL: URL          // the Cloudflare Worker route, e.g. https://<worker>/chat
    var model: String
    private let session: URLSession

    init(proxyURL: String, model: String = "claude-sonnet-4-6") {
        self.apiURL = URL(string: proxyURL)!
        self.model = model

        // .default (NOT .ephemeral) so TLS session tickets are cached. Ephemeral does a full
        // handshake every request -> transient -1200 errSSLPeerHandshakeFail with big image payloads.
        // Disable URL/cookie caching so nothing is persisted to disk.
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 120
        config.timeoutIntervalForResource = 300
        config.waitsForConnectivity = true
        config.urlCache = nil
        config.httpCookieStorage = nil
        self.session = URLSession(configuration: config)

        warmUpTLSConnectionIfNeeded()
    }

    private func makeAPIRequest() -> URLRequest {
        var request = URLRequest(url: apiURL)
        request.httpMethod = "POST"
        request.timeoutInterval = 120
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        return request   // NOTE: no x-api-key / anthropic-version header — the Worker injects those.
    }

    // Sniff PNG signature; default to JPEG. The API rejects a request whose declared media_type
    // doesn't match the actual bytes. ScreenCaptureKit grabs are JPEG; clipboard pastes are PNG.
    private func detectImageMediaType(for imageData: Data) -> String {
        if imageData.count >= 4 {
            let pngSignature: [UInt8] = [0x89, 0x50, 0x4E, 0x47] // .PNG
            if [UInt8](imageData.prefix(4)) == pngSignature { return "image/png" }
        }
        return "image/jpeg"
    }

    // Throwaway HEAD to the host root to cache a TLS session ticket before the first big request.
    // Runs once per process; failures ignored.
    private func warmUpTLSConnectionIfNeeded() {
        Self.tlsWarmupLock.lock()
        let shouldStart = !Self.hasStartedTLSWarmup
        if shouldStart { Self.hasStartedTLSWarmup = true }
        Self.tlsWarmupLock.unlock()
        guard shouldStart else { return }

        guard var comps = URLComponents(url: apiURL, resolvingAgainstBaseURL: false) else { return }
        comps.path = "/"; comps.query = nil; comps.fragment = nil
        guard let warmupURL = comps.url else { return }

        var warmupRequest = URLRequest(url: warmupURL)
        warmupRequest.httpMethod = "HEAD"
        warmupRequest.timeoutInterval = 10
        session.dataTask(with: warmupRequest) { _, _, _ in }.resume()
    }
}
```

### Streaming request + SSE parse (the primary path)
```swift
/// Calls `onTextChunk` on the main actor each time new text arrives (passing the CUMULATIVE text).
/// Returns the full text and total duration when the stream completes.
func analyzeImageStreaming(
    images: [(data: Data, label: String)],
    systemPrompt: String,
    conversationHistory: [(userPlaceholder: String, assistantResponse: String)] = [],
    userPrompt: String,
    onTextChunk: @MainActor @Sendable (String) -> Void
) async throws -> (text: String, duration: TimeInterval) {
    let startTime = Date()
    var request = makeAPIRequest()

    // 1. Replay prior turns as alternating user/assistant messages.
    var messages: [[String: Any]] = []
    for (userPlaceholder, assistantResponse) in conversationHistory {
        messages.append(["role": "user", "content": userPlaceholder])
        messages.append(["role": "assistant", "content": assistantResponse])
    }

    // 2. Current user turn = [image, label, image, label, ..., userPrompt] content blocks.
    var contentBlocks: [[String: Any]] = []
    for image in images {
        contentBlocks.append([
            "type": "image",
            "source": [
                "type": "base64",
                "media_type": detectImageMediaType(for: image.data),
                "data": image.data.base64EncodedString()
            ]
        ])
        contentBlocks.append(["type": "text", "text": image.label])
    }
    contentBlocks.append(["type": "text", "text": userPrompt])
    messages.append(["role": "user", "content": contentBlocks])

    // 3. Body. system is a top-level string. stream: true.
    let body: [String: Any] = [
        "model": model,
        "max_tokens": 1024,
        "stream": true,
        "system": systemPrompt,
        "messages": messages
    ]
    request.httpBody = try JSONSerialization.data(withJSONObject: body)

    // 4. Byte stream for SSE.
    let (byteStream, response) = try await session.bytes(for: request)
    guard let httpResponse = response as? HTTPURLResponse else {
        throw NSError(domain: "ClaudeAPI", code: -1,
                      userInfo: [NSLocalizedDescriptionKey: "Invalid HTTP response"])
    }
    // Non-2xx: drain the stream as the error body.
    guard (200...299).contains(httpResponse.statusCode) else {
        var chunks: [String] = []
        for try await line in byteStream.lines { chunks.append(line) }
        throw NSError(domain: "ClaudeAPI", code: httpResponse.statusCode,
            userInfo: [NSLocalizedDescriptionKey: "API Error (\(httpResponse.statusCode)): \(chunks.joined(separator: "\n"))"])
    }

    // 5. Parse SSE. Each event line is "data: {json}". Watch content_block_delta -> text_delta.
    var accumulatedResponseText = ""
    for try await line in byteStream.lines {
        guard line.hasPrefix("data: ") else { continue }
        let jsonString = String(line.dropFirst(6))      // drop "data: "
        guard jsonString != "[DONE]" else { break }
        guard let jsonData = jsonString.data(using: .utf8),
              let eventPayload = try? JSONSerialization.jsonObject(with: jsonData) as? [String: Any],
              let eventType = eventPayload["type"] as? String else { continue }

        if eventType == "content_block_delta",
           let delta = eventPayload["delta"] as? [String: Any],
           (delta["type"] as? String) == "text_delta",
           let textChunk = delta["text"] as? String {
            accumulatedResponseText += textChunk
            let current = accumulatedResponseText        // capture cumulative string
            await onTextChunk(current)                   // emit FULL text-so-far, not the delta
        }
    }

    return (text: accumulatedResponseText, duration: Date().timeIntervalSince(startTime))
}
```

### Non-streaming twin (validation path)
Same message/body builder, but no `stream`, `max_tokens: 256`, and it parses the final JSON: `json["content"]` -> first block with `type == "text"` -> `["text"]`. Use when you don't need progressive display.

### Orchestration (CompanionManager, abridged)
```swift
private static let workerBaseURL = "https://<worker-name>.<subdomain>.workers.dev"

private lazy var claudeAPI = ClaudeAPI(proxyURL: "\(Self.workerBaseURL)/chat", model: selectedModel)
private lazy var elevenLabsTTSClient = ElevenLabsTTSClient(proxyURL: "\(Self.workerBaseURL)/tts")

// push-to-talk completion -> sendTranscriptToClaudeWithScreenshot(transcript:)
let screenCaptures = try await CompanionScreenCaptureUtility.captureAllScreensAsJPEG()
let labeledImages = screenCaptures.map { cap in
    (data: cap.imageData,
     label: cap.label + " (image dimensions: \(cap.screenshotWidthInPixels)x\(cap.screenshotHeightInPixels) pixels)")
}
let (fullResponseText, _) = try await claudeAPI.analyzeImageStreaming(
    images: labeledImages,
    systemPrompt: Self.companionVoiceResponseSystemPrompt,
    conversationHistory: historyForAPI,
    userPrompt: transcript,
    onTextChunk: { _ in }            // shipped flow shows a spinner; see overlay below for live-text path
)
// then: parse [POINT:x,y:label] from fullResponseText (optional) and:
try await elevenLabsTTSClient.speakText(spokenText)
```

### Overlay live-text path (the intended progressive UI)
```swift
// CompanionManager-side updater bound to onTextChunk:
func updateStreamingText(_ accumulatedText: String) {
    overlayViewModel.streamingResponseText = accumulatedText
    resizePanelToFitContent()
}
// SwiftUI view re-renders on every update:
Text(viewModel.streamingResponseText.isEmpty ? "..." : viewModel.streamingResponseText)
    .font(.system(size: 13, weight: .regular))
    .fixedSize(horizontal: false, vertical: true)
// Panel: NSPanel(styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
//        content = NSHostingView(CompanionResponseOverlayView), floats above all apps.
```

## Data contracts
- **Request body** (`POST <worker>/chat`, `Content-Type: application/json`):
  ```json
  {
    "model": "claude-sonnet-4-6",
    "max_tokens": 1024,
    "stream": true,
    "system": "<system prompt string>",
    "messages": [
      {"role":"user","content":"<prior user placeholder>"},
      {"role":"assistant","content":"<prior assistant text>"},
      {"role":"user","content":[
        {"type":"image","source":{"type":"base64","media_type":"image/jpeg","data":"<b64>"}},
        {"type":"text","text":"Screen 1 (image dimensions: 2560x1440 pixels)"},
        {"type":"text","text":"<transcribed user question>"}
      ]}
    ]
  }
  ```
- **SSE event consumed**: lines `data: {json}`; relevant `{"type":"content_block_delta","delta":{"type":"text_delta","text":"..."}}`. `[DONE]` (or stream end) terminates.
- **Callback contract**: `onTextChunk` receives the **cumulative** string each time, on the main actor.
- **Return**: `(text: String, duration: TimeInterval)`.
- The Worker is responsible for adding `x-api-key` and `anthropic-version` and forwarding to `https://api.anthropic.com/v1/messages` (the Swift client sends neither).

## Dependencies & assumptions
- Swift concurrency: `URLSession.bytes(for:)` async byte streaming (macOS 12+/iOS 15+).
- `JSONSerialization` for both encode and SSE decode (no Codable models).
- A reachable Cloudflare Worker (or any proxy) that: accepts this JSON body, injects the Anthropic key, sets streaming, and pipes the SSE response straight back unmodified.
- Caller supplies screenshots as `Data` (JPEG/PNG), a system prompt, optional history, and the user prompt.
- Anthropic Messages API SSE semantics: `content_block_delta` / `text_delta`.

## To port this, you need:
- [ ] A proxy endpoint that holds the Anthropic key and forwards `/v1/messages` with `stream: true`, returning the raw SSE byte stream.
- [ ] An async HTTP client that exposes the response as a line stream (Swift `URLSession.bytes`; in other langs use a chunked/SSE reader).
- [ ] The exact body shape above (top-level `system` string; image blocks as base64 `source`).
- [ ] Media-type sniffing (PNG magic bytes `89 50 4E 47`, else JPEG) — do NOT hardcode.
- [ ] SSE parse: split on lines, keep `data: ` lines, JSON-parse, filter `content_block_delta`/`text_delta`, accumulate, emit cumulative text.
- [ ] A main-thread UI sink that renders the latest cumulative string and resizes to fit.
- [ ] (Optional but recommended) a one-shot TLS warm-up HEAD before the first large request.

## Gotchas
- **`.ephemeral` URLSession breaks large image uploads** with `-1200` SSL handshake errors. Use `.default` + warm-up; disable disk caching separately for privacy.
- **media_type must match the actual bytes** or the API 400s.
- The callback emits the **whole accumulated string**, so a naive UI that appends will duplicate text — just assign, don't concatenate.
- No `x-api-key` / `anthropic-version` headers on the client — they live in the proxy. If you point this at `api.anthropic.com` directly it will fail auth.
- `[DONE]` handling is present but Anthropic's stream normally just ends; the `for await` loop terminating is the real end signal.
- The shipped companion flow passes `onTextChunk: { _ in }` (spinner UI); the `updateStreamingText` overlay path is the real progressive-display mechanism if you want live tokens.
- Image payloads can be multiple MB; the request timeout is 120s and `waitsForConnectivity` is on.

## Origin (reference only)
- `leanring-buddy/ClaudeAPI.swift` (primary — class, init, `analyzeImageStreaming`, `analyzeImage`, `detectImageMediaType`, TLS warm-up).
- `leanring-buddy/CompanionManager.swift` (orchestration: screenshot → STT → Claude → TTS; `workerBaseURL`, lazy client construction).
- `leanring-buddy/CompanionResponseOverlay.swift` (`updateStreamingText` / `streamingResponseText`, NSPanel + NSHostingView overlay).
- Repo: https://github.com/farzaa/clicky (assume gone — everything needed is inlined above).
