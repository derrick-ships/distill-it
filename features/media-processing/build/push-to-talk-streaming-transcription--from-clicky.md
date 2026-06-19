# Push-to-Talk Streaming Transcription (build spec) — distilled from clicky

## Summary
Global modifier-only hotkey (ctrl+option) via a listen-only CGEvent tap drives push-to-talk dictation. An `AVAudioEngine` mic tap streams buffers into a pluggable `BuddyTranscriptionProvider`; the default `AssemblyAIStreamingTranscriptionProvider` converts buffers to 16kHz PCM16 and streams them over a WebSocket to AssemblyAI v3, stitching ordered "turn" messages into partial + final transcripts. Apple Speech and OpenAI are swappable alternates selected by Info.plist key.

## Core logic (inlined)

### 1. Global hotkey monitor (listen-only CGEvent tap)

```swift
import AppKit; import Combine; import CoreGraphics; import Foundation

final class GlobalPushToTalkShortcutMonitor: ObservableObject {
    let shortcutTransitionPublisher = PassthroughSubject<BuddyPushToTalkShortcut.ShortcutTransition, Never>()
    private var globalEventTap: CFMachPort?
    private var globalEventTapRunLoopSource: CFRunLoopSource?
    @Published private(set) var isShortcutCurrentlyPressed = false   // mutated only from tap callback (main thread)

    deinit { stop() }

    func start() {
        guard globalEventTap == nil else { return }   // NEVER restart while held — resets pressed flag, kills waveform

        let monitoredEventTypes: [CGEventType] = [.flagsChanged, .keyDown, .keyUp]
        let eventMask = monitoredEventTypes.reduce(CGEventMask(0)) { $0 | (CGEventMask(1) << $1.rawValue) }

        let eventTapCallback: CGEventTapCallBack = { _, eventType, event, userInfo in
            guard let userInfo else { return Unmanaged.passUnretained(event) }
            let monitor = Unmanaged<GlobalPushToTalkShortcutMonitor>.fromOpaque(userInfo).takeUnretainedValue()
            return monitor.handleGlobalEventTap(eventType: eventType, event: event)
        }

        guard let tap = CGEvent.tapCreate(
            tap: .cgSessionEventTap, place: .headInsertEventTap,
            options: .listenOnly,                    // listen-only: never swallow keystrokes from other apps
            eventsOfInterest: eventMask, callback: eventTapCallback,
            userInfo: Unmanaged.passUnretained(self).toOpaque()
        ) else { print("⚠️ couldn't create CGEvent tap"); return }

        guard let source = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0) else {
            CFMachPortInvalidate(tap); return
        }
        self.globalEventTap = tap; self.globalEventTapRunLoopSource = source
        CFRunLoopAddSource(CFRunLoopGetMain(), source, .commonModes)   // runs on main run loop
        CGEvent.tapEnable(tap: tap, enable: true)
    }

    func stop() {
        isShortcutCurrentlyPressed = false
        if let s = globalEventTapRunLoopSource { CFRunLoopRemoveSource(CFRunLoopGetMain(), s, .commonModes); globalEventTapRunLoopSource = nil }
        if let t = globalEventTap { CFMachPortInvalidate(t); globalEventTap = nil }
    }

    private func handleGlobalEventTap(eventType: CGEventType, event: CGEvent) -> Unmanaged<CGEvent>? {
        if eventType == .tapDisabledByTimeout || eventType == .tapDisabledByUserInput {
            if let t = globalEventTap { CGEvent.tapEnable(tap: t, enable: true) }   // re-arm if OS disables us
            return Unmanaged.passUnretained(event)
        }
        let keyCode = UInt16(event.getIntegerValueField(.keyboardEventKeycode))
        let transition = BuddyPushToTalkShortcut.shortcutTransition(
            for: eventType, keyCode: keyCode,
            modifierFlagsRawValue: event.flags.rawValue,
            wasShortcutPreviouslyPressed: isShortcutCurrentlyPressed
        )
        switch transition {
        case .none: break
        case .pressed:  isShortcutCurrentlyPressed = true;  shortcutTransitionPublisher.send(.pressed)
        case .released: isShortcutCurrentlyPressed = false; shortcutTransitionPublisher.send(.released)
        }
        return Unmanaged.passUnretained(event)   // listen-only: always pass through unchanged
    }
}
```

### 2. Shortcut definition / transition logic (modifier-only vs. letter+modifier)

