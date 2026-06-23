# Captions-First Transcription Cascade — from [claude-video](https://github.com/bradautomates/claude-video)

> Domain: [[_domain]] · Source: https://github.com/bradautomates/claude-video · NotebookLM: <link once added>

## What it does

This is the part of the `/watch` skill that gets the **words** out of a video — the spoken audio turned into timestamped text the model can read alongside the frames. It tries the cheapest source first and only escalates if it has to:

1. **Native captions** — if the platform (YouTube, etc.) already has subtitles, yt-dlp downloads them and they're parsed directly. Free, instant, no API key.
2. **Whisper API fallback** — if there are no captions (or the source is a local file with none), it rips the audio, shrinks it to a tiny mono MP3, and uploads it to a speech-to-text API. Groq's `whisper-large-v3` is preferred (cheaper, faster); OpenAI's `whisper-1` is the alternate.

Either way, the result is the same: a list of `{start, end, text}` segments, rendered as `[MM:SS] spoken words…` lines. The rest of the pipeline can't tell which path produced it.

## Why it exists

Frames alone are blind to narration. A coding tutorial's frames show the screen, but the *explanation* is spoken. So you need the transcript — but transcription is the expensive, slow, rate-limited part of the whole system, so the design is obsessed with not paying for it when you don't have to.

The free path (captions) covers the overwhelmingly common case (popular videos have subtitles). The paid path exists only as a safety net for caption-less content and local files. Putting free-first into the architecture — not as an afterthought — is what keeps `/watch` cheap to run at scale.

## How it actually works

**The caption path.** When downloading, yt-dlp is asked to also write subtitles (both human-made and auto-generated) in WebVTT format, English variants preferred. WebVTT from YouTube auto-captions is *messy*: because captions scroll on screen, the same line appears two or three times across overlapping time windows. So the parser does two jobs — it reads each timestamped cue and strips the inline styling tags, **and** it dedupes: if a cue repeats the previous text it just extends the previous segment's end time; if a cue is the previous text plus more words (the scroll growing), it replaces it. The output is clean, non-repeating segments.

**The Whisper path.** Only entered if captions produced nothing. First it extracts audio with ffmpeg into a deliberately tiny format — mono, 16 kHz, 64 kbps MP3, about half a megabyte per minute — because the APIs have upload size limits (~25 MB) and you want long videos to fit. Then it uploads. The clever bit: it does the multipart/form-data HTTP upload **by hand with pure standard library**, so there's no `pip install groq` or `pip install openai` — the tool stays dependency-free. It picks the backend by which API key is present (Groq first), POSTs the audio, and converts the API's response into the same `{start, end, text}` shape the caption parser produces.

**Choosing and focusing.** Backend selection reads keys from environment variables or a `~/.config/watch/.env` file, Groq preferred unless you force one. If you asked for a focus range (say 1:30–1:45), the transcript is filtered to just the segments overlapping that window, so the words line up with the frames you're looking at.

**Resilience.** The upload isn't a single shot. It retries up to four attempts total with exponential backoff. It treats rate-limit (429) responses specially — honoring the server's `Retry-After` header if present, and giving up after two 429s rather than hammering. Other 4xx client errors fail immediately (retrying a bad request never helps). Network blips (timeouts, connection resets) get their own retry path.

## The non-obvious parts

- **Free-first is the whole point.** The expensive API is structurally the *fallback*, not the default. Most runs never touch it.
- **The YouTube rolling-duplicate problem is real and easy to miss.** If you naively parse VTT you get a transcript where every sentence is tripled. The dedupe logic (exact-repeat → extend; prefix-growth → replace) is the unglamorous fix that makes the transcript usable.
- **Hand-rolled multipart to avoid SDKs.** Both Whisper APIs are OpenAI-compatible and the upload is simple enough that building the multipart body manually is worth it to keep the tool installable with zero Python dependencies. That's a deliberate trade: a little gnarly byte-assembly code in exchange for "it just runs."
- **The Cloudflare User-Agent trap.** Groq sits behind Cloudflare, and the default `Python-urllib/3.x` user agent trips a WAF rule and gets a 403 *before authentication even runs*. Setting any non-default UA fixes it. This is the kind of thing you'd burn an hour debugging — it looks like an auth failure but isn't.
- **Audio is shrunk aggressively on purpose.** Mono 16 kHz 64 kbps is far below music quality, but it's plenty for speech recognition and it's what lets a long video's audio fit under the 25 MB upload ceiling.
- **One normalized shape unifies everything.** Captions and Whisper both emit `{start, end, text}`. That single decision is why `filter_range` and `format_transcript` are written once and work for both.

## Related

- [[duration-aware-frame-budgeting--from-claude-video]] (the visual half of the same `/watch` pipeline)
- [[agentic-video-understanding-pipeline--from-claude-video]] (the orchestrator that runs captions → whisper and merges with frames)
- See also: [[audio-transcription--from-markitdown]] (file-at-rest transcription via speech_recognition), [[push-to-talk-streaming-transcription--from-clicky]] (live streaming STT) — different points on the transcription spectrum.
