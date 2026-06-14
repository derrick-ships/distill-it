# Domain: media-processing

Extracting text, metadata, and AI-generated descriptions from binary media files (images, audio) for use in text pipelines.

## What this domain is about

Media files (images, audio recordings) are opaque to language models by default. This domain covers the patterns for making them legible: extracting embedded metadata (EXIF, ID3 tags) via tools like exiftool, transcribing audio via speech recognition, and generating natural-language descriptions of images via LLM vision APIs.

## Key pattern: optional enhancement

Both features in this domain follow the same enhancement pattern: base conversion always works (produces whatever metadata is available), and richer output is layered in when optional dependencies (exiftool, speech_recognition, LLM client) are present. Missing dependencies raise `MissingDependencyException`, which the caller catches gracefully.

## Features in this domain

- [[image-llm-captioning--from-markitdown]] — EXIF extraction + LLM vision captioning for images
- [[audio-transcription--from-markitdown]] — speech_recognition transcription + exiftool metadata for audio