```swift
enum BuddyPushToTalkShortcut {
    enum ShortcutOption { case shiftFunction, controlOption, shiftControl, controlOptionSpace, shiftControlSpace
        fileprivate var modifierOnlyFlags: NSEvent.ModifierFlags? {
            switch self {
            case .shiftFunction: return [.shift, .function]
            case .controlOption: return [.control, .option]
            case .shiftControl:  return [.shift, .control]
            case .controlOptionSpace, .shiftControlSpace: return nil   // these are key+modifier, not modifier-only
            }
        }
        fileprivate var spaceShortcutModifierFlags: NSEvent.ModifierFlags? {
            switch self {
            case .controlOptionSpace: return [.control, .option]
            case .shiftControlSpace:  return [.shift, .control]
            default: return nil
            }
        }
    }
    enum ShortcutTransition { case none, pressed, released }

    static let currentShortcutOption: ShortcutOption = .controlOption   // <-- DEFAULT
    static let pushToTalkKeyCode: UInt16 = 49   // Space

    // CGEvent path (used by the global tap):
    static func shortcutTransition(for eventType: CGEventType, keyCode: UInt16,
                                   modifierFlagsRawValue: UInt64, wasShortcutPreviouslyPressed: Bool) -> ShortcutTransition {
        // maps CGEventType -> {flagsChanged,keyDown,keyUp}; converts raw flags to NSEvent.ModifierFlags
        // masked with .deviceIndependentFlagsMask, then delegates to the core resolver below.
        // (NSEvent path also exists for in-app monitoring.)
    }

    // Core resolver:
    //  - If shortcut is MODIFIER-ONLY: only react to .flagsChanged.
    //      pressed  = flags NOW contain all required modifiers && !wasPreviouslyPressed
    //      released = flags NO LONGER contain them          && wasPreviouslyPressed
    //  - Else (key+modifier): pressed = .keyDown && keyCode==Space && flags ⊇ requiredModifiers && !wasPreviouslyPressed
    //                         released = .keyUp  && keyCode==Space && wasPreviouslyPressed
}
```

### 3. Provider protocols + selection factory

```swift
import AVFoundation; import Foundation

protocol BuddyStreamingTranscriptionSession: AnyObject {
    var finalTranscriptFallbackDelaySeconds: TimeInterval { get }   // AssemblyAI 2.8, Apple 1.8, OpenAI 8.0
    func appendAudioBuffer(_ audioBuffer: AVAudioPCMBuffer)
    func requestFinalTranscript()
    func cancel()
}

protocol BuddyTranscriptionProvider {
    var displayName: String { get }
    var requiresSpeechRecognitionPermission: Bool { get }   // true only for Apple Speech
    var isConfigured: Bool { get }
    var unavailableExplanation: String? { get }
    func startStreamingSession(
        keyterms: [String],
        onTranscriptUpdate: @escaping (String) -> Void,      // partial / running transcript
        onFinalTranscriptReady: @escaping (String) -> Void,  // committed final, delivered ONCE
        onError: @escaping (Error) -> Void
    ) async throws -> any BuddyStreamingTranscriptionSession
}

enum BuddyTranscriptionProviderFactory {
    private enum PreferredProvider: String { case assemblyAI = "assemblyai", openAI = "openai", appleSpeech = "apple" }
    static func makeDefaultProvider() -> any BuddyTranscriptionProvider {
        // Reads Info.plist "VoiceTranscriptionProvider" (lowercased).
        // apple -> AppleSpeechTranscriptionProvider (always)
        // assemblyai -> AssemblyAI if isConfigured else OpenAI(if configured) else Apple
        // openai -> OpenAI if isConfigured else AssemblyAI(if configured) else Apple
        // unset -> AssemblyAI(if configured) else OpenAI(if configured) else Apple
    }
}
```

### 4. Dictation manager — mic tap + lifecycle (key methods)

