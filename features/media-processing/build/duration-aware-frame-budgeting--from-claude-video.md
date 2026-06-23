# Duration-Aware Frame Budgeting (build spec) — distilled from claude-video

## Summary

Given a video and (optionally) a `[start, end]` range, decide **how many frames to extract and at what fps**, then extract them with ffmpeg and return each frame's absolute timestamp. The frame *count* is budgeted by duration (short → dense, long → capped at 100); the fps is derived from `count / duration` and hard-clamped to 2 fps. Two budget tables: a normal "whole video" table and a denser "focus" table used when the caller passes a range. Pure stdlib + `ffprobe`/`ffmpeg` subprocess calls.

## Core logic (inlined)

Constants: `MAX_FPS = 2.0`, default `max_frames = 100` (the orchestrator passes 80 by default but caps at 100).

**Clamp helper** — converts a desired fps into a (fps, frame-count) pair bounded by both the fps ceiling and the frame ceiling:

```python
def _clamp_fps(fps, duration_seconds, max_frames):
    fps = min(fps, MAX_FPS)                                  # never above 2 fps
    target = min(max_frames, max(1, round(fps * duration_seconds)))
    return fps, target
```

**Normal budget (full-video scan):** pick a target frame COUNT from a duration tier table, then back-derive fps = target/duration and clamp.

```python
def auto_fps(duration_seconds, max_frames=100):
    if duration_seconds <= 0:
        return 1.0, 1
    if duration_seconds <= 30:
        target = min(max_frames, max(12, round(duration_seconds)))   # floor of 12 frames
    elif duration_seconds <= 60:
        target = min(max_frames, 40)
    elif duration_seconds <= 180:      # 3 min
        target = min(max_frames, 60)
    elif duration_seconds <= 600:      # 10 min
        target = min(max_frames, 80)
    else:
        target = max_frames            # >10 min: hard cap, sparse
    return _clamp_fps(target / duration_seconds, duration_seconds, max_frames)
```

**Focus budget (range supplied) — deliberately denser:**

```python
def auto_fps_focus(duration_seconds, max_frames=100):
    if duration_seconds <= 0:
        return min(MAX_FPS, 2.0), 2
    if duration_seconds <= 5:
        target = min(max_frames, max(10, round(duration_seconds * 6)))
    elif duration_seconds <= 15:
        target = min(max_frames, max(30, round(duration_seconds * 4)))
    elif duration_seconds <= 30:
        target = min(max_frames, 60)
    elif duration_seconds <= 60:
        target = min(max_frames, 80)
    else:                              # 60s-180s and beyond
        target = max_frames
    return _clamp_fps(target / duration_seconds, duration_seconds, max_frames)
```

**Selection at call time:** `focused = start is not None or end is not None`. `effective_duration = max(0, effective_end - effective_start)` where `effective_end` defaults to full duration and `effective_start` to 0. Call `auto_fps_focus` if focused else `auto_fps`. A manual `--fps` override bypasses the tables: `fps = min(override, MAX_FPS); target = max(1, round(fps * effective_duration))`.

**Probe (ffprobe) — get duration + dims + audio presence:**

```
ffprobe -v quiet -print_format json -show_format -show_streams <path>
# duration = float(format.duration or video_stream.duration or 0)
# returns {duration_seconds, width, height, codec, size_bytes, has_audio}
```

**Extraction (ffmpeg):**

```python
def extract(video_path, out_dir, fps, resolution=512, max_frames=100,
            start_seconds=None, end_seconds=None):
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("frame_*.jpg"): old.unlink()   # clean stale frames
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    if start_seconds is not None: cmd += ["-ss", f"{start_seconds:.3f}"]  # BEFORE -i = fast keyframe seek
    if end_seconds   is not None: cmd += ["-to", f"{end_seconds:.3f}"]
    cmd += ["-i", video_path,
            "-vf", f"fps={fps},scale={resolution}:-2",     # -2 keeps aspect, even dims
            "-frames:v", str(max_frames),                  # hard stop at the cap
            "-q:v", "4",                                   # JPEG quality knob
            f"{out_dir}/frame_%04d.jpg"]
    subprocess.run(cmd, capture_output=True, text=True)    # raise on returncode != 0
    offset = start_seconds or 0.0
    frames = sorted(out_dir.glob("frame_*.jpg"))
    return [{"index": i,
             "timestamp_seconds": round(offset + (i / fps if fps > 0 else 0.0), 2),
             "path": str(p)} for i, p in enumerate(frames)]
```

