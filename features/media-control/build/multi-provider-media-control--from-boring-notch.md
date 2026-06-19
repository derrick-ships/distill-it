# Multi-Provider Media / Now-Playing Control (build spec) — distilled from boring.notch

## Summary
A unified now-playing abstraction over Apple Music, Spotify, YouTube Music, and the system's private MediaRemote. One Combine-publishing protocol, four adapters (AppleScript; AppleScript; local HTTP+WebSocket; private MediaRemote via a Perl `dlopen` bridge), and a singleton manager that selects the active adapter from a user preference, subscribes to its state stream, and projects a single `PlaybackState` to SwiftUI. Capability flags express per-provider limits. macOS 14+, Swift/Combine.

## Core logic (inlined)

### The protocol (verbatim)
```swift
protocol MediaControllerProtocol: ObservableObject {
    var playbackStatePublisher: AnyPublisher<PlaybackState, Never> { get }
    var supportsVolumeControl: Bool { get }
    var supportsFavorite: Bool { get }
    func setFavorite(_ favorite: Bool) async
    func play() async
    func pause() async
    func seek(to time: Double) async
    func nextTrack() async
    func previousTrack() async
    func togglePlay() async
    func toggleShuffle() async
    func toggleRepeat() async
    func setVolume(_ level: Double) async
    func isActive() -> Bool
    func updatePlaybackInfo() async
}
```

### The shared state type
```swift
struct PlaybackState {            // Equatable EXCLUDES lastUpdated, playbackRate, volume
    var bundleIdentifier: String  // "com.apple.Music" | "com.spotify.client" | ...
    var isPlaying: Bool
    var title: String; var artist: String; var album: String
    var currentTime: Double; var duration: Double   // seconds
    var playbackRate: Double      // default 1.0
    var isShuffled: Bool
    var repeatMode: RepeatMode    // .off=1 / .one=2 / .all=3
    var lastUpdated: Date
    var artwork: Data?            // raw image bytes
    var volume: Double            // 0.0–1.0
    var isFavorite: Bool
}
enum RepeatMode: Int, Codable { case off = 1, one = 2, all = 3 }
```

### Adapter mechanisms
**AppleMusic / Spotify (AppleScript + DistributedNotificationCenter):**
- Observe `com.apple.Music.playerInfo` / `com.spotify.client.PlaybackStateChanged`.
- On notify, run one AppleScript returning a list: Music → `{isPlaying,title,artist,album,currentTime,duration,shuffle,repeat,volume,artworkData,favorited}` (artwork = raw bytes); Spotify → `{isPlaying,name,artist,album,position,duration,shuffling,repeating,volume,artworkUrl}` (duration in **ms**, artwork = URL fetched+cached by URL).
- Commands: `tell application "Music"/"Spotify" to <verb>`; seek = `set player position to <s>`. Spotify repeat is boolean → maps to `.off`/`.all` only. `isActive()` = `NSWorkspace.runningApplications` contains the bundle id.

**NowPlaying (private MediaRemote — system-wide):**
- READ: `Process` runs `/usr/bin/perl mediaremote-adapter.pl <frameworkPath> stream`; the script `dlopen`s the bundled `MediaRemoteAdapter.framework` and streams newline-delimited JSON. Swift reads via an actor over a `Pipe`, decodes `{payload, diff?}`; when `diff==true` merge only present fields; dead-reckon `currentTime += playbackRate * Δt` while playing.
- COMMANDS: resolve symbols from `MediaRemote.framework` via `CFBundleGetFunctionPointerForName` + `unsafeBitCast`: `MRMediaRemoteSendCommand(cmd,info)` with `play=0,pause=1,togglePlay=2,next=4,prev=5`; `MRMediaRemoteSetElapsedTime(Double)`; `MRMediaRemoteSetShuffleMode(Int)`; `MRMediaRemoteSetRepeatMode(Int)`.
- VOLUME: not supported → AppleScript fallback against the currently-playing bundle id. FAVORITE: AppleScript against Apple Music. `isActive()` → always `true`.

