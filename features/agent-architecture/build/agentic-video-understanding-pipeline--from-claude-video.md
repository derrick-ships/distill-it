# Agentic Video-Understanding Pipeline (`/watch`) (build spec) — distilled from claude-video

## Summary

A skill that gives an LLM agent the ability to "watch" video without a video model: a Python orchestrator turns a video (URL or local) into timestamped frames + a timestamped transcript, prints a markdown report of frame file paths, and the agent Reads those images and answers. The agent is the reasoning engine; the script is its eyes/ears. Pattern = **decompose video into the modalities the model already has (image + text), aligned on a shared timestamp clock, delivered via a skill contract.**

## Core logic (inlined)

### The skill contract (what the agent does — from SKILL.md)

```
Step 0  Preflight: run `setup.py --check`. Exit 0 => proceed silently.
        Non-zero => prompt to install binaries / set API key (exit code says which).
Step 1  Parse user message -> (source: URL|path, question, optional flags).
Step 2  Run: python3 watch.py "<source>" [flags]   (prints markdown report to stdout).
Step 3  Read EVERY frame path in the report with the Read tool (parallel calls) -> model "sees" the video.
Step 4  Answer the question using frames (timestamped visuals) + transcript (timestamped words).
Step 5  Delete the work dir (recursive remove) unless follow-ups are expected.
```

The script never calls the model. It only emits file paths + text. The agent's instructions ("read the frames, then answer") live in the skill, not the code. This separation is the reusable core.

### The orchestrator (watch.py) — glue across download -> frames -> transcript -> report

```python
# 1. work dir: tempfile.mkdtemp(prefix="watch-")  (or --out-dir)
# 2. download: dl = download(source, work/"download")
#       URL  -> yt-dlp at <=720p, mp4, + write-subs/write-auto-subs (vtt), + info.json
#       local-> resolve path, no subs
#    returns {video_path, subtitle_path|None, info, downloaded}
# 3. probe: meta = get_metadata(video_path)  -> duration etc.
# 4. range validation:
#       start>=0; end>start; start < full_duration
#    effective_start/end/duration; focused = start or end is not None
# 5. frame budget: auto_fps_focus(dur) if focused else auto_fps(dur); --fps overrides (clamped to 2)
#    frames = extract(video, work/"frames", fps, resolution, max_frames, start, end)
# 6. transcript cascade:
#       if subtitle_path: segs = parse_vtt(subtitle_path); if focused -> filter_range(segs,start,end)
#       elif not --no-whisper:
#            backend,key = load_api_key(--whisper)
#            if backend: segs = transcribe_video(video, work/"audio.mp3", backend, key); filter if focused
#            else: print a "set an API key" hint, continue frames-only
# 7. print markdown report (see Data contracts).
```

Key default: `--max-frames` default is **80**, hard-capped to `min(max_frames, 100)`. Download format string: `-f "bv*[height<=720]+ba/b[height<=720]/bv+ba/b" --merge-output-format mp4`.

### Download specifics (download.py)

```python
def is_url(s):  # NOT a URL if it starts with "-"; else urlparse scheme in (http,https) and netloc
yt-dlp flags: -N 8 (concurrent fragments), --write-info-json, --write-subs, --write-auto-subs,
              --sub-langs en,en-US,en-GB,en-orig, --sub-format vtt, --convert-subs vtt,
              --no-playlist, --ignore-errors, -o "<dir>/video.%(ext)s"
# Treat "video file present in out dir" as success even if yt-dlp exits non-zero
# (a failed subtitle variant must not fail the whole download).
# Subtitle pick: prefer a *.en*.vtt among video*.vtt. Info from video.info.json
# -> {title, uploader|channel, duration, webpage_url}.
```

### Preflight (setup.py --check) — exit-code contract

```
exit 0  all good, proceed silently
exit 2  missing binaries (yt-dlp / ffmpeg)
exit 3  no API key
exit 4  both missing
# <100ms lookup; lets the skill decide: run, or prompt the precise fix.
```

