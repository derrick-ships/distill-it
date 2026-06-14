# YouTube URL Extraction (build spec) — distilled from markitdown

## Summary

Converts a YouTube watch URL into Markdown. Scrapes HTML meta tags for structured metadata, digs `ytInitialData` JSON out of a script tag for the description, and uses `youtube_transcript_api` for the full transcript (with retry logic). All three parts are independently optional.

## Core logic (inlined)

```python
import json, re, time
from bs4 import BeautifulSoup
import requests

class YouTubeConverter(DocumentConverter):
    def accepts(self, stream, stream_info, **kwargs):
        url = stream_info.url or ""
        mime = stream_info.mimetype or ""
        return (
            url.startswith("https://www.youtube.com/watch?")
            and (mime.startswith("text/html") or (stream_info.extension or "") in (".html", ".htm"))
        )

    def convert(self, stream, stream_info, **kwargs):
        html = stream.read().decode(stream_info.charset or "utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        parts = []

        # Title
        title = soup.find("title")
        if title:
            clean_title = title.text.replace(" - YouTube", "").strip()
            parts.append(f"# {clean_title}")

        # Structured metadata from <meta> tags
        meta_fields = {
            "interactionCount": "Views",
            "keywords": "Keywords",
            "duration": "Duration",
        }
        for prop, label in meta_fields.items():
            tag = soup.find("meta", {"itemprop": prop})
            if tag and tag.get("content"):
                parts.append(f"**{label}**: {tag['content']}")

        # Description from ytInitialData JSON (buried in <script> tag)
        description = _extract_yt_description(soup)
        if description:
            parts.append(f"\n## Description\n{description}")

        # Transcript
        url = stream_info.url or ""
        video_id = _extract_video_id(url)
        if video_id:
            transcript = _fetch_transcript(video_id, max_retries=3, retry_delay=2.0)
            if transcript:
                parts.append(f"\n## Transcript\n{transcript}")

        return DocumentConverterResult(text_content="\n".join(parts))


def _extract_video_id(url: str) -> str | None:
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url)
    return parse_qs(parsed.query).get("v", [None])[0]


def _extract_yt_description(soup: BeautifulSoup) -> str | None:
    for script in soup.find_all("script"):
        if script.string and "ytInitialData" in script.string:
            match = re.search(r"var ytInitialData\s*=\s*(\{.*?\});\s*</script>",
                              script.string, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    return _find_key_recursive(data, "attributedDescriptionBodyText")
                except json.JSONDecodeError:
                    pass
    return None


def _find_key_recursive(obj, key: str):
    if isinstance(obj, dict):
        if key in obj:
            content = obj[key]
            # The value may be {"content": "text"} or plain string
            if isinstance(content, dict):
                return content.get("content", str(content))
            return str(content)
        for v in obj.values():
            result = _find_key_recursive(v, key)
            if result: return result
    elif isinstance(obj, list):
        for item in obj:
            result = _find_key_recursive(item, key)
            if result: return result
    return None


def _fetch_transcript(video_id: str, max_retries=3, retry_delay=2.0) -> str | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return None

    for attempt in range(max_retries):
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            try:
                transcript = transcript_list.find_transcript(["en"])
            except Exception:
                transcript = transcript_list.find_generated_transcript(["en"])
            segments = transcript.fetch()
            return " ".join(seg["text"] for seg in segments)
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    return None
```

## Data contracts

- **Input**: HTML bytes from a `youtube.com/watch?v=...` URL; `stream_info.url` must be set
- **Output**: Markdown with title `#`, metadata key-values, `## Description`, `## Transcript`
- `ytInitialData` JSON structure: large nested dict; description at `attributedDescriptionBodyText.content`
- Transcript segments: list of `{"text": str, "start": float, "duration": float}`

## Dependencies & assumptions

```
beautifulsoup4 >= 4.12
youtube-transcript-api >= 0.6   # optional; transcript skipped if absent
```

## To port this, you need:

- [ ] `accepts()` URL prefix check on `stream_info.url`
- [ ] BeautifulSoup meta tag extraction for `interactionCount`, `keywords`, `duration`
- [ ] `_extract_yt_description()` — script tag scan + JSON parse + recursive key search
- [ ] `_extract_video_id()` from URL query param `v`
- [ ] `_fetch_transcript()` with retry loop and `ImportError` catch
- [ ] `youtube_transcript_api` optional — return `None` if not installed

## Gotchas

- `ytInitialData` JSON is multi-megabyte and changes structure across YouTube UI versions. The recursive key search is more robust than a hardcoded path.
- The regex for extracting `ytInitialData` may need tuning — YouTube occasionally changes the variable assignment syntax.
- Only handles `youtube.com/watch?v=` URLs. Shorts (`/shorts/`), playlists, and channel pages need separate handling.
- `youtube_transcript_api` is rate-limited. The 3-retry / 2s-delay loop handles transient 429s.

## Origin

https://github.com/microsoft/markitdown — `converters/_youtube_converter.py`
