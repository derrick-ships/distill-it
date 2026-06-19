# Media Pipeline (build spec) — distilled from vlc

## Summary

A multi-stage media processing pipeline: Access (bytes from source) → Demux (container parsing, packet extraction) → Decoder (compressed → raw frames) → Output (render/playback). Each stage is a swappable module selected at runtime. An input thread drives the main loop. All stages run concurrently with queues between them.

## Core logic (inlined)

**MRL parsing:**
```c
// Input: "http://host/path.ts"
// Output:
struct mrl_parts {
    char *access;   // "http"
    char *demux;    // "" (inferred from content)
    char *path;     // "host/path.ts"
    char *anchor;   // "" (fragment after #)
};
// Done by vlc_UrlParse() + input_SplitMRL()
```

**Pipeline assembly:**
```
InputSourceInit(source, mrl_parts):
    stream = access_New(access_module_name, path)   // "http" -> HTTP module
    stream = stream_FilterAutoNew(stream)            // attach any auto-filters
    stream = InputStreamHandleAnchor(stream, anchor) // handle #fragment
    demux  = demux_NewAdvanced(stream, demux_hint)  // auto-detect container
    demux  = demux_FilterChainNew(demux)            // optional demux filters
```

**Demux → decoder fan-out:**
```
MainLoop():
    while not stopped:
        MainLoopDemux():
            data = demux.demux()       // returns block_t packets
            for each elementary stream in data:
                es_out.send(es, block)  // routes to correct decoder queue

// Each decoder runs in its own thread:
DecoderThread(es):
    while not flushed:
        block = DecoderQueue.pop()
        frames = decode(block)         // codec-specific
        for frame in frames:
            vout.put_picture(frame)    // or aout.play(pcm_data)
```

**Input thread control loop:**
```c
// Handles user commands:
switch(command):
    case INPUT_CONTROL_SET_POSITION:
        demux.control(DEMUX_SET_POSITION, pos)
    case INPUT_CONTROL_SET_PAUSE_STATE:
        es_out_Control(es_out, ES_OUT_SET_PAUSE_STATE, paused)
    case INPUT_CONTROL_SET_RATE:
        demux.control(DEMUX_SET_SPEED, rate * DEFAULT_PTS_DELAY)
```

**Timing model:**
```
PTS  = Presentation Timestamp (when to display this frame)
DTS  = Decode Timestamp (when to decode; matters for B-frames)
PCR  = Program Clock Reference (master clock in MPEG-TS)

VLC's clock: vlc_clock_t tracks master/slave relationship.
Video output delays display until PTS matches real time.
Audio output is the clock master by default.
```

## Data contracts

```c
// Core data unit: block_t (compressed packet)
struct block_t {
    uint8_t    *p_buffer;      // data bytes
    size_t      i_buffer;      // byte count
    vlc_tick_t  i_pts;         // presentation timestamp (vlc_tick_t = microseconds)
    vlc_tick_t  i_dts;         // decode timestamp
    vlc_tick_t  i_length;      // duration
    uint32_t    i_flags;        // BLOCK_FLAG_KEYFRAME, BLOCK_FLAG_DISCONTINUITY, ...
    block_t    *p_next;         // chained blocks
};

// Decoded video frame: picture_t
struct picture_t {
    plane_t     p[PICTURE_PLANE_MAX];  // Y/U/V or R/G/B planes
    vlc_tick_t  date;           // display PTS
    bool        b_force;        // force display regardless of clock
    // pixel format, width, height in p_fmt
};

// Elementary stream descriptor: es_format_t
struct es_format_t {
    int          i_cat;         // VIDEO_ES, AUDIO_ES, SPU_ES
    vlc_fourcc_t i_codec;       // codec identifier e.g. VLC_CODEC_H264
    video_format_t video;       // width, height, frame_rate, pixel_format
    audio_format_t audio;       // sample_rate, channels, bit_depth
};
```

## Dependencies & assumptions

**Access modules need:**
- Network socket API (HTTP, RTSP) or file I/O.
- Ability to report byte position, length, and whether seeking is supported.
- Produce `stream_t` (sequential byte source with optional seek).

**Demux modules need:**
- Container format knowledge (MP4 atoms, MKV EBML, MPEG-TS tables).
- Ability to emit `block_t` per elementary stream with correct PTS/DTS.
- Implement `DEMUX_GET_POSITION`, `DEMUX_SET_POSITION` controls.

**Decoder modules need:**
- Codec library (FFmpeg, platform SDK, or software implementation).
- Accept `block_t`, emit `picture_t` (video) or PCM blocks (audio).
- Handle `BLOCK_FLAG_DISCONTINUITY` for seeking.

**Output modules need:**
- OS-level audio/video API.
- Accept framed picture/PCM data with timestamps; handle clock sync.

## To port this, you need:

- [ ] A stream abstraction (`read(buf, len)`, `seek(pos)`, `control(...)`) as the pipeline connector.
- [ ] A packet type (`block_t`) carrying bytes + timestamps + flags.
- [ ] An elementary-stream router that sends decoded packets to the right decoder.
- [ ] Per-decoder thread (queue-based) so decode runs independently of demux speed.
- [ ] A timing/clock system: master clock + PTS-based gate before rendering.
- [ ] A control queue for the input thread: seek, pause, rate, stop.
- [ ] Timeshift buffer (optional): disk-backed queue between demux and decoders for DVR.

## Gotchas

**PTS discontinuities.** When the user seeks, decoders must be flushed (`BLOCK_FLAG_DISCONTINUITY` signals this). Leftover frames in decoder queues must be discarded or they display at the wrong time.

**Audio as master clock.** If video is the master, small audio gaps cause jitter. VLC defaults to audio as clock master because the ear detects drift more acutely. Your implementation should do the same.

**B-frames.** MPEG-2 and H.264/5 use B-frames where DTS ≠ PTS. A decoder needs to buffer and reorder frames before display. Many codec libraries (FFmpeg) do this internally; if using raw APIs you must handle it.

**Seeking in unseekable streams.** Live broadcasts (HTTP radio, RTSP cameras) have no seeking. The demux module reports `DEMUX_CAN_SEEK = false`. Your control loop must check this before forwarding seek commands.

**Subtitle synchronization.** SPU/subtitle decoders run on a separate ES. They must track the same clock as video output. If video is paused, subtitle display must also pause — route through the same master clock.

**Memory pressure.** Compressed packets (`block_t`) and decoded frames (`picture_t`) are both large. VLC uses reference-counted picture pools so the display doesn't have to copy frames — it retains a reference until display. Build your own picture pool or use the GPU texture lifecycle to avoid copies.

## Origin (reference only)

- Repo: https://code.videolan.org/videolan/vlc (mirror: https://github.com/videolan/vlc)
- `src/input/input.c` — `input_Start()`, `Init()`, `MainLoop()`, `MainLoopDemux()`
- `src/input/access.c` — access module loading
- `src/input/demux.c` — `InputDemuxNew()`, `demux_FilterChainNew()`
- `src/input/decoder.c` — `DecoderThread()`, decoder queue management
- `src/video_output/video_output.c` — vout pipeline and clock gating