```swift
@MainActor
final class BuddyDictationManager: NSObject, ObservableObject {
    private static let defaultFinalTranscriptFallbackDelaySeconds: TimeInterval = 2.4
    private let transcriptionProvider: any BuddyTranscriptionProvider
    private let audioEngine = AVAudioEngine()
    private var activeTranscriptionSession: (any BuddyStreamingTranscriptionSession)?
    private var latestRecognizedText = ""
    private var finalizeFallbackWorkItem: DispatchWorkItem?

    init() {
        let p = BuddyTranscriptionProviderFactory.makeDefaultProvider()
        self.transcriptionProvider = p; super.init()
    }

    private func startRecognitionSession() async throws {
        activeTranscriptionSession?.cancel(); activeTranscriptionSession = nil

        let session = try await transcriptionProvider.startStreamingSession(
            keyterms: buildTranscriptionKeyterms(),
            onTranscriptUpdate:    { [weak self] t in Task { @MainActor in self?.latestRecognizedText = t } },
            onFinalTranscriptReady:{ [weak self] t in Task { @MainActor in
                guard let self else { return }
                self.latestRecognizedText = t
                if self.isFinalizingTranscript { self.finishCurrentDictationSessionIfNeeded(shouldSubmitFinalDraft: self.shouldAutomaticallySubmitFinalDraft) }
            }},
            onError: { [weak self] e in Task { @MainActor in self?.handleRecognitionError(e) } }
        )
        self.activeTranscriptionSession = session

        // MIC TAP: native input format, 1024-frame buffers. Provider does any resampling.
        let inputNode = audioEngine.inputNode
        let inputFormat = inputNode.outputFormat(forBus: 0)
        inputNode.removeTap(onBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: inputFormat) { [weak self] buffer, _ in
            self?.activeTranscriptionSession?.appendAudioBuffer(buffer)
            self?.updateAudioPowerLevel(from: buffer)   // RMS -> waveform UI
        }
        audioEngine.prepare()
        try audioEngine.start()
    }

    // STOP (key released): stop engine, flush final, arm fallback timer.
    private func stopPushToTalk(expectedStartSource: BuddyDictationStartSource) {
        guard activeStartSource == expectedStartSource else { isPreparingToRecord = false; return }
        guard !isFinalizingTranscript else { return }
        isRecordingFromMicrophoneButton = false; isRecordingFromKeyboardShortcut = false
        isFinalizingTranscript = true
        let delay = activeTranscriptionSession?.finalTranscriptFallbackDelaySeconds ?? Self.defaultFinalTranscriptFallbackDelaySeconds
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        activeTranscriptionSession?.requestFinalTranscript()
        finalizeFallbackWorkItem?.cancel()
        let work = DispatchWorkItem { [weak self] in Task { @MainActor in
            self?.finishCurrentDictationSessionIfNeeded(shouldSubmitFinalDraft: /*captured*/ false) } }
        finalizeFallbackWorkItem = work
        DispatchQueue.main.asyncAfter(deadline: .now() + delay, execute: work)
    }
    // finishCurrentDictationSessionIfNeeded composes draft (existing + transcript) and submits ONCE.
    // RMS level: sqrt(sum(sample^2)/n) * 10.2, clamped 0...1, smoothed max(level, prev*0.72).
}
```

### 5. AssemblyAI realtime backend — token proxy + provider

```swift
final class AssemblyAIStreamingTranscriptionProvider: BuddyTranscriptionProvider {
    // Cloudflare Worker mints a short-lived token; real API key never ships in the app.
    private static let tokenProxyURL = "https://your-worker-name.your-subdomain.workers.dev/transcribe-token"
    let displayName = "AssemblyAI"
    let requiresSpeechRecognitionPermission = false
    var isConfigured: Bool { true }
    var unavailableExplanation: String? { nil }

    // ONE shared URLSession for ALL ws sessions — per-session sessions corrupt the OS
    // connection pool -> "Socket is not connected" on rapid reconnect.
    private let sharedWebSocketURLSession = URLSession(configuration: .default)

    func startStreamingSession(keyterms: [String], onTranscriptUpdate: @escaping (String)->Void,
                               onFinalTranscriptReady: @escaping (String)->Void, onError: @escaping (Error)->Void
    ) async throws -> any BuddyStreamingTranscriptionSession {
        let token = try await fetchTemporaryToken()
        let session = AssemblyAIStreamingTranscriptionSession(
            apiKey: nil, temporaryToken: token, urlSession: sharedWebSocketURLSession,
            keyterms: keyterms, onTranscriptUpdate: onTranscriptUpdate,
            onFinalTranscriptReady: onFinalTranscriptReady, onError: onError)
        try await session.open()
        return session
    }

    private func fetchTemporaryToken() async throws -> String {
        var request = URLRequest(url: URL(string: Self.tokenProxyURL)!)
        request.httpMethod = "POST"
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw AssemblyAIStreamingTranscriptionProviderError(message: "Failed to fetch token …")
        }
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let token = json["token"] as? String else {
            throw AssemblyAIStreamingTranscriptionProviderError(message: "Invalid token response from proxy.")
        }
        return token
    }
}
```

