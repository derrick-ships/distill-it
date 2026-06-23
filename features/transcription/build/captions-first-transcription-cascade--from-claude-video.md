# Captions-First Transcription Cascade (build spec) — distilled from claude-video

## Summary

Get a timestamped transcript from a video, cheapest source first: (1) parse platform captions (WebVTT, deduped) if present; (2) else extract tiny mono MP3 audio and POST it to a Whisper-compatible API (Groq `whisper-large-v3` preferred, OpenAI `whisper-1` fallback) via a hand-rolled stdlib multipart upload with retry/backoff. Every source normalizes to `{start, end, text}` segments so `filter_range` and `format_transcript` work regardless of origin. Zero third-party Python deps.

## Core logic (inlined)

### 1. Caption path — WebVTT parse + dedupe

yt-dlp is told to fetch subs (`--write-subs --write-auto-subs --sub-langs en,en-US,en-GB,en-orig --sub-format vtt --convert-subs vtt`). Then:

```python
TS_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s+-->\s+(\d{2}):(\d{2}):(\d{2})[.,](\d{3})")
TAG_RE = re.compile(r"<[^>]+>")   # strip inline <c>, <00:00:00.000> styling tags

def parse_vtt(path):
    lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    segments, i = [], 0
    while i < len(lines):
        m = TS_RE.match(lines[i])
        if not m:
            i += 1; continue
        start = _to_seconds(*m.groups()[:4]); end = _to_seconds(*m.groups()[4:])
        i += 1
        cue = []
        while i < len(lines) and lines[i].strip():
            cleaned = TAG_RE.sub("", lines[i]).strip()
            if cleaned: cue.append(cleaned)
            i += 1
        text = " ".join(cue).strip()
        if text: segments.append({"start": round(start,2), "end": round(end,2), "text": text})
        i += 1
    return _dedupe(segments)

def _dedupe(segments):                 # collapse YouTube rolling duplicates
    out = []
    for seg in segments:
        if out and seg["text"] == out[-1]["text"]:            # exact repeat -> extend end
            out[-1]["end"] = seg["end"]; continue
        if out and seg["text"].startswith(out[-1]["text"] + " "):  # scroll grew -> replace
            out[-1]["text"] = seg["text"]; out[-1]["end"] = seg["end"]; continue
        out.append(seg)
    return out
```

`_to_seconds(h,m,s,ms) = int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000`.

### 2. Whisper path — only if captions yielded nothing

**Audio extraction (tiny on purpose):**
```
ffmpeg -hide_banner -loglevel error -y -i <video> -vn \
       -acodec libmp3lame -ar 16000 -ac 1 -b:a 64k <out.mp3>
# mono, 16kHz, 64kbps ~= 480 kB/min -> fits the ~25 MB Whisper upload limit
```

**Endpoints / models:**
```
GROQ:   https://api.groq.com/openai/v1/audio/transcriptions   model whisper-large-v3
OPENAI: https://api.openai.com/v1/audio/transcriptions        model whisper-1
```

**Backend + key resolution** — prefer Groq, fall back to OpenAI; env first then dotenv:
```python
# order: GROQ_API_KEY then OPENAI_API_KEY
# sources per key: os.environ, then ~/.config/watch/.env, then ./.env
# dotenv parse: skip blank/#; split on first '='; strip matching surrounding quotes
# if `preferred` ("groq"|"openai") given, only that backend's key is considered
# returns (backend, api_key) or (None, None)
```

**Hand-rolled multipart upload (pure stdlib):**
```python
def _build_multipart(fields, file_path):       # fields = {model, response_format, temperature}
    boundary = f"----WatchBoundary{uuid.uuid4().hex}"
    eol = b"\r\n"; buf = io.BytesIO()
    for name, value in fields.items():
        buf.write(f"--{boundary}".encode()+eol)
        buf.write(f'Content-Disposition: form-data; name="{name}"'.encode()+eol+eol)
        buf.write(str(value).encode()+eol)
    mime = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    buf.write(f"--{boundary}".encode()+eol)
    buf.write(f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"'.encode()+eol)
    buf.write(f"Content-Type: {mime}".encode()+eol+eol)
    buf.write(file_path.read_bytes()+eol)
    buf.write(f"--{boundary}--".encode()+eol)
    return buf.getvalue(), boundary
```

