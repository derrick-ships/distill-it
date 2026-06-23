# claude-video

> Source: https://github.com/bradautomates/claude-video · Distilled: 2026-06-23

## What it is

A Claude Code skill (`/watch`) that lets the model actually watch a video. You give it a URL (YouTube, TikTok, Vimeo, Instagram, X) or a local file plus a question; it downloads the video, extracts auto-scaled timestamped frames with ffmpeg, pulls a timestamped transcript (platform captions first, Whisper API fallback), and emits a markdown report of frame paths + transcript. Claude then reads each frame image and answers from the real visual + audio content. Pure-stdlib Python over `yt-dlp` + `ffmpeg`; packaged as a Claude Code plugin.

**Stack:** Python (stdlib only — no pip deps), shell, `yt-dlp`, `ffmpeg`/`ffprobe`, Groq `whisper-large-v3` / OpenAI `whisper-1`.

## Features distilled

| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| Duration-Aware Frame Budgeting | media-processing | [study](../features/media-processing/study/duration-aware-frame-budgeting--from-claude-video.md) | [build](../features/media-processing/build/duration-aware-frame-budgeting--from-claude-video.md) |
| Captions-First Transcription Cascade | transcription | [study](../features/transcription/study/captions-first-transcription-cascade--from-claude-video.md) | [build](../features/transcription/build/captions-first-transcription-cascade--from-claude-video.md) |
| Agentic Video-Understanding Pipeline (`/watch`) | agent-architecture | [study](../features/agent-architecture/study/agentic-video-understanding-pipeline--from-claude-video.md) | [build](../features/agent-architecture/build/agentic-video-understanding-pipeline--from-claude-video.md) |

## Not yet distilled (candidates)

- Multi-source video ingestion (yt-dlp wrapper, format selection, subtitle fetch) — partially covered inside the pipeline + transcription build specs.
- ffmpeg frame extraction mechanics — covered inside the frame-budgeting build spec.
- Skill preflight + setup contract (`setup.py --check` exit codes, key/env management) — summarized inside the pipeline build spec; not a standalone doc.
