# Domain: media-processing

Extracting text, metadata, and AI-generated descriptions from binary media files (images, audio) for use in text pipelines.

## What this domain is about

Media files (images, audio recordings) are opaque to language models by default. This domain covers the patterns for making them legible: extracting embedded metadata (EXIF, ID3 tags) via tools like exiftool, transcribing audio via speech recognition, and generating natural-language descriptions of images via LLM vision APIs.

## Key pattern: optional enhancement

Both features in this domain follow the same enhancement pattern: base conversion always works (produces whatever metadata is available), and richer output is layered in when optional dependencies (exiftool, speech_recognition, LLM client) are present. Missing dependencies raise `MissingDependencyException`, which the caller catches gracefully.

## Features in this domain

- [[image-llm-captioning--from-markitdown]] — EXIF extraction + LLM vision captioning for images
- [[audio-transcription--from-markitdown]] — speech_recognition transcription + exiftool metadata for audio
- [[screen-capture-self-exclusion--from-clicky]] — ScreenCaptureKit single-frame capture of every display that filters out the app's own windows by bundle id (so an AI never sees its own overlays), returning cursor-screen-first labeled JPEGs and reconciling the CG-vs-AppKit multi-monitor coordinate mismatch.
- [[push-to-talk-streaming-transcription--from-clicky]] — a global modifier-only hotkey (listen-only CGEvent tap) driving AVAudioEngine push-to-talk into a pluggable provider protocol; default AssemblyAI v3 streams 16kHz PCM16 over WebSocket with turn-stitching, with Apple Speech and OpenAI batch as fallbacks. Live realtime STT vs markitdown's file-at-rest transcription.