### 6. AssemblyAI session — WebSocket protocol, turn stitching

```swift
private final class AssemblyAIStreamingTranscriptionSession: NSObject, BuddyStreamingTranscriptionSession {
    private struct MessageEnvelope: Decodable { let type: String }
    private struct TurnMessage: Decodable {
        let type: String; let transcript: String?; let turn_order: Int?
        let end_of_turn: Bool?; let turn_is_formatted: Bool?
    }
    private struct ErrorMessage: Decodable { let type: String; let error: String?; let message: String? }
    private struct StoredTurnTranscript { var transcriptText: String; var isFormatted: Bool }

    private static let websocketBaseURLString = "wss://streaming.assemblyai.com/v3/ws"
    private static let targetSampleRate = 16_000.0
    private static let explicitFinalTranscriptGracePeriodSeconds = 1.4   // wait for formatted turn after ForceEndpoint
    let finalTranscriptFallbackDelaySeconds: TimeInterval = 2.8

    private let stateQueue = DispatchQueue(label: "…assemblyai.state")   // all transcript state mutated here
    private let sendQueue  = DispatchQueue(label: "…assemblyai.send")    // serializes ws sends
    private let audioPCM16Converter = BuddyPCM16AudioConverter(targetSampleRate: targetSampleRate)
    private var webSocketTask: URLSessionWebSocketTask?
    private var activeTurnOrder: Int?
    private var activeTurnTranscriptText = ""
    private var storedTurnTranscriptsByOrder: [Int: StoredTurnTranscript] = [:]
    private var hasDeliveredFinalTranscript = false
    private var isAwaitingExplicitFinalTranscript = false

    func open() async throws {
        let url = try Self.makeWebsocketURL(temporaryToken: temporaryToken, keyterms: keyterms)
        var req = URLRequest(url: url)
        if let apiKey { req.setValue(apiKey, forHTTPHeaderField: "Authorization") }   // token usually in query instead
        let task = urlSession.webSocketTask(with: req); webSocketTask = task; task.resume()
        receiveNextMessage()
        try await withCheckedThrowingContinuation { c in stateQueue.async { self.readyContinuation = c } } // resolves on "Begin"
    }

    // URL query params (encoding declared up front):
    //   sample_rate=16000, encoding=pcm_s16le, format_turns=true, speech_model=u3-rt-pro,
    //   keyterms_prompt=<JSON array string> (optional), token=<temp token>

    func appendAudioBuffer(_ buffer: AVAudioPCMBuffer) {
        guard let pcm16 = audioPCM16Converter.convertToPCM16Data(from: buffer), !pcm16.isEmpty else { return }
        sendQueue.async { [weak self] in self?.webSocketTask?.send(.data(pcm16)) { e in if let e { self?.failSession(with: e) } } }
    }

    func requestFinalTranscript() {        // key released
        stateQueue.async { guard !self.hasDeliveredFinalTranscript else { return }
            self.isAwaitingExplicitFinalTranscript = true; self.scheduleExplicitFinalTranscriptDeadline() }
        sendJSONMessage(["type": "ForceEndpoint"])
    }
    func cancel() { sendJSONMessage(["type": "Terminate"]); webSocketTask?.cancel(with: .goingAway, reason: nil) }

    // Incoming JSON, decode envelope.type (lowercased):
    //   "begin"       -> resolve ready continuation
    //   "turn"        -> handleTurnMessage (below)
    //   "termination" -> if awaiting final & not delivered -> deliver bestAvailableTranscriptText()
    //   "error"       -> failSession(error ?? message)

    private func handleTurnMessage(_ m: TurnMessage) {
        let text = m.transcript?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        stateQueue.async {
            let order = m.turn_order ?? self.activeTurnOrder ?? ((self.storedTurnTranscriptsByOrder.keys.max() ?? -1) + 1)
            if m.end_of_turn == true || m.turn_is_formatted == true {       // finalize this turn
                self.activeTurnOrder = nil; self.activeTurnTranscriptText = ""
                self.storeTurnTranscript(text, forTurnOrder: order, isFormatted: m.turn_is_formatted == true)
            } else {                                                        // partial
                self.activeTurnOrder = order; self.activeTurnTranscriptText = text
            }
            let full = self.composeFullTranscript(); self.latestTranscriptText = full
            if !full.isEmpty { self.onTranscriptUpdate(full) }
            guard self.isAwaitingExplicitFinalTranscript else { return }
            if m.end_of_turn == true || m.turn_is_formatted == true {
                self.explicitFinalTranscriptDeadlineWorkItem?.cancel()
                self.deliverFinalTranscriptIfNeeded(self.bestAvailableTranscriptText())
            }
        }
    }

    // storeTurnTranscript: a FORMATTED turn must NOT be overwritten by an UNFORMATTED one of same order.
    // composeFullTranscript: stored turns sorted by key, joined " ", then active partial appended.
    // deliverFinalTranscriptIfNeeded: guard once, fire onFinalTranscriptReady, then send Terminate.
    // failSession: if awaiting final & have partial -> deliver partial as fallback; else onError.
}
```

