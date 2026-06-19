# libVLC Embeddable Engine (build spec) — distilled from vlc

## Summary

Embed the full VLC multimedia engine in any C/C++ (or language-binding) application. The API is: create instance → create media → create player → attach window → play → respond to events → release. Hardware-accelerated decoding and rendering, codec breadth, and network streaming all come for free. LGPL license allows commercial embedding.

## Core logic (inlined)

**Minimal playback (C):**
```c
#include <vlc/vlc.h>

// 1. Create engine instance
const char *vlc_args[] = { "--no-xlib" };  // suppress xlib init (headless)
libvlc_instance_t *inst = libvlc_new(1, vlc_args);

// 2. Create media
libvlc_media_t *media = libvlc_media_new_location(inst, "file:///path/to/video.mp4");
// or: libvlc_media_new_path(inst, "/path/to/video.mp4");
libvlc_media_add_option(media, ":start-time=10");  // start 10s in

// 3. Create player and bind media
libvlc_media_player_t *player = libvlc_media_player_new(inst);
libvlc_media_player_set_media(player, media);
libvlc_media_release(media);  // player holds its own ref

// 4. Attach native window (before play)
libvlc_media_player_set_xwindow(player, x11_window_id);  // Linux
// libvlc_media_player_set_hwnd(player, hwnd);            // Windows
// libvlc_media_player_set_nsobject(player, nsview);      // macOS

// 5. Play
libvlc_media_player_play(player);

// ... do other stuff, wait for events ...

// 6. Cleanup
libvlc_media_player_stop_async(player);
// Wait for stopped event, then:
libvlc_media_player_release(player);
libvlc_release(inst);
```

**Event subscription:**
```c
libvlc_event_manager_t *em = libvlc_media_player_event_manager(player);

libvlc_event_attach(em, libvlc_MediaPlayerEndReached,
    my_end_callback, user_data);
libvlc_event_attach(em, libvlc_MediaPlayerEncounteredError,
    my_error_callback, user_data);
libvlc_event_attach(em, libvlc_MediaPlayerPositionChanged,
    my_position_callback, user_data);  // fires frequently

// Callback signature:
void my_end_callback(const libvlc_event_t *event, void *user_data) {
    // IMPORTANT: this runs on libVLC's internal event thread
    // Marshal to UI thread before touching UI
    AppEvent *e = new AppEvent(APP_PLAYBACK_ENDED);
    PostToUIThread(e);
}
```

**Playback controls:**
```c
libvlc_media_player_set_pause(player, 1);           // pause
libvlc_media_player_set_pause(player, 0);           // resume
libvlc_media_player_set_position(player, 0.5f);     // seek to 50%
libvlc_media_player_set_rate(player, 2.0f);         // 2x speed
libvlc_media_player_set_time(player, 30000);        // seek to 30 seconds (ms)
float pos = libvlc_media_player_get_position(player); // 0.0-1.0
libvlc_time_t ms = libvlc_media_player_get_time(player);
libvlc_time_t total = libvlc_media_player_get_length(player);
```

**Track management:**
```c
// Get all tracks (libVLC 4.x API):
libvlc_media_tracklist_t *tracks =
    libvlc_media_player_get_tracklist(player, libvlc_track_audio, false);
size_t count = libvlc_media_tracklist_count(tracks);
for (size_t i = 0; i < count; i++) {
    const libvlc_media_track_t *t = libvlc_media_tracklist_at(tracks, i);
    printf("track %zu: lang=%s\n", i, t->psz_language);
}
// Select a track:
libvlc_media_player_select_track(player, track);
libvlc_media_tracklist_delete(tracks);
```

**Custom pixel callback (software rendering):**
```c
// Called to allocate pixel buffer:
void *lock_cb(void *opaque, void **planes) {
    *planes = opaque;  // pre-allocated pixel buffer
    return NULL;
}
void unlock_cb(void *opaque, void *picture, void *const *planes) { }
void display_cb(void *opaque, void *picture) {
    // upload *opaque buffer to GPU / display
}
libvlc_video_set_callbacks(player, lock_cb, unlock_cb, display_cb, pixel_buf);
libvlc_video_set_format(player, "RV32", width, height, width * 4);
```

## Data contracts

