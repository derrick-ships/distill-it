# Stream Output & Transcoding (build spec) — distilled from vlc

## Summary

A chained stream processing pipeline that takes decoded media (or re-encoded media) and routes it to one or more outputs: file, HTTP, RTP/UDP multicast, or another encoder. The chain is specified as a string and assembled at runtime from modules. The transcode stage decodes incoming packets, applies filters, re-encodes to a target codec/bitrate, and passes the result downstream. Enables live transcoding, re-streaming, format conversion, and simultaneous multi-output delivery.

## Core logic (inlined)

**Stream output chain string format:**
```
#<module1>{param=val,...}:<module2>{...}:...

Examples:
#transcode{vcodec=h264,vb=800,scale=0.5,acodec=mp3,ab=128}:http{mux=ts,dst=:8080/}
#duplicate{dst=#transcode{vcodec=h264,vb=1500}:rtp{dst=192.168.1.5,port=5004},dst=#std{access=file,mux=mp4,dst=/recordings/out.mp4}}
#transcode{vcodec=copy,acodec=copy}:std{access=file,mux=mkv,dst=/out.mkv}
```

**How VLC assembles and runs the chain:**
```c
// 1. Parse chain string into linked list of sout modules:
sout_instance = sout_NewInstance(p_input, "#transcode{...}:http{...}")

// 2. For each module in chain, module_need() loads it:
sout_stream_t *chain = sout_StreamChainNew(sout, "transcode", cfg, next_module)

// 3. Incoming compressed packets arrive via:
sout_stream_id = sout_stream->pf_add(sout_stream, &es_format)  // announce a stream
sout_stream->pf_send(sout_stream, stream_id, block)             // send a block

// 4. Transcode module's pf_send (simplified):
transcode_pf_send(sout, stream_id, block):
    raw_frames = decoder_Decode(decoder_ctx, block)
    filtered_frames = filter_chain_Run(filter_chain, raw_frames)
    encoded_blocks = encoder_Encode(encoder_ctx, filtered_frames)
    sout_next->pf_send(sout_next, stream_id, encoded_blocks)
```

**Transcode module parameters:**
```
vcodec=<fourcc>    Target video codec: h264, h265, mp2v, theora, copy
vb=<kbps>          Video bitrate in kbps (e.g., vb=1500)
width=<px>         Output width (or 0 for auto)
height=<px>        Output height (or 0 for auto)
scale=<float>      Scale factor (e.g., scale=0.5 for half resolution)
fps=<n/d>          Frame rate (e.g., fps=30/1)
deinterlace        Enable deinterlace filter
vfilter=<name>     Apply a video filter module

acodec=<fourcc>    Target audio codec: mp3, aac, vorb, flac, copy
ab=<kbps>          Audio bitrate in kbps
samplerate=<hz>    Sample rate (e.g., 44100, 48000)
channels=<n>       Number of channels (1=mono, 2=stereo, 6=5.1)
afilter=<name>     Apply an audio filter module

threads=<n>        Encoder thread count
```

**Output module parameters:**
```
std{access=<type>,mux=<type>,dst=<location>}
  access: file, http, rtp, udp, sftp
  mux: ts, mp4, ogg, mkv, avi, webm, raw
  dst: /path/to/file.mp4  OR  :8080/  OR  192.168.1.5:5004

http{dst=:8080/,mux=ts}          HTTP TS stream on port 8080
rtp{dst=192.168.1.255,port=5004} RTP multicast
```

**VLM control (programmatic, via libVLC):**
```c
libvlc_instance_t *inst = libvlc_new(0, NULL);

// Create a broadcast
libvlc_vlm_add_broadcast(inst,
    "my_channel",                       // name
    "file:///input/source.mp4",         // input MRL
    "#transcode{vcodec=h264,vb=800}:http{dst=:8080/,mux=ts}", // sout
    0, NULL,                            // no options
    VLC_TRUE,                           // enabled
    VLC_FALSE);                         // loop

libvlc_vlm_play_media(inst, "my_channel");
// ... streaming ...
libvlc_vlm_stop_media(inst, "my_channel");
libvlc_vlm_del_media(inst, "my_channel");
libvlc_release(inst);
```

**VLM text protocol (socket control):**
```
new webcam broadcast enabled loop
setup webcam input v4l2:///dev/video0
setup webcam output #transcode{vcodec=h264,vb=800}:http{mux=ts,dst=:8080/}
control webcam play
control webcam stop
del webcam
```