**YouTube Music (YTM Desktop app local API @ http://localhost:26538):**
- AUTH: actor POSTs `/auth/boringNotch`, caches bearer token, re-fetches on 401/403.
- READ: WebSocket `ws://localhost:26538/api/v1/ws` (Bearer); messages keyed by `type`: `PLAYER_INFO|VIDEO_CHANGED|PLAYER_STATE_CHANGED` (full), `POSITION_CHANGED`, `REPEAT_CHANGED`, `SHUFFLE_CHANGED`, `VOLUME_CHANGED` (0–100→0–1). Fallback: `Timer` polling `GET /api/v1/song` every 2s; WS reconnect backoff 1s→60s.
- COMMANDS: `POST /play|/pause|/toggle-play|/next|/previous|/seek-to {seconds}|/volume {volume:0-100}|/shuffle|/switch-repeat|/like`. Lifecycle tracked via `NSWorkspace.didLaunch/didTerminateApplicationNotification`.

### The Perl bridge — `mediaremote-adapter.pl`
```
argv: FRAMEWORK_PATH, FUNCTION
DynaLoader::dl_load_file($framework, 0)              # == dlopen
$sym = DynaLoader::dl_find_symbol($lib, $func)        # == dlsym
DynaLoader::dl_install_xsub("main::stream", $sym)     # raw C ptr -> callable Perl sub
&{"main::stream"}()                                   # invoke
# params passed via env vars MEDIAREMOTEADAPTER_PARAM_<func>_<i>_<name> / _OPTION_<name>
# funcs: adapter_stream(_env) (continuous JSON), adapter_get(_env) (one-shot),
#        adapter_send_env, adapter_seek_env, adapter_shuffle_env, adapter_repeat_env, adapter_speed_env,
#        adapter_test (exit 1 => deprecated/non-functional)
```

### Orchestration — `MusicManager` (singleton, ObservableObject)
```
init: MediaChecker.checkDeprecationStatus() async; then setActiveControllerBasedOnPreference()
preference = Defaults[.mediaController]  // enum: .nowPlaying/.appleMusic/.spotify/.youtubeMusic
if isNowPlayingDeprecated && pref == .nowPlaying: substitute .appleMusic
createController(for:): cancel previous cancellables; instantiate adapter; subscribe to
   playbackStatePublisher on DispatchQueue.main -> updateFromPlaybackState (@MainActor) ->
   project into @Published (songTitle, artistName, albumArt, isPlaying, elapsedTime, songDuration,
   isShuffled, repeatMode, volume, isFavoriteTrack, canFavoriteTrack, bundleIdentifier, ...)
observe Notification.Name.mediaControllerChanged -> swap controller live
```
`MediaChecker` runs `adapter_test`; exit code 1 → `isNowPlayingDeprecated = true`.

## Data contracts
- `PlaybackState` (above) is the single boundary type. Commands are async fire-and-forget; `isActive()` sync.
- Provider preference: `Defaults[.mediaController]` (`MediaControllerType` enum: `.nowPlaying/.appleMusic/.spotify/.youtubeMusic`).
- YTM API: base `http://localhost:26538`, auth `POST /auth/boringNotch`→bearer, WS `/api/v1/ws`, song `GET /api/v1/song`.

## Dependencies & assumptions
- Public: AppKit `NSWorkspace`, `DistributedNotificationCenter`, Combine, `URLSessionWebSocketTask`, `Process`/`Pipe`, `/usr/bin/perl`.
- Private: `MediaRemote.framework` (command symbols, in-process) + a **bundled** `MediaRemoteAdapter.framework` (read stream, via Perl subprocess). These need the app's entitlements; the Perl subprocess pattern delegates them.
- External: an `AppleScriptHelper` (async osascript runner) and `ImageService` (async image fetch/cache) — not read here.
- YTM adapter requires the third-party YouTube Music Desktop app running locally.

## To port this, you need:
- [ ] A protocol with a state publisher + capability flags + async commands + `isActive()`.
- [ ] A single value type for now-playing state, with equality that ignores noisy fields (timestamps, rate, volume).
- [ ] One adapter per source; pick mechanism per source (scripting bridge / private framework / local API).
- [ ] A manager that selects the active adapter from a preference, subscribes to its stream on the main queue, projects to observable UI props, and hot-swaps on preference change.
- [ ] A capability/deprecation probe at startup with a safe fallback provider.
- [ ] (If using private MediaRemote) a way to call it from an entitled context — the Perl `DynaLoader` subprocess is one zero-compile option.

## Gotchas
- **Private MediaRemote is fragile** — Apple has deprecated/locked parts of it across versions; `adapter_test` exit code drives the fallback. Always have a non-private fallback (AppleScript).
- **Two private entry points** (read via bundled adapter framework + Perl; commands via MediaRemote in-process) — don't assume one path covers both.
- **Spotify can't "repeat one"** and duration is ms — normalize per adapter, not in the UI.
- **NowPlaying has no per-app volume** — falls back to AppleScript against the live bundle id.
- **Diff stream + dead-reckoning** — merge partial `diff` updates and interpolate elapsed time, or the progress bar stutters.
- **`isActive()` always-true for NowPlaying** — it's "the system"; use `bundleIdentifier` to know the real app.
- **YTM needs the desktop app + auth** — handle 401/403 token refresh and WS→polling degradation.
- **Run scripting/network off the main thread**, project results onto `@MainActor` — the manager does the publisher hop on `DispatchQueue.main`.

## Origin (reference only)
Repo: https://github.com/TheBoredTeam/boring.notch · Files (read verbatim): `MediaControllers/{MediaControllerProtocol,NowPlayingController,AppleMusicController,SpotifyController}.swift`, `MediaControllers/YouTube Music Controller/{YouTubeMusicController,YouTubeMusicNetworking,YouTubeMusicModels,YouTubeMusicAuthentication}.swift`, `managers/MusicManager.swift`, `models/PlaybackState.swift`, `helpers/MediaChecker.swift`, `mediaremote-adapter/mediaremote-adapter.pl`. GAPS: `AppleScriptHelper`, `ImageService`, `MediaControllerType` enum decl, and the bundled framework's internal MediaRemote call graph not read — verify symbol signatures before relying.
