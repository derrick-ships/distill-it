# Media Pipeline — from [vlc](https://code.videolan.org/videolan/vlc)

> Domain: [[media-processing]] · Source: https://code.videolan.org/videolan/vlc · NotebookLM:

## What it does

When you open a file or stream in VLC, a precise sequence of stages assembles itself to move data from its source to your speakers and screen. This pipeline — access → demux → decoder → output — is not wired at compile time. Each stage is a module selected at runtime based on what the input looks like. The result is a player that can handle an HTTP MPEG-TS stream, a local MKV file, a Blu-ray disc, and an RTSP camera feed all through the same code path, with each stage swapped out as needed.

## Why it exists

Media data comes in layers: a network protocol carries a container format which carries compressed tracks which must be decoded and rendered. Each layer is an independent concern with dozens of competing standards. By making each layer a swappable module, VLC can extend to new formats without touching the pipeline core. A new codec is a new decoder module. A new streaming protocol is a new access module. The pipeline acts as the stable spine that these modules plug into.

## How it actually works

**Step 1: MRL parsing.** VLC receives a Media Resource Locator like `http://host/path.ts` or `file:///home/user/movie.mkv`. The input system splits it into four parts: access method (`http`, `file`, `dvd`), demux hint (usually empty or inferred), path, and anchor. This split determines which modules to try.

**Step 2: Access module.** An `access` module handles raw byte delivery from the source. `module_need(…, "access", "http,any", …)` loads the HTTP module, which knows how to open a TCP connection, handle redirects, send Range headers for seeking, and deliver a byte stream. For files it's the filesystem module. For DVDs it's a libdvdnav-backed module. The access module produces a raw `stream_t` object.

**Step 3: Stream filters.** Optional filter modules attach to the stream before demuxing — for example, to handle HTTP chunked transfer encoding, to decrypt a stream (HLS AES-128), or to record the raw bytes to disk simultaneously with playback. These are chained automatically.

**Step 4: Demux module.** A `demux` module understands a container format. Given the byte stream, it separates it into elementary streams — one video track, one audio track, maybe subtitles. The MP4 demuxer knows the `moov`/`mdat` atom structure; the MKV demuxer knows EBML. As it parses, it emits `block_t` packets timestamped with PTS/DTS. The demux module also handles seeking by knowing where keyframes are.

**Step 5: ES output / decoders.** Each elementary stream goes to a decoder module. Video `block_t` packets (e.g., H.264 NAL units) go to a `video decoder` module (VideoToolbox on macOS, MediaCodec on Android, FFmpeg's avcodec everywhere else). Audio packets go to an `audio decoder`. Subtitle packets go to an SPU decoder. Each decoder runs in its own thread, consuming from a queue and producing raw frames.

**Step 6: Video output.** Decoded `picture_t` frames go to the video output subsystem. A `vout display` module renders them — OpenGL, Direct3D, Vulkan, or a software scaler to a window buffer. The display has its own thread to maintain frame timing independently of decoding speed.

**Step 7: Audio output.** Decoded PCM audio goes through the audio output chain. An `audio output` module delivers samples to PulseAudio, CoreAudio, WASAPI, etc. Resampling and channel remapping happen in filter modules that insert themselves between the decoder and the output.

**Main loop.** An input thread (`MainLoop`) drives the entire pipeline. It calls `MainLoopDemux()` which pulls data from the demux, hands it to decoders, and checks for control commands (seek, pause, rate change). Position/timing stats are collected each loop iteration. The loop exits when EOF is reached or the user stops playback.

**Cleanup.** Teardown is symmetric: decoders drain, video/audio outputs flush, demux closes, access closes. Slave inputs (external subtitle files) are torn down first.

## The non-obvious parts

**The timeshift layer.** Between the ES output and the decoders, VLC can insert a timeshift buffer (`input_EsOutTimeshiftNew`) — a disk-backed queue that lets you pause and rewind live streams without any change to the access module. The pipeline "sees" a timeshifted stream; the access module just keeps delivering.

**"access_demux" modules.** Some protocols know their own container (HLS, DASH, RTSP-SDP). These are access-demux hybrids that both deliver bytes and parse the container in one module, bypassing the normal two-step split.

**PCR forwarding in transcode.** When stream_out/transcode is in the chain (converting formats), it must forward the Program Clock Reference timestamps through the encode pipeline to avoid A/V sync drift. This is subtle — re-encoded frames have different timestamps than the inputs.

**ES output mode.** The same demux → decoder → output pipeline supports two different "modes" for who decides what to render. In normal mode, VLC auto-selects the best audio/video/subtitle tracks. In `--no-auto-select` mode (used when VLC is embedded in other apps via libVLC), the application controls track selection.

**Seeking is module-responsibility.** The input core sends a seek request to the demux module, which must reposition itself correctly in the container. Some formats (MPEG-TS broadcasts) don't support seeking at all; the module signals this to the core.

## Related

- [[capability-module-system--from-vlc]] (each stage of the pipeline is selected via the module system)
- [[libvlc-embeddable-engine--from-vlc]] (libVLC wraps this pipeline in a public API)
- [[stream-output-transcoding--from-vlc]] (the stream_out stage that can branch or transform the pipeline)
