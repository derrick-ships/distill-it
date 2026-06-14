# Audio Transcription — from [markitdown](https://github.com/microsoft/markitdown)

> Domain: [[_domain]] · Source: https://github.com/microsoft/markitdown · NotebookLM:

## What it does

Converts audio files (WAV, MP3, M4A, MP4) into Markdown containing the transcribed speech plus embedded metadata (title, artist, album, genre, bitrate, etc.). Transcription uses the `speech_recognition` library; metadata uses the `exiftool` binary. Both are optional — the converter gracefully degrades if either is absent.

## Why it exists

Audio is completely opaque to text LLMs. Meeting recordings, podcast episodes, and voice memos become useful the moment they're transcribed. Pairing transcription with metadata (who recorded it, when, what album/artist it belongs to) gives downstream models richer context without requiring separate preprocessing steps.

## How it actually works

**Metadata extraction:** If `exiftool` is available, the converter extracts these fields: `Title`, `Artist`, `Author`, `Band`, `Album`, `Genre`, `Track`, `DateTimeOriginal`, `CreateDate`, `NumChannels`, `SampleRate`, `AvgBytesPerSec`, `BitsPerSample`. (Duration is intentionally excluded — exiftool returns incorrect values for duration when reading from a memory stream.) These appear at the top of the Markdown output as key-value pairs.

**Transcription:** The `transcribe_audio()` function (in `_transcribe_audio.py`) takes the stream and a format hint (`"wav"`, `"mp3"`, or `"mp4"`) and uses `speech_recognition` to transcribe the audio. If `speech_recognition` is not installed, a `MissingDependencyException` is raised, which the AudioConverter catches and handles — the rest of the output (metadata) is still returned.

**Output structure:** The result is a Markdown block with metadata at the top (from exiftool), followed by the transcription text.

## The non-obvious parts

- `speech_recognition` by default uses Google's free Web Speech API under the hood. This requires internet access and sends audio to Google's servers. For sensitive audio, users should configure a local recognition engine.
- Duration is intentionally omitted from exiftool extraction. This is a specific known issue: exiftool misreports duration when the audio is provided as a stream rather than a file path.
- The format hint (`"wav"`, `"mp3"`, `"mp4"`) passed to `transcribe_audio` is derived from the stream's extension — it's needed because speech_recognition needs to know how to decode the bytes.

## Related

- [[converter-pipeline--from-markitdown]] — dispatches to this converter
- [[image-llm-captioning--from-markitdown]] — shares the exiftool metadata extraction pattern