**POST with retry/backoff:**
```python
MAX_ATTEMPTS = 4; MAX_429_RETRIES = 2; RETRY_BASE_DELAY = 2.0
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": f"multipart/form-data; boundary={boundary}",
    # CRITICAL: Groq is behind Cloudflare; default Python-urllib UA trips WAF rule 1010 (403)
    # BEFORE auth runs. Any non-default UA clears it.
    "User-Agent": "watch-skill/1.0 (+claude-code; python-urllib)",
}
# fields = {"model": model, "response_format": "verbose_json", "temperature": "0"}
# loop attempt 0..3:
#   urlopen(timeout=300). On success -> json.loads(body).
#   HTTPError: if 400<=code<500 and code!=429 -> raise immediately (client error, no retry).
#              if 429 -> rate_limit_hits++; give up after MAX_429_RETRIES; delay = Retry-After header or 2*2**attempt + 1.
#              else (5xx) -> delay = 2*2**attempt.
#   URLError/Timeout/ConnReset/OSError -> delay = 2*(attempt+1).
#   sleep(delay) and continue.
```

**Normalize response → segments:**
```python
def _segments_from_response(data):     # Whisper verbose_json
    out = [{"start": round(float(s.get("start") or 0),2),
            "end":   round(float(s.get("end")   or 0),2),
            "text":  (s.get("text") or "").strip()}
           for s in (data.get("segments") or []) if (s.get("text") or "").strip()]
    if not out and (data.get("text") or "").strip():     # fallback: whole-text, no timestamps
        out = [{"start": 0.0, "end": 0.0, "text": data["text"].strip()}]
    return out
```

### 3. Shared consumers (work on either source's output)

```python
def filter_range(segments, start, end):     # keep segments overlapping [start, end]
    if start is None and end is None: return segments
    lo = start if start is not None else float("-inf")
    hi = end   if end   is not None else float("inf")
    return [s for s in segments if s["end"] >= lo and s["start"] <= hi]

def format_transcript(segments):            # "[MM:SS] text" lines
    return "\n".join(f"[{int(s['start'])//60:02d}:{int(s['start'])%60:02d}] {s['text']}"
                     for s in segments)
```

## Data contracts

Normalized segment (the universal shape):
```json
{"start": 90.0, "end": 94.5, "text": "and here we define the handler"}
```
Whisper request fields: `model`, `response_format=verbose_json`, `temperature=0`, plus the audio `file`. Whisper response consumed: `segments[].{start,end,text}`, with `text` as a whole-string fallback. dotenv line format: `KEY=value` (optional surrounding quotes stripped, `#` comments skipped).

## Dependencies & assumptions

- **`ffmpeg`** (audio extraction) and **`yt-dlp`** (caption fetch) on PATH. No Python packages — `urllib`, `ssl`, `io`, `mimetypes`, `uuid`, `re` only.
- **An API key**: `GROQ_API_KEY` (preferred) or `OPENAI_API_KEY`, from env or `~/.config/watch/.env`.
- Whisper upload limit ~25 MB → the 16kHz/mono/64k audio profile is sized to fit long videos.

## To port this, you need:
- [ ] ffmpeg + yt-dlp (or your own caption source) in the environment.
- [ ] At least one Whisper-compatible key, resolved from env/dotenv.
- [ ] To keep the `{start,end,text}` normalization if you want `filter_range`/`format_transcript` to stay source-agnostic.
- [ ] The non-default `User-Agent` header if you use Groq (otherwise 403 behind Cloudflare).

## Gotchas

- **Groq + default urllib UA = 403 before auth.** Set any non-default `User-Agent`. The error looks like an auth/permissions problem but is a Cloudflare WAF block.
- **YouTube auto-caption rolling duplicates** triple every line if you don't dedupe (exact-repeat → extend end; prefix-growth → replace). Don't skip `_dedupe`.
- **Don't retry non-429 4xx.** A 400/401/413 won't fix itself; retrying wastes time and money. Only 429 + 5xx + network errors are retryable.
- **429 handling honors `Retry-After`** when present; caps at 2 rate-limit retries so you don't hammer a throttled key.
- **yt-dlp may exit non-zero just because a subtitle variant 429'd** even though the video downloaded fine — treat "video file present" as success, and the caption path simply yields nothing (→ Whisper fallback).
- **No audio track** → ffmpeg produces an empty file; detect zero-size output and fail clearly ("video may have no audio track").
- **`response_format=verbose_json` is required** to get per-segment timestamps; plain `json` returns only whole text (handled by the fallback, but you lose timing).

## Origin (reference only)

Repo: https://github.com/bradautomates/claude-video — `scripts/transcribe.py` (VTT parse + dedupe + filter_range + format_transcript), `scripts/whisper.py` (audio extract, multipart, retry POST, key resolution, segment normalize), `scripts/download.py` (yt-dlp subtitle flags).
