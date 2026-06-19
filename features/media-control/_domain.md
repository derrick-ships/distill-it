# Domain: media-control

Patterns for reading and controlling media/now-playing playback across heterogeneous sources behind a single unified interface — the adapter pattern applied to music/media players with wildly different control surfaces.

## What this domain is about

Controlling "whatever is playing" is messy: each player exposes a different mechanism (AppleScript scripting bridges, private system frameworks, local web APIs) and a different capability set (some can't repeat-one, some can't report volume). This domain captures how to unify them — one protocol publishing a single normalized playback-state value, one adapter per source translating that source's reality, capability flags for honest per-source limits, and a manager that selects the active source and hot-swaps it.

## Core patterns

- **Unified playback protocol + state value**: a stream of one normalized `PlaybackState`; equality ignores noisy fields (timestamps, rate) to avoid UI churn
- **Per-source adapters**: scripting bridge (AppleScript), private framework (MediaRemote), or local HTTP/WebSocket (a companion desktop app) — each owns its quirks
- **Capability flags + graceful degradation**: `supports*` flags, deprecation probes with safe fallbacks, WebSocket→polling fallback
- **Entitled private-API access**: reach private system playback APIs from an appropriately-entitled context (e.g. a `dlopen` subprocess)

## Features in this domain

- [[multi-provider-media-control--from-boring-notch]] — `MediaControllerProtocol` + Apple Music/Spotify (AppleScript), YouTube Music (local HTTP+WebSocket), and system NowPlaying (private MediaRemote via a Perl `DynaLoader` bridge); a `MusicManager` selects and hot-swaps the active adapter and projects one `PlaybackState` to SwiftUI