### 7. PCM16 audio conversion (16kHz mono interleaved)

```swift
final class BuddyPCM16AudioConverter {
    private let targetAudioFormat: AVAudioFormat
    private var audioConverter: AVAudioConverter?
    private var currentInputFormatDescription: String?

    init(targetSampleRate: Double) {
        self.targetAudioFormat = AVAudioFormat(
            commonFormat: .pcmFormatInt16, sampleRate: targetSampleRate,
            channels: 1, interleaved: true)!
    }

    func convertToPCM16Data(from buffer: AVAudioPCMBuffer) -> Data? {
        let desc = buffer.format.settings.description
        if currentInputFormatDescription != desc {          // rebuild converter only when input format changes
            audioConverter = AVAudioConverter(from: buffer.format, to: targetAudioFormat)
            currentInputFormatDescription = desc
        }
        guard let audioConverter else { return nil }
        let ratio = targetAudioFormat.sampleRate / buffer.format.sampleRate
        let outCap = AVAudioFrameCount((Double(buffer.frameLength) * ratio).rounded(.up) + 32)  // +32 frame headroom
        guard let outBuf = AVAudioPCMBuffer(pcmFormat: targetAudioFormat, frameCapacity: outCap) else { return nil }
        var provided = false; var err: NSError?
        let status = audioConverter.convert(to: outBuf, error: &err) { _, outStatus in
            if provided { outStatus.pointee = .noDataNow; return nil }
            provided = true; outStatus.pointee = .haveData; return buffer
        }
        guard status != .error, let ptr = outBuf.audioBufferList.pointee.mBuffers.mData else { return nil }
        let bpf = Int(targetAudioFormat.streamDescription.pointee.mBytesPerFrame)
        let n = Int(outBuf.frameLength) * bpf
        guard n > 0 else { return nil }
        return Data(bytes: ptr, count: n)
    }
}
// BuddyWAVFileBuilder.buildWAVData(fromPCM16MonoAudio:sampleRate:...) wraps PCM16 in a RIFF/WAVE header
// (PCM format=1) — used by the OpenAI provider to POST a .wav.
```

## Data contracts
- **Hotkey events:** `ShortcutTransition { none | pressed | released }` published on `shortcutTransitionPublisher`.
- **Mic buffers:** native-format `AVAudioPCMBuffer`, 1024 frames, from `AVAudioEngine.inputNode` tap. Provider resamples.
- **Provider → caller callbacks:** `onTranscriptUpdate(String)` = running/partial; `onFinalTranscriptReady(String)` = committed final, **fired exactly once**; `onError(Error)`.
- **AssemblyAI WebSocket:** `wss://streaming.assemblyai.com/v3/ws` + query `sample_rate=16000&encoding=pcm_s16le&format_turns=true&speech_model=u3-rt-pro[&keyterms_prompt=<JSON array>][&token=<temp>]`. Outbound: binary PCM16 frames; control JSON `{"type":"ForceEndpoint"}`, `{"type":"Terminate"}`. Inbound JSON types: `Begin`, `Turn` (`{transcript, turn_order, end_of_turn, turn_is_formatted}`), `Termination`, `Error`.
- **Token proxy:** `POST <worker>/transcribe-token` → `{"token": "<short-lived>"}`.
- **Audio target format:** Int16, 16000 Hz, 1 channel, interleaved → raw `Data` (or WAV via builder).
- **Provider fallback delays:** AssemblyAI 2.8s, Apple 1.8s, OpenAI 8.0s; internal AAI grace after ForceEndpoint 1.4s; manager default 2.4s.

