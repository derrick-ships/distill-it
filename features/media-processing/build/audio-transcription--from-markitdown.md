# Audio Transcription (build spec) — distilled from markitdown

## Summary

WAV/MP3/M4A/MP4 converter with two layers: exiftool subprocess for audio metadata (title, artist, album, bitrate, etc.), and `speech_recognition` library for speech-to-text. Both are optional. Duration is explicitly excluded from exiftool extraction due to incorrect values when reading from memory streams.

## Core logic (inlined)

```python
import speech_recognition as sr
from io import BytesIO
import tempfile, os

AUDIO_EXIF_FIELDS = [
    "Title", "Artist", "Author", "Band", "Album", "Genre", "Track",
    "DateTimeOriginal", "CreateDate", "NumChannels", "SampleRate",
    "AvgBytesPerSec", "BitsPerSample",
    # NOTE: "Duration" intentionally excluded — wrong values from memory stream
]

AUDIO_FORMAT_MAP = {
    ".wav": "wav", ".mp3": "mp3", ".m4a": "mp4", ".mp4": "mp4",
}

class AudioConverter(DocumentConverter):
    def accepts(self, stream, stream_info, **kwargs):
        ext = (stream_info.extension or "").lower()
        mime = stream_info.mimetype or ""
        return ext in AUDIO_FORMAT_MAP or any(
            mime.startswith(m) for m in ("audio/wav", "audio/mpeg", "audio/mp4", "video/mp4")
        )

    def convert(self, stream, stream_info, **kwargs):
        audio_bytes = stream.read()
        ext = (stream_info.extension or ".mp3").lower()
        fmt = AUDIO_FORMAT_MAP.get(ext, "mp3")
        parts = []

        # Layer 1: metadata via exiftool
        metadata = _run_exiftool(audio_bytes, AUDIO_EXIF_FIELDS)
        for key, value in metadata.items():
            parts.append(f"**{key}**: {value}")

        # Layer 2: transcription
        try:
            transcript = _transcribe_audio(audio_bytes, fmt)
            if transcript:
                parts.append(f"\n## Transcript\n{transcript}")
        except MissingDependencyException:
            pass  # speech_recognition not installed — skip silently

        return DocumentConverterResult(text_content="\n".join(parts))


def _transcribe_audio(audio_bytes: bytes, fmt: str) -> str:
    try:
        import speech_recognition as sr
    except ImportError:
        raise MissingDependencyException("speech_recognition")

    recognizer = sr.Recognizer()

    # speech_recognition needs a temp file for non-WAV formats
    if fmt == "wav":
        with sr.AudioFile(BytesIO(audio_bytes)) as source:
            audio = recognizer.record(source)
    else:
        suffix = f".{fmt}"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        try:
            with sr.AudioFile(tmp_path) as source:
                audio = recognizer.record(source)
        finally:
            os.unlink(tmp_path)

    return recognizer.recognize_google(audio)  # uses Google Web Speech API
```

## Data contracts

- **Input**: WAV/MP3/M4A/MP4 bytes in stream; extension used to select decoder format
- **Output**: Markdown — EXIF metadata key-values at top, then `## Transcript` section with speech text
- **Duration field**: intentionally omitted — exiftool returns incorrect values when audio is provided as a stream (not file path)

## Dependencies & assumptions

```
# exiftool: system binary (same as image converter)
SpeechRecognition >= 3.10   # Python package: pip install SpeechRecognition
pydub >= 0.25               # required by SpeechRecognition for MP3/M4A decoding
ffmpeg                      # system binary required by pydub
```
`recognize_google()` uses Google's free Web Speech API — requires internet, sends audio data externally.

## To port this, you need:

- [ ] `accepts()` matching by extension (`.wav`, `.mp3`, `.m4a`, `.mp4`) and MIME
- [ ] `_run_exiftool(bytes, fields)` — same pattern as [[image-llm-captioning--from-markitdown]], different field list
- [ ] `_transcribe_audio(bytes, fmt)` — WAV uses `BytesIO` directly; other formats need temp file
- [ ] `AUDIO_EXIF_FIELDS` list (without Duration)
- [ ] `MissingDependencyException` catch around transcription so metadata still returns if SR not installed
- [ ] `os.unlink(tmp_path)` in finally block for temp file cleanup

## Gotchas

- `speech_recognition.AudioFile` does NOT reliably accept `BytesIO` for MP3/M4A — it needs a real file path for non-WAV formats. The temp file is not optional; it's a known limitation of the library.
- `recognize_google()` is free but rate-limited and sends audio to Google. For private audio, configure a local recognizer (e.g., `recognize_sphinx()` for offline, or a self-hosted Whisper endpoint).
- Duration is wrong from exiftool when reading from stdin/stream (not a file path). This is a known exiftool limitation.
- `pydub` + `ffmpeg` are required for MP3/M4A decoding. If ffmpeg is missing, `speech_recognition` will fail on non-WAV files with an unhelpful error.

## Origin

https://github.com/microsoft/markitdown — `converters/_audio_converter.py`, `converters/_transcribe_audio.py`, `converters/_exiftool.py`
