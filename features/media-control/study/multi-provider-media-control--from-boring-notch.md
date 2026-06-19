# Multi-Provider Media / Now-Playing Control — from [boring.notch](https://github.com/TheBoredTeam/boring.notch)

> Domain: [[_domain]] · Source: https://github.com/TheBoredTeam/boring.notch · NotebookLM: <add link>

## What it does
It shows and controls whatever music is playing — title, artist, artwork, progress, play/pause/next/seek/shuffle/repeat/volume/favorite — no matter *which* app is playing it: Apple Music, Spotify, YouTube Music, or "whatever the system says is playing." Every source is hidden behind one common interface, so the rest of the app (and its UI) never has to care who the provider is.

## Why it exists
There's no single macOS API that cleanly controls every music app. Apple Music and Spotify speak AppleScript; the system's global "now playing" lives in a *private* framework (MediaRemote); YouTube Music runs in a separate desktop app with its own local web API. Each is a different world with different capabilities (Spotify can't do "repeat one," not everything exposes volume). The job-to-be-done is "unify all of them behind one protocol, pick the active one, and stream a single consistent now-playing state to the UI." It's the adapter pattern applied to a genuinely messy integration surface.

## How it actually works
- **One protocol.** `MediaControllerProtocol` defines the common surface: a `playbackStatePublisher` (a Combine stream of `PlaybackState`), capability flags (`supportsVolumeControl`, `supportsFavorite`), and async commands (`play/pause/togglePlay/next/previous/seek/toggleShuffle/toggleRepeat/setVolume/setFavorite`), plus `isActive()` and `updatePlaybackInfo()`.
- **Four adapters, four mechanisms:**
  - **Apple Music** and **Spotify** — listen to each app's `DistributedNotificationCenter` notification (e.g. `com.apple.Music.playerInfo`), then run an AppleScript query that returns the full state as a list; commands are `tell application "Music" to …` one-liners. (Spotify duration is in ms; its repeat is boolean-only, so "repeat one" can't be represented.)
  - **System NowPlaying** — reads the *private* MediaRemote framework. State is streamed as newline-delimited JSON from a `perl` subprocess that loads a bundled `MediaRemoteAdapter.framework`; commands are sent by calling private `MRMediaRemoteSendCommand` (and friends) resolved directly from `MediaRemote.framework`.
  - **YouTube Music** — talks to the YouTube Music *Desktop* app's local API at `http://localhost:26538`: a Bearer-token auth handshake, a WebSocket for live updates (with a 2-second polling fallback and exponential-backoff reconnect), and `POST /play|/pause|/next|/seek-to|…` for commands.
- **One orchestrator.** `MusicManager` (singleton) reads the user's chosen provider, instantiates that adapter, subscribes to its `playbackStatePublisher`, and projects the incoming `PlaybackState` into `@Published` properties the SwiftUI views bind to. Changing the preference posts a notification and `MusicManager` swaps the controller live. A startup `MediaChecker` probes whether the private NowPlaying path still works on this macOS version; if not, it silently falls back to Apple Music.

## The non-obvious parts
- **The Perl bridge is the wildest bit.** To read the private MediaRemote "now playing" stream, the app shells out to `/usr/bin/perl` running `mediaremote-adapter.pl`, which uses Perl's built-in `DynaLoader` to `dlopen` a bundled framework and turn a raw C function pointer into a callable Perl sub (`dl_install_xsub`) — no compiled shim binary needed, architecture-independent. Parameters are passed via *environment variables* because the C symbols aren't standard cdecl functions. It exists because the private API needs to run in a process with the right entitlements, and Perl is a zero-compile way to load and call it.
- **Two different private-framework entry points.** *Reading* state goes through the bundled `MediaRemoteAdapter.framework` via the Perl subprocess; *sending* commands goes through `MediaRemote.framework` loaded directly in-process (`CFBundleGetFunctionPointerForName` + `unsafeBitCast`). Two halves of the same private API, reached two different ways.
- **A diff protocol for the now-playing stream.** The JSON stream sends `"diff": true` partial updates; the handler merges only changed fields and *dead-reckons* elapsed time (adds `playbackRate × elapsed`) instead of needing a position tick every frame.
- **Capabilities are honest about limits.** Spotify maps repeat to only `.off`/`.all` (no "one"); NowPlaying can't set per-app volume so it *falls back to AppleScript* against whichever bundle id is currently playing; favorite is Apple-Music-only. The protocol exposes `supports*` flags so the UI can hide what a provider can't do.
- **`NowPlayingController.isActive()` is always `true`** — it represents "the system," which is always playing *something* (or nothing); the `bundleIdentifier` in the state says which app it actually is.
- **YouTube Music degrades gracefully.** WebSocket preferred; if it fails, 2-second polling with reconnect backoff 1s→60s.
- **`PlaybackState` equality deliberately ignores `lastUpdated`, `playbackRate`, and `volume`** so trivial ticks don't spam UI updates.

## Related
- [[notch-shaped-window--from-boring-notch]] — the window this music UI lives in.
- [[system-hud-replacement--from-boring-notch]] — sibling macOS-integration feature (volume HUD overlaps with media volume).
- See also: [[email-provider-abstraction--from-inbox-zero]], [[whatsapp-provider-adapter--from-whatsapp-agentkit]] — the same provider-abstraction pattern in other domains.
