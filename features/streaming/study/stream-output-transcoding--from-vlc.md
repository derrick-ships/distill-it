# Stream Output & Transcoding — from [vlc](https://code.videolan.org/videolan/vlc)

> Domain: [[streaming]] · Source: https://code.videolan.org/videolan/vlc · NotebookLM:

## What it does

VLC can simultaneously play and re-stream any media — converting its format, bitrate, and container on the fly. You can tell VLC to take a webcam feed and push it as HLS to a web server, transcode an MKV to MP4 while saving it locally, or duplicate a stream to two different destinations at once. This is the "stream output" (stream_out) system, and it uses the same module architecture as playback. The stream_out chain is a series of processing stages that media data flows through after decoding — and the transcode module is the most powerful stage in that chain.

## Why it exists

Broadcasters, digital signage operators, and video surveillance systems need to repackage streams in real time without a separate transcoding server. VLC's stream_out system brings this capability to a free, open-source tool that runs on commodity hardware. It's also what powers VLC's "Convert/Save" dialog, which wraps the same chain in a GUI.

## How it actually works

**The stream_out chain.** When VLC opens media in stream output mode, instead of routing decoded data to a local renderer, it routes it through a `sout_instance_t` — a chain of `stream_out` modules connected in series. You specify the chain as a string:

```
#transcode{vcodec=h264,vb=800,acodec=mp3,ab=128}:http{mux=ts,dst=:8080/stream}
```

The `#` starts the chain; `:` separates stages; each stage is a module name with optional parameters. VLC parses this at startup and assembles the `stream_out` module chain.

**Duplicate module.** `#duplicate{dst=...,dst=...}` splits the stream and sends copies through multiple chains simultaneously. This is how you simultaneously save to disk and push to a streaming server.

**Transcode module.** `#transcode{...}` is where re-encoding happens. When a packet arrives:
1. The transcode module passes it to a decoder (same module system as playback).
2. The decoded raw frames go through optional filters (deinterlace, scale, overlay).
3. The filtered frames go to an encoder — a `video encoder` or `audio encoder` module (x264, x265, FFmpeg, etc.).
4. The encoded packets are passed downstream.

For streams you don't want to re-encode, you can "copy" (`vcodec=copy`) which bypasses decode/encode entirely and just passes the compressed packets through.

**Mux/output module.** After transcode, a mux module (`ts`, `mp4`, `ogg`, `webm`) wraps the encoded packets in a container, and an output module (`file`, `http`, `rtp`, `udp`) delivers the result. The output modules are `stream_out` variants of the normal access modules.

**PCR/timestamp forwarding.** Transcoding changes frame timing. When re-encoding, the output encoder produces new timestamps, but the Program Clock Reference (PCR) for MPEG-TS multiplexing must still be consistent. VLC's transcode module tracks encode latency and adjusts PCR forwarding so downstream MPEG-TS streams have valid clock references — a non-trivial correctness requirement.

**Command-line / VLM.** VLC's Video LAN Manager (VLM) allows scheduling and managing multiple stream_out chains via a text protocol. `libvlc_vlm_add_broadcast()` starts a named broadcast with an input URL and sout string; `libvlc_vlm_stop_media()` stops it. This turns VLC into a mini streaming server controllable via network socket.

## The non-obvious parts

**The chain is asymmetric.** The transcode module is inside the `stream_out` chain, but it uses the same codec modules as the playback pipeline — just calling them as encoders instead of decoders. There's no separate "transcoding engine"; it's the same module system wearing different hats.

**Transcoding is expensive.** Decoding + re-encoding at high resolution is CPU-intensive. Hardware encoders (VideoToolbox, NVENC, VAAPI via `--sout-transcode-vcodec=h264_v4l2m2m`) dramatically reduce CPU load but require platform-specific setup.

**`vcodec=copy` is not lossless re-muxing at any bitrate.** It passes compressed packets unchanged. If the input is AVC in MKV and you want H.264 in TS, you can use `vcodec=copy` to avoid quality loss — but only if the codec is compatible with the output mux. H.264 in MKV vs. H.264 in TS differ only in container, not codec.

**HTTP streaming with VLC is single-threaded per client.** The `http` output module in VLC serves each client from a loop in one thread. For more than ~5-10 simultaneous clients, you need a proper CDN or server like nginx-rtmp. VLC's HTTP output is for testing or small deployments.

**VLM for automation.** Most integrations that automate VLC as a streaming engine use the VLM socket or `libvlc_vlm_*` API rather than parsing stream output chain strings manually. The VLM protocol is simple text: `new channel_name broadcast enabled loop in input_url out sout_string`.

## Related

- [[media-pipeline--from-vlc]] (stream_out plugs into the pipeline at the post-decode stage)
- [[capability-module-system--from-vlc]] (transcode reuses decoder/encoder modules via the same capability lookup)
- [[libvlc-embeddable-engine--from-vlc]] (libvlc_vlm_* API exposes stream_out control programmatically)