## Data contracts

**The report (stdout markdown the agent consumes):**
```markdown
# watch: video report

- **Source:** <url-or-path>
- **Title:** ... / **Uploader:** ...
- **Duration:** MM:SS (137.4s)
- **Focus range:** 1:30 -> 1:45 (15.0s)        # only if focused
- **Resolution:** 1280x720 (h264)
- **Frames:** 30 @ 1.000 fps, full mode (budget 60, max 80)
- **Transcript:** 24 segments (via captions|whisper (groq))

> **Warning:** This is a 42-minute video. Frame coverage is sparse... (only if full & >600s)

## Frames
Frames live at: `/tmp/watch-xxxx/frames`
**Read each frame path below with the Read tool to view the image.**
- `/tmp/watch-xxxx/frames/frame_0001.jpg` (t=0:00)
- `/tmp/watch-xxxx/frames/frame_0002.jpg` (t=0:01)
...

## Transcript
_Source: captions._
(transcript lines, each "[MM:SS] spoken text", inside a fenced block)

---
_Work dir: `/tmp/watch-xxxx` — delete when done._
```

**download() return:** `{video_path, subtitle_path|None, info:{title,uploader,duration,url}, downloaded}`.
**Frame record:** `{index, timestamp_seconds (absolute), path}`.
**Transcript segment:** `{start, end, text}`.

## Dependencies & assumptions

- External binaries on PATH: **`yt-dlp`**, **`ffmpeg`/`ffprobe`**.
- Optional **`GROQ_API_KEY`/`OPENAI_API_KEY`** (env or `~/.config/watch/.env`) for the Whisper fallback.
- A host agent that (a) can run a shell command and capture stdout, and (b) can read local image files as multimodal input (the Read tool). Pure stdlib Python otherwise.
- Skill packaging: `SKILL.md` (contract) + `scripts/` + a SessionStart/preflight hook. Installable via Claude Code plugin marketplace (`.claude-plugin/`).

## To port this, you need:
- [ ] An agent runtime that can shell out and read image files by path (the two capabilities the whole pattern rests on).
- [ ] yt-dlp + ffmpeg installed (or substitute your own download/extract).
- [ ] The frame budgeter ([[duration-aware-frame-budgeting--from-claude-video]]) and transcript cascade ([[captions-first-transcription-cascade--from-claude-video]]) — this spec orchestrates both.
- [ ] A skill/tool-contract layer telling the agent: run script -> read every frame path -> answer using frames+transcript -> clean up. Without this the script's output is inert.
- [ ] A temp-dir lifecycle (create per run, recursive-remove after) to avoid state leaks.

## Gotchas

- **Timestamps are the alignment key.** Frames and transcript MUST share absolute source time, or the agent can't correlate "what's shown" with "what's said." Don't drop or relativize them.
- **The agent must actually Read the frames.** If the host just passes the markdown text, the model never sees the images — it only sees paths. The skill step "Read each frame path" is load-bearing.
- **Treat yt-dlp non-zero exit as soft.** Subtitle fetch failures (429s) are common and must not fail a good video download — check for the video file instead of trusting the exit code.
- **Sparse-coverage honesty.** >10 min full-scan prints a warning and suggests `--start/--end`. Keep that — silently sparse frames produce confidently wrong answers.
- **Resolution vs. cost.** 512px default is fine for scenes; bump to 1024 only to read on-screen text/code (~4x the image tokens). Expose it.
- **Frames-only is a valid terminal state.** No captions + no key + `--no-whisper` -> report frames with a clear "no transcript" note rather than erroring. The agent can still answer visual questions.
- **`is_url` excludes args starting with `-`** so a stray flag isn't mistaken for a source.

## Origin (reference only)

Repo: https://github.com/bradautomates/claude-video — `SKILL.md` (the 5-step contract), `scripts/watch.py` (orchestrator), `scripts/download.py`, `scripts/setup.py` (preflight exit codes). Frame + transcript internals in the two related build specs.
