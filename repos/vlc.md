# vlc

**Source URL:** https://code.videolan.org/videolan/vlc  
**Mirror:** https://github.com/videolan/vlc  
**Product:** VLC media player — a free, open-source, cross-platform multimedia player and streaming server.  
**Stack:** C (60%), C++ (19%), Objective-C (9%), QML (4%). License: GPLv2 (app) + LGPLv3 (libVLC).  
**Date distilled:** 2026-06-19  

## What it is

VLC is a multimedia player and framework built almost entirely from swappable runtime modules (plugins). It plays virtually every audio/video format, streams over every protocol, and runs on Windows, macOS, Linux, Android, iOS, and more. libVLC is the embeddable LGPL engine at its core.

## Features distilled

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Capability-Based Module System | plugin-architecture | [study](../features/plugin-architecture/study/capability-module-system--from-vlc.md) | [build](../features/plugin-architecture/build/capability-module-system--from-vlc.md) |
| Media Pipeline | media-processing | [study](../features/media-processing/study/media-pipeline--from-vlc.md) | [build](../features/media-processing/build/media-pipeline--from-vlc.md) |
| libVLC Embeddable Engine | media-processing | [study](../features/media-processing/study/libvlc-embeddable-engine--from-vlc.md) | [build](../features/media-processing/build/libvlc-embeddable-engine--from-vlc.md) |
| Stream Output & Transcoding | streaming | [study](../features/streaming/study/stream-output-transcoding--from-vlc.md) | [build](../features/streaming/build/stream-output-transcoding--from-vlc.md) |

## Key architectural insights

- **Everything is a module.** VLC's core is tiny. Every codec, output, interface, and protocol is a `(capability_string, priority_int, activate_fn, deactivate_fn)` plugin discovered and selected at runtime. This is the design decision that lets one codebase support hundreds of platforms.
- **libVLC = thin LGPL wrapper.** The same engine that runs VLC's Qt UI is exposed as a C library any app can embed. The embedding API is stateful (instance → media → player), event-driven, and thread-aware.
- **Stream output = in-process broadcast server.** VLC can transcode and re-stream any input to any output via a declarative chain string (`#transcode{vcodec=h264}:http{dst=:8080/}`) without a separate streaming server.
