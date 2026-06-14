# Content-Aware File Detection (Magika) — from [markitdown](https://github.com/microsoft/markitdown)

> Domain: [[_domain]] · Source: https://github.com/microsoft/markitdown · NotebookLM:

## What it does

Before a file is handed to any converter, MarkItDown runs a layered detection pipeline that figures out what the file actually is — not just what its name says. It stacks three signals: filename hints (extension + MIME type), the standard Python `mimetypes` library for bidirectional extension↔MIME mapping, and Google's Magika ML model for content-based classification. The result is a ranked list of `StreamInfo` guesses, most-confident first.

## Why it exists

Files lie. A file named `report.pdf` might actually be an HTML page. An HTTP response might come with `Content-Type: application/octet-stream` because the server doesn't know what it is. For a conversion pipeline that routes on file type, bad detection means the wrong converter gets called and produces garbage. Magika was built by Google to solve exactly this problem — ML trained on hundreds of millions of files.

## How it actually works

Detection happens in `_get_stream_info_guesses()`, which returns a list of `StreamInfo` objects in confidence order:

**Step 1 — Collect hints.** Whatever the caller knows about the file is bundled into a base `StreamInfo`: filename (for extension extraction), MIME type from HTTP headers, explicit overrides if the user passed `stream_info=`.

**Step 2 — Bidirectional MIME↔extension enrichment.** Using Python's `mimetypes` module, if the extension is known but MIME type isn't, it guesses the MIME. If MIME is known but extension isn't, it guesses the extension. This fills in whichever half of the pair is missing.

**Step 3 — Magika content scan.** The stream is passed to `magika.identify_stream()`. Magika reads the file content (not just the header bytes — it uses a deep learning model trained on full-file content patterns) and returns a predicted file type with a label, confidence score, and a list of known extensions for that type. If the prediction is not `"unknown"`, it produces a new `StreamInfo` with the Magika-derived extension and MIME type.

**Step 4 — Charset detection (text files).** If Magika identifies the file as text, the converter reads the first 4096 bytes and runs `charset_normalizer` to detect encoding (UTF-8, latin-1, etc.). The charset is stored in `StreamInfo.charset`, which converters use when decoding the byte stream.

**Step 5 — Emit candidates.** The function returns a list: Magika's guess (if any) first, then the hint-based guess. The pipeline's dispatch loop tries each candidate in order — so if Magika is confident, its type is tried first.

## The non-obvious parts

- Magika is an optional dependency. If it's not installed, the pipeline falls back to extension + MIME hints only. This degrades gracefully.
- Magika reads stream content, which means the stream position must be reset to 0 after Magika runs. The code does this explicitly.
- charset_normalizer only runs on files Magika identifies as text. For binary files, charset is left None and converters handle binary I/O themselves.
- The `StreamInfo` is immutable (frozen dataclass). Updates create new instances via `copy_and_update()`.

## Related

- [[converter-pipeline--from-markitdown]] — consumes these StreamInfo guesses for dispatch
