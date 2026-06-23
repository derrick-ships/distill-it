# Domain: transcription

Turning spoken audio in video/audio media into clean, timestamped text — preferring free existing captions, falling back to paid speech-to-text APIs only when needed.

## What this domain is about

Many "understand this media" pipelines need the words, not just the pixels. This domain covers the patterns for getting a timestamped transcript cheaply and robustly: pulling platform-provided captions first (free), parsing their messy formats (WebVTT with rolling duplicates), and only paying for a Whisper-class API when captions are absent. The unifying idea is a **cost-ordered cascade** with a single normalized segment shape so downstream code never cares where the transcript came from.

## Key pattern: cost-ordered fallback to a normalized shape

Every source — native captions or a Whisper API — is reduced to the same `{start, end, text}` segment list. Captions are tried first because they're free and instant; Whisper is the paid fallback. Both feed the same `filter_range` (for focus windows) and `format_transcript` (for `[MM:SS] text` output). Swapping or adding a backend never touches the consumer.

## Features in this domain

- [[captions-first-transcription-cascade--from-claude-video]] — native captions (yt-dlp WebVTT, deduped) first, then Groq `whisper-large-v3` / OpenAI `whisper-1` over a hand-rolled stdlib multipart upload with retry/backoff. The cost-ordered cascade behind the `/watch` skill.