## Data contracts

```c
// stream_out module interface:
struct sout_stream_t {
    sout_stream_sys_t *p_sys;       // module private data
    int  (*pf_add)(sout_stream_t *, const es_format_t *); // announce ES
    void (*pf_del)(sout_stream_t *, void *id);            // remove ES
    int  (*pf_send)(sout_stream_t *, void *id, block_t *); // send packet
    void (*pf_flush)(sout_stream_t *, void *id);          // flush
    sout_stream_t *p_next;  // next module in chain
};

// Encoder interface (video):
struct encoder_t {
    es_format_t    fmt_in;    // raw input format (e.g. I420 YUV)
    es_format_t    fmt_out;   // encoded output format (e.g. H264)
    block_t *(*pf_encode_video)(encoder_t *, picture_t *);
    block_t *(*pf_encode_audio)(encoder_t *, block_t *);
};

// Block with timestamps (same as pipeline):
struct block_t {
    uint8_t    *p_buffer;
    size_t      i_buffer;
    vlc_tick_t  i_pts;    // microseconds since epoch (VLC epoch)
    vlc_tick_t  i_dts;
    vlc_tick_t  i_length;
    uint32_t    i_flags;  // BLOCK_FLAG_KEYFRAME, etc.
};
```

## Dependencies & assumptions

- VLC (or libVLC) installed with codec/mux modules.
- For hardware encoding: NVENC (NVIDIA GPU, `--sout-transcode-vcodec=h265_nvenc`), VideoToolbox (macOS), VAAPI (Linux).
- For HTTP output: VLC acts as HTTP server; no external web server needed.
- For RTP multicast: network must support UDP multicast routing.
- VLM requires the `--extraintf=telnet` or RC interface module loaded.

## To port this, you need:

- [ ] A chain assembly function that parses a DSL string into ordered module instances.
- [ ] A `sout_stream` interface: `add(es_format)` to register a track, `send(id, block)` to push a packet.
- [ ] A transcode module that holds {decoder, filter chain, encoder} per track; pf_send drives the decode→filter→encode pipeline per block.
- [ ] An HTTP mux+output module: accept encoded `block_t`, mux into container, chunk-serve over HTTP.
- [ ] PCR tracking: when re-encoding, recalculate and insert PCR fields in MPEG-TS at correct intervals (~100ms).
- [ ] A duplicate module that fans `pf_send` to N next-chains, each with independent state.

## Gotchas

**Chain string is fragile across VLC versions.** Module names and parameters changed between VLC 2.x, 3.x, and 4.x. Pin the VLC version if your application generates chain strings.

**`vcodec=copy` ≠ "no processing."** Even copy mode creates encoder/decoder wrapper structs, just with pass-through logic. It still involves the module system and can fail if the codec is unsupported by the target mux.

**Encoding latency adds sync risk.** Encoders buffer frames for B-frame lookahead (typically 8-16 frames for H.264). During this buffer fill, audio keeps flowing but video output is delayed. VLC compensates via PCR adjustment; naïve implementations will have A/V sync drift from the first frame.

**HTTP output has no authentication.** VLC's built-in HTTP module serves to anyone who connects. If you're using it for anything other than local testing, put nginx in front or filter at the network level.

**Stream output and playback are mutually exclusive by default.** When `--sout` is set, VLC enters stream_out mode and does NOT render locally. Use `#duplicate{dst=#display,dst=#transcode{...}}` to simultaneously play locally and stream.

**One VLM channel per libvlc instance.** While you can have multiple named broadcasts, they share one libvlc engine. High-bitrate transcoding of many streams in one instance will saturate CPU. For production multi-stream use, launch separate libvlc instances or use FFmpeg.

## Origin (reference only)

- Repo: https://code.videolan.org/videolan/vlc (mirror: https://github.com/videolan/vlc)
- `modules/stream_out/transcode/transcode.c` — the transcode module implementation
- `modules/stream_out/duplicate.c` — duplicate (fan-out) module
- `modules/stream_out/http.c` — HTTP output module
- `src/sout/sout.c` — chain assembly, `sout_NewInstance()`
- `lib/vlm.c` — `libvlc_vlm_*` implementations
- VLC streaming how-to: https://wiki.videolan.org/Documentation:Streaming_HowTo
