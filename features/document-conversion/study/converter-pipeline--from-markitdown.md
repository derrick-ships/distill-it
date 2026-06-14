# Converter Pipeline Architecture — from [markitdown](https://github.com/microsoft/markitdown)

> Domain: [[_domain]] · Source: https://github.com/microsoft/markitdown · NotebookLM:

## What it does

MarkItDown's converter pipeline is the engine that takes any input — a file path, URL, HTTP response, or raw byte stream — and routes it through the right converter to produce Markdown. You call `md.convert("file.pdf")` and the pipeline figures out that it's a PDF, picks the PDF converter, runs it, and hands you back a Markdown string.

## Why it exists

The core problem is heterogeneity: LLM workflows need to consume dozens of different file types, but no single library handles all of them. The pipeline exists to give a single, uniform entry point (`convert(source)`) that dispatches to the right specialist behind the scenes. Adding a new format means adding one converter class — you don't touch the dispatch logic.

## How it actually works

When you call `convert()`, three things happen in sequence:

**1. Source normalization.** The method inspects what you passed in. A string starting with `http:` or `https:` goes to `convert_uri()`. A plain string goes to `convert_local()`. A `Path` object goes to `convert_local()`. A `requests.Response` goes to `convert_response()`. Each of these opens the source as a binary stream and bundles metadata (filename, URL, MIME type from headers, etc.) into a `StreamInfo` object.

**2. Type detection.** The pipeline calls `_get_stream_info_guesses()`, which produces a ranked list of StreamInfo candidates. It starts with whatever hints are available (extension from filename, MIME type from HTTP headers), then enriches them using the standard `mimetypes` library and Google's Magika ML model. For text files, it also runs charset detection. See [[magika-file-detection--from-markitdown]] for details.

**3. Converter dispatch.** The internal `_convert()` method sorts all registered converters by their priority value (lower = higher priority). It then tries each `StreamInfo` candidate in order. For each candidate, it iterates through converters calling `converter.accepts(stream, stream_info)`. The first converter that returns True gets to call `convert()`. If that conversion fails (exception), the next converter is tried. The loop exits when one succeeds, or raises `UnsupportedFormatException` if all fail.

**Output normalization:** Every result's `text_content` gets trailing whitespace stripped per line, producing consistent output regardless of which converter produced it.

**Plugin support:** Before dispatch, plugins registered via `enable_plugins=True` have already injected their converters into the same list. They're indistinguishable from built-in converters at dispatch time.

## The non-obvious parts

- The priority system uses floats, not integers. `PRIORITY_SPECIFIC_FILE_FORMAT = 0.0`, `PRIORITY_GENERIC_FILE_FORMAT = 10.0`. Lower value = higher priority = tried first. The PlainTextConverter registers at 10.0 so it only runs if nothing more specific accepted the file.
- `register_converter()` inserts at position 0, then sorting by priority applies. Last-registered wins among equal-priority converters (stable sort preserves insertion order, and newer ones are at position 0).
- `convert_local()` is safer than `convert()` for untrusted input — it won't follow URLs. `convert_stream()` is safest — it takes only a raw stream with no I/O.
- The `StreamInfo` carries hints, not truth. Magika or charset detection may override the extension-derived MIME type.

## Related

- [[magika-file-detection--from-markitdown]] — the type detection step
- [[plugin-system--from-markitdown]] — how external converters enter the pipeline
- [[pdf-conversion--from-markitdown]], [[office-doc-conversion--from-markitdown]] — example specialist converters
