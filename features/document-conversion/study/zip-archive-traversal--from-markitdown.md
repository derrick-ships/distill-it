# ZIP Archive Traversal — from [markitdown](https://github.com/microsoft/markitdown)

> Domain: [[_domain]] · Source: https://github.com/microsoft/markitdown · NotebookLM:

## What it does

Converts a ZIP archive into Markdown by recursively unpacking each contained file and converting it with the appropriate converter. The output is a single Markdown document with each file's content under a `## File: path/to/file.ext` header.

## Why it exists

ZIP archives are common containers in data pipelines: exported datasets, bundled documents, deliverable packages. Being able to convert an entire ZIP into Markdown without manually unpacking it makes bulk processing much simpler. The killer feature is recursion: a ZIP containing another ZIP, or a ZIP containing a PPTX with embedded images, all gets handled transparently.

## How it actually works

The ZipConverter accepts `.zip` files or any MIME type starting with `application/zip`. When it runs:

1. It opens the archive using Python's built-in `zipfile.ZipFile`.
2. It iterates through all entries using `namelist()`.
3. For each file, it extracts it into a `BytesIO` stream (never to disk) and creates a `StreamInfo` with the filename. This gives the pipeline enough metadata to guess the file type by extension.
4. It calls the parent MarkItDown instance's `_convert()` method on each stream — so the full pipeline runs recursively, picking the right converter for each file type.
5. Results are concatenated under `## File: <path>` headers.
6. Files that fail to convert (unsupported format or conversion error) are silently skipped — the archive traversal continues.

The recursive call to the parent MarkItDown means the ZipConverter doesn't need to know about any other file type. All format-specific logic lives in the appropriate specialist converter.

## The non-obvious parts

- Files are extracted to `BytesIO`, not disk. This keeps the operation fully in-memory and avoids temp file cleanup.
- Silent skipping of failed files is intentional — a corrupt file inside a ZIP shouldn't abort conversion of the rest of the archive.
- Nested ZIPs work because `_convert()` will encounter the inner ZIP file and route it back through ZipConverter again.

## Related

- [[converter-pipeline--from-markitdown]] — the parent that ZipConverter calls recursively
