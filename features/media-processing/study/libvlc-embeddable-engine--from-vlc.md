# libVLC Embeddable Engine — from [vlc](https://code.videolan.org/videolan/vlc)

> Domain: [[media-processing]] · Source: https://code.videolan.org/videolan/vlc · NotebookLM:

## What it does

libVLC is the public C API that wraps VLC's entire multimedia engine in an embeddable library. Any application — a video security monitor, a custom music player, a game engine's cutscene system, a media kiosk — can call `libvlc_new()` to create an engine instance, give it a URL or file path, and get back a media player with full playback control. libVLC handles all the codec selection, buffering, clock management, and rendering described in the media pipeline feature. The embedding application only needs to provide a window handle for video and respond to events.

## Why it exists

VLC's full functionality is too valuable to lock inside VLC's own UI. Video production tools, surveillance systems, automotive infotainment, and consumer electronics all need to play arbitrary media — but they don't want to embed the full Qt VLC interface. libVLC solves this by exposing the engine under a clean LGPL license (so commercial products can use it without open-sourcing their own code) while keeping the module ecosystem and codec breadth intact. Language bindings exist for C++, Python, C#/.NET, Java/Android, Swift/iOS, and more.

## How it actually works

**Initialization.** `libvlc_new(argc, argv)` creates a VLC engine instance (`libvlc_instance_t`). The `argv` array lets you pass VLC command-line options — `--no-video`, `--aout=pulse`, `--network-caching=3000` — to configure the engine at startup. The function scans plugin directories, loads the module registry, and sets up internal threading.

**Media creation.** `libvlc_media_new_location(inst, "http://host/stream.mp4")` or `libvlc_media_new_path(inst, "/path/to/file.mkv")` creates a `libvlc_media_t` descriptor. No network activity happens yet — this is just an MRL object. You can attach options to it with `libvlc_media_add_option(media, ":start-time=30")`.

**Player creation.** `libvlc_media_player_new(inst)` creates a player. `libvlc_media_player_set_media(player, media)` associates them. The player is a `libvlc_media_player_t` that wraps a `vlc_player_t` internally and exposes a flat C API.

**Window attachment.** For video rendering, you give the player a native window handle before calling play:
```
libvlc_media_player_set_xwindow(player, xid)    // Linux/X11
libvlc_media_player_set_hwnd(player, hwnd)       // Windows
libvlc_media_player_set_nsobject(player, nsview) // macOS
```
VLC's vout module then renders directly into that window. Alternatively, `libvlc_video_set_callbacks()` provides raw pixel callbacks for custom rendering (software path only).

**Playback control.** `libvlc_media_player_play()` starts the pipeline. `libvlc_media_player_set_pause()`, `libvlc_media_player_set_position(0.5f)` (seek to 50%), `libvlc_media_player_set_rate(2.0f)` (2x speed), `libvlc_media_player_stop_async()` — all pass through to the underlying input thread control queue.

**Event system.** libVLC emits events for state changes: `libvlc_MediaPlayerPlaying`, `libvlc_MediaPlayerEndReached`, `libvlc_MediaPlayerEncounteredError`, `libvlc_MediaPlayerPositionChanged`. You subscribe via `libvlc_event_attach(event_mgr, event_type, callback, user_data)`. Events are delivered on an internal event thread, so callbacks must be thread-safe.

**Track management.** `libvlc_media_player_get_full_track_description()` returns all available audio, video, and subtitle tracks. `libvlc_media_player_select_track()` switches between them at runtime.

**Cleanup.** Release in reverse: `libvlc_media_player_release()`, `libvlc_media_release()`, `libvlc_release()`. All internal threads are stopped and modules unloaded.

## The non-obvious parts

**Versioning is tight.** libVLC's version is the same number as the VLC app version. libVLC 3.x and libVLC 4.x have incompatible APIs — the 4.x API was redesigned. Check which version your target platform ships.

**The event thread is not the UI thread.** State-change callbacks fire on libVLC's internal thread. All UI updates from them must be marshaled to the UI thread (Qt signals, GLib idle, GCD dispatch_async, etc.). Calling libVLC APIs directly from the event callback is allowed but can deadlock if the call needs the player's lock.

**No implicit media library.** libVLC plays one item at a time. Playlists are an app-layer concern (libVLC 4.x provides `libvlc_media_list_t` for a flat list, but queue logic is yours). This is by design: embedding apps have their own playlist models.

**Custom rendering is software-only.** `libvlc_video_set_callbacks()` gives you raw RGBA/YUV pixels, but it bypasses hardware-accelerated rendering. For GPU-accelerated output in an embedded context, use `libvlc_video_set_output_callbacks()` (libVLC 4.x) which supports OpenGL/D3D11 texture sharing.

**Module options control everything.** Almost every VLC feature is accessible as a module option string. If libVLC's typed API doesn't expose something, `libvlc_media_add_option(media, ":option=value")` usually does.

## Related

- [[media-pipeline--from-vlc]] (libVLC wraps this pipeline — understanding it explains why the API looks the way it does)
- [[capability-module-system--from-vlc]] (plugin selection still happens internally — libVLC is a thin wrapper over the same module machinery)