**Time parsing** (`SS`, `MM:SS`, `HH:MM:SS`, optional `.ms`): split on `:`; 1 part = seconds, 2 = `m*60+s`, 3 = `h*3600+m*60+s`. **Time formatting** for labels: `MM:SS`, or `H:MM:SS` if >=1h.

## Data contracts

`ffprobe` metadata dict:
```json
{"duration_seconds": 137.4, "width": 1280, "height": 720,
 "codec": "h264", "size_bytes": 9123841, "has_audio": true}
```

`extract()` returns a list of frame records (this is what the orchestrator hands to the model):
```json
[{"index": 0, "timestamp_seconds": 90.0, "path": "/tmp/watch-x/frames/frame_0001.jpg"},
 {"index": 1, "timestamp_seconds": 90.5, "path": "/tmp/watch-x/frames/frame_0002.jpg"}]
```
Note `timestamp_seconds` is the ABSOLUTE source-video time (offset + index/fps), not relative to the clip — so frame 0 of a 1:30-1:45 focus run is `90.0`, not `0.0`.

## Dependencies & assumptions

- **`ffmpeg` + `ffprobe`** on PATH (the only hard deps). No Python packages — pure stdlib (`subprocess`, `shutil.which`, `pathlib`, `json`).
- Output frames are JPEG at `-q:v 4`, width = `resolution` (default 512; 1024 for reading on-screen text/code), height auto (`-2`).
- Assumes the consumer understands a token cost of ~50-80k image tokens for 80 frames @ 512px, ~4x at 1024px — this is why the cap exists.

## To port this, you need:
- [ ] `ffmpeg` and `ffprobe` available (check with `shutil.which`, fail with an install hint).
- [ ] A writable temp/working dir for the JPEGs.
- [ ] A downstream consumer that can read image files by path (e.g. a multimodal model's image input). The budgeter is consumer-agnostic.
- [ ] To tune `MAX_FPS` (2.0), the frame floor (12), and the cap (100) to your model's context/cost envelope — these three numbers are the whole policy.

## Gotchas

- **Clamp order matters:** the tier tables can request >2 fps (the <=5s focus tier asks ~6 fps); `_clamp_fps` silently caps to 2. Don't read the tables as the real fps.
- **`-ss` before `-i` is fast seek (keyframe-snap).** Can land slightly off the requested second. Fine for preview frames; for frame-exact seeking put `-ss` after `-i` (slower, decodes from 0). Timestamps stay honest either way (computed from requested start, not decoded PTS).
- **`scale=W:-2`** (not `-1`) forces even height — some encoders/JPEG paths choke on odd dimensions. Keep the `-2`.
- **`-frames:v max_frames` is a second safety net** beyond the fps math: even if fps*duration overshoots, ffmpeg stops at the cap.
- **Stale-frame cleanup:** deletes existing `frame_*.jpg` before extracting. Reusing a dir without this mixes old and new frames.
- **`duration <= 0`** (ffprobe couldn't read it) → returns a minimal 1-frame budget rather than dividing by zero. Handle "unknown duration" explicitly.

## Origin (reference only)

Repo: https://github.com/bradautomates/claude-video — logic in `scripts/frames.py` (`auto_fps`, `auto_fps_focus`, `_clamp_fps`, `extract`, `get_metadata`, `parse_time`, `format_time`). Selection/override also mirrored in `scripts/watch.py`.
