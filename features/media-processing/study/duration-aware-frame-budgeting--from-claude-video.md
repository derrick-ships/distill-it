# Duration-Aware Frame Budgeting — from [claude-video](https://github.com/bradautomates/claude-video)

> Domain: [[_domain]] · Source: https://github.com/bradautomates/claude-video · NotebookLM: <link once added>

## What it does

When you hand a video to an LLM "to watch," you can't actually send it the video — you send it a handful of still frames plus a transcript. This feature is the part that decides **how many frames to grab and how far apart**, automatically, based on how long the video is.

A 20-second clip gets sampled densely (roughly one frame per second, ~12–20 frames) so nothing is missed. A 40-minute lecture gets capped at 100 frames spread thinly across the whole thing, with a printed warning that coverage is sparse. If you instead say "just look at 1:30 to 1:45," it switches into a denser "focus" budget — up to 2 frames per second — because you're clearly zooming in for detail.

The whole thing is a budget, not a fixed frame rate. The target is a *frame count* appropriate to the length, and the frame rate is back-calculated from that.

## Why it exists

Every frame you send to a multimodal model costs tokens — a lot of them (roughly 50–80k image tokens for 80 frames at 512px wide, and that *quadruples* at 1024px). So there are two competing failure modes:

- **Too few frames** on a short video → you miss the moment that answers the question.
- **Too many frames** on a long video → you blow the context window and the bill, and the model drowns.

A naive "extract 1 frame per second" breaks both ways: it's wasteful on a 3-second GIF and impossible on an hour-long video (3,600 frames). Budgeting by duration keeps short videos dense and long videos survivable, with one hard ceiling (100 frames) that nothing can exceed.

## How it actually works

It starts by probing the video with `ffprobe` to learn the real duration (and width/height/codec/whether there's an audio track). Duration is the only input that matters for budgeting.

Then it runs the duration through a **tier table**. In normal "scan the whole video" mode the tiers are:

- **≤30 seconds:** target ≈ the number of seconds, but never fewer than 12 frames. So a 5-second clip still gets 12 frames; a 25-second clip gets ~25.
- **30–60 seconds:** 40 frames.
- **1–3 minutes:** 60 frames.
- **3–10 minutes:** 80 frames.
- **over 10 minutes:** 100 frames (the cap), spread across the entire length — and a warning is printed telling you to use a focus range instead.

Once it has a target frame count, it divides by the duration to get the frames-per-second rate, then **clamps that rate to a hard maximum of 2 fps**. This clamp is the safety rail: it means even a tiny video never tries to pull more than 2 frames per second of real footage.

If you pass a `--start`/`--end` range, it switches to the **focus tier table**, which is deliberately denser because you're inspecting a small slice:

- **≤5s:** up to ~6 fps worth (but clamped to 2 fps, so really ~10 frames).
- **5–15s:** ~30+ frames.
- **15–30s:** 60 frames.
- **30–60s:** 80 frames.
- **1–3 min:** 100 frames (cap).

The actual frame grabbing is done by `ffmpeg` with a video filter that says "give me `fps=X` frames, scaled to `width=512`, keeping aspect ratio." It writes `frame_0001.jpg`, `frame_0002.jpg`, … and then — crucially — **reconstructs the real timestamp of each frame** so the model knows *when* in the video each picture was taken. The timestamp of frame *i* is `start_offset + i / fps`. That offset matters in focus mode: if you asked for 1:30–1:45, frame 0 is labeled t=1:30, not t=0.

## The non-obvious parts

- **It's a frame *budget*, not an fps setting.** The mental model most people reach for ("set the frame rate") is exactly backwards. Here the count is chosen first and the rate falls out of it. That's what lets a 10-second clip and a 10-minute video both produce a sane number of images.
- **The "never fewer than 12 frames" floor on short clips.** Without it, a 3-second video would get 3 frames, which is too sparse to understand motion. The floor guarantees a minimum density on the things most likely to be examined closely.
- **The 2-fps clamp is applied *after* the tier math.** The tiers can ask for a high rate (e.g. the ≤5s focus tier wants 6 fps); the clamp quietly caps it. So the tier tables read more aggressive than what actually runs.
- **Fast seek vs. accurate seek.** When extracting a range, `ffmpeg` is told to seek *before* loading the input (`-ss` before `-i`), which snaps to the nearest keyframe. It's fast but can be off by a fraction of a second — fine for preview frames, and the timestamps stay honest because they're computed from the requested start, not the actual keyframe.
- **100 is a religious ceiling.** Every path — normal, focus, manual fps override — is bounded by `max_frames` (default 80 from the orchestrator, hard max 100). Long videos don't get "a bit more," they get the cap and a warning. The honesty of telling the user "this is sparse, zoom in" is part of the design.

## Related

- [[captions-first-transcription-cascade--from-claude-video]] (the audio half of the same `/watch` pipeline — frames are the visual half)
- [[agentic-video-understanding-pipeline--from-claude-video]] (the orchestrator that calls this budgeter, then hands frame paths to Claude)
- See also: [[audio-transcription--from-markitdown]], [[media-pipeline--from-vlc]] — other media-processing approaches in this brain.