```c
// State machine (libvlc_state_t):
libvlc_NothingSpecial = 0   // initial, no media
libvlc_Opening              // opening media
libvlc_Buffering            // network buffering
libvlc_Playing              // actively playing
libvlc_Paused               // paused
libvlc_Stopped              // stopped
libvlc_Ended                // reached end
libvlc_Error                // unrecoverable error

// Event types fired on state transitions:
libvlc_MediaPlayerOpening
libvlc_MediaPlayerBuffering     // event.media_player_buffering.new_cache (0-100%)
libvlc_MediaPlayerPlaying
libvlc_MediaPlayerPaused
libvlc_MediaPlayerStopped
libvlc_MediaPlayerEndReached
libvlc_MediaPlayerEncounteredError

// Position events:
libvlc_MediaPlayerPositionChanged  // event.media_player_position_changed.new_position
libvlc_MediaPlayerTimeChanged      // event.media_player_time_changed.new_time (ms)
libvlc_MediaPlayerLengthChanged    // after media opens and duration is known
```

## Dependencies & assumptions

- **libvlc.so** / **libvlc.dll** (ships with VLC or can be linked via vcpkg/homebrew/conan).
- Headers: `vlc/vlc.h` (public API), `vlc/libvlc_media.h`, `vlc/libvlc_media_player.h`.
- A native window handle at video attachment time (X11 XID, Win32 HWND, macOS NSView pointer).
- Plugin directory at runtime (defaults to system VLC install; can override with `--plugin-path=...`).
- For static embedding: link all needed modules as `.a` files and call `vlc_entry__<name>` functions to pre-register them.

**Language bindings (use these instead of calling libvlc C API directly):**
```
C++:    libvlcpp       (header-only, modern C++)
Python: python-vlc     (ctypes-based, auto-generated from headers)
C#/.NET: LibVLCSharp   (cross-platform, Xamarin/MAUI support)
Java:   libvlcjni      (Android only, embedded in VLC-Android)
Swift:  VLCKit         (iOS/tvOS/macOS, wraps Objective-C bindings)
```

## To port this, you need:

- [ ] libVLC installed or vendored (v3.x for broad compatibility, v4.x for modern GPU texture API).
- [ ] Determine target platforms; use appropriate window-attachment API per platform.
- [ ] UI-thread event marshaling: create a thread-safe channel (queue, pipe, signal) for libVLC callbacks.
- [ ] State machine in your app that mirrors libvlc_state_t to drive UI (play/pause button, progress bar).
- [ ] Handle `libvlc_MediaPlayerLengthChanged` to know when duration is valid (not at open time).
- [ ] For web/Electron: use libvlcpp + node-libvlc binding or CEFSubprocess with a native plugin.
- [ ] For GPU texture sharing (libVLC 4.x): implement `libvlc_video_output_cfg_t` + OpenGL/D3D11 setup callbacks.

## Gotchas

**Stop is async.** `libvlc_media_player_stop_async()` returns immediately. The player is not stopped until you receive `libvlc_MediaPlayerStopped`. Calling `libvlc_media_player_release()` before that can crash. Use the event to gate cleanup.

**Position before length.** `libvlc_media_player_get_length()` returns -1 until the media is fully opened and `libvlc_MediaPlayerLengthChanged` fires. Don't read it at play time.

**Multiple `libvlc_new()` calls.** You typically create one `libvlc_instance_t` per application, not one per player. Multiple instances are allowed but expensive (each scans plugins). Share one instance.

**Option string injection.** `libvlc_media_add_option(media, ":sout=#transcode{...}:file{...}")` invokes VLC's full stream output chain from the embedding app. This is powerful but the option strings are not stable across VLC major versions.

**Hardware acceleration is automatic.** You don't configure it. VLC's module system picks VideoToolbox/MediaCodec/VAAPI/NVDEC if available based on module priority. If you need to force software decode: `libvlc_media_add_option(media, ":codec=avcodec")`.

**Thread-unsafe API.** Most libvlc functions are NOT thread-safe. Call them from one thread (typically the UI thread) or add your own locking.

## Origin (reference only)

- Repo: https://code.videolan.org/videolan/vlc (mirror: https://github.com/videolan/vlc)
- `lib/media_player.c` — all `libvlc_media_player_*` implementations
- `lib/media.c` — `libvlc_media_*` implementations
- `lib/libvlc.c` — `libvlc_new()`, `libvlc_release()`
- Official docs: https://videolan.videolan.me/vlc/
- Samples: https://code.videolan.org/videolan/libvlc-samples
