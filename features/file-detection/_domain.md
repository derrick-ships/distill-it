# Domain: file-detection

Determining a file's true type from content, extension, MIME type hints, and ML-based identification — without trusting the filename alone.

## What this domain is about

File type detection is the problem of reliably identifying what a byte stream actually contains. Extensions lie, MIME types from HTTP headers may be generic (`application/octet-stream`), and user-supplied metadata is untrustworthy. Robust detection stacks multiple signals: standard library MIME guessing, magic-byte sniffing, and ML-based content classification.

## Signals used in this domain

1. **File extension** — fast, unreliable
2. **MIME type** — from OS library or HTTP headers, unreliable for unknown types
3. **Magic bytes** — first bytes of the stream identify format class
4. **ML content classification** (Magika) — trained on file content, highest accuracy

## Features in this domain

- [[magika-file-detection--from-markitdown]] — layered detection pipeline using mimetypes + Magika ML model