## Dependencies & assumptions
- macOS, frameworks: `AppKit`, `AVFoundation`, `CoreGraphics`, `Combine`, `Speech` (Apple provider), `Foundation`.
- **Accessibility/Input-Monitoring permission** required for the CGEvent tap (and Screen Recording is unrelated here). Mic permission via `AVCaptureDevice`. Speech permission via `SFSpeechRecognizer` only for Apple provider.
- A deployed Cloudflare Worker that proxies AssemblyAI's token endpoint (keeps the API key server-side) — see [[credential-management/cloudflare-worker-key-proxy--from-clicky]].
- Info.plist keys: `VoiceTranscriptionProvider` (assemblyai|openai|apple), `OpenAIAPIKey`, `OpenAITranscriptionModel` (default `gpt-4o-transcribe`).
- App keeps running in background (event tap is system-wide).

## To port this, you need:
- [ ] CGEvent tap created with `.listenOnly` + `.cgSessionEventTap`, added to `CFRunLoopGetMain()`; re-enable on `tapDisabledByTimeout`/`ByUserInput`.
- [ ] Convert the flag-change stream into pressed/released using a "was previously pressed" flag (modifier-only shortcuts emit `.flagsChanged`, NOT keyDown).
- [ ] Guard `start()` to no-op if the tap already exists (don't reset state mid-press).
- [ ] `AVAudioEngine` input tap (1024 frames, native format) forwarding buffers to the active session.
- [ ] The two protocols (`BuddyTranscriptionProvider`, `BuddyStreamingTranscriptionSession`) + a factory that reads config and falls back when a provider is unconfigured.
- [ ] `BuddyPCM16AudioConverter` (16kHz mono Int16) — only rebuild `AVAudioConverter` when input format changes; add ~32-frame output headroom.
- [ ] AssemblyAI session: build the query-param URL, send binary PCM16, decode `MessageEnvelope` then specific type, stitch turns by `turn_order`, let formatted overwrite unformatted (never reverse), deliver final once.
- [ ] Stacked deadlines: internal grace (1.4s) + manager fallback (provider's delay) so a missing final never hangs the UI.
- [ ] ONE shared `URLSession` reused across all WebSocket sessions.
- [ ] Permission de-dup: single in-flight permission `Task` + ~1s cooldown trusting the cached result.

## Gotchas
- **Modifier-only shortcuts produce no keyDown** — you MUST watch `.flagsChanged` and diff against the previous pressed state, or the hotkey never fires.
- **Tap must be `.listenOnly`** or you intercept (and can drop) keystrokes for every app. Always return `Unmanaged.passUnretained(event)`.
- **Never restart the tap while held** — a periodic permission poller calling `start()` would otherwise reset `isShortcutCurrentlyPressed` and kill an in-progress dictation/waveform.
- **AssemblyAI emits each turn twice** (unformatted then formatted). Store by `turn_order` and only let formatted overwrite unformatted, never the reverse, or you'll downgrade punctuation.
- **One URLSession for all WebSocket sessions** — per-session `URLSession` corrupts the OS connection pool → "Socket is not connected" on rapid reconnects.
- **The token is short-lived and fetched per session** via the proxy; the real key never ships. The `Authorization` header path exists but is unused when `token` is in the query.
- **Three "final" deadlines stack** (1.4s grace, provider fallback, 2.4s manager default). Deliver final exactly once (`hasDeliveredFinalTranscript` guard) or you double-submit.
- **OpenAI provider is NOT realtime** — it accumulates buffers (PCM16 → WAV) and POSTs once to `https://api.openai.com/v1/audio/transcriptions` (multipart: model, language=en, response_format=json, optional prompt). Hence its 8s fallback. Don't expect partials from it.
- **Apple provider** feeds buffers to `SFSpeechAudioBufferRecognitionRequest` (`shouldReportPartialResults=true`, `taskHint=.dictation`, on-device when supported); `requestFinalTranscript()` calls `endAudio()`; needs speech-recognition permission.
- **`installTap` uses native input format**, not 16kHz — all resampling happens inside the provider's converter. Removing/installing the tap on every session is required (`removeTap(onBus:0)` first).

## Origin (reference only)
clicky `leanring-buddy/` (repo dir is misspelled): `GlobalPushToTalkShortcutMonitor.swift`, `BuddyDictationManager.swift`, `BuddyTranscriptionProvider.swift`, `AssemblyAIStreamingTranscriptionProvider.swift`, `BuddyAudioConversionSupport.swift`, `AppleSpeechTranscriptionProvider.swift`, `OpenAIAudioTranscriptionProvider.swift`. Source: https://github.com/farzaa/clicky. Verbatim/near-verbatim as of distillation; assume upstream may disappear.
