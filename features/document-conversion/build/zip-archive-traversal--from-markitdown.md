# ZIP Archive Traversal (build spec) — distilled from markitdown

## Summary

Opens a ZIP archive in-memory, iterates all entries, extracts each to a `BytesIO` stream, and recursively runs the parent MarkItDown pipeline on each file. Results are concatenated under `## File: path` headers. Failed files are silently skipped.

## Core logic (inlined)

```python
import zipfile
from io import BytesIO

class ZipConverter(DocumentConverter):
    def __init__(self, markitdown_instance):
        self._md = markitdown_instance  # reference to parent for recursive calls

    def accepts(self, stream, stream_info, **kwargs):
        return (
            (stream_info.mimetype or "").startswith("application/zip")
            or (stream_info.extension or "").lower() == ".zip"
        )

    def convert(self, stream, stream_info, **kwargs):
        parts = []
        with zipfile.ZipFile(stream) as zf:
            for name in zf.namelist():
                # Skip directories
                if name.endswith("/"):
                    continue
                try:
                    file_bytes = zf.read(name)
                    file_stream = BytesIO(file_bytes)
                    # Build StreamInfo so child pipeline can detect type by extension
                    child_info = StreamInfo(filename=name, extension=Path(name).suffix or None)
                    result = self._md._convert(
                        file_stream=file_stream,
                        stream_info_guesses=[child_info],
                        **kwargs
                    )
                    parts.append(f"## File: {name}\n\n{result.text_content}")
                except (UnsupportedFormatException, FileConversionException):
                    pass  # silently skip unconvertible files
        return DocumentConverterResult(text_content="\n\n---\n\n".join(parts))
```

## Data contracts

- **Input**: binary stream of a ZIP file; any MIME starting with `application/zip` or `.zip` extension
- **Output**: Markdown with `## File: <path>` sections, one per successfully converted file
- Each section's content is whatever the appropriate converter produced for that file type

## Dependencies & assumptions

- Python `zipfile` module (stdlib — no extra install)
- Requires reference to parent `MarkItDown` instance so recursive `_convert()` can be called
- All other format converters must already be registered on the parent instance

## To port this, you need:

- [ ] Access to the parent pipeline's `_convert()` method (or equivalent dispatch)
- [ ] `StreamInfo` with `filename` and `extension` fields (for child type detection)
- [ ] `UnsupportedFormatException` and `FileConversionException` as catchable types
- [ ] `BytesIO` stream extraction (no temp files needed — all in-memory)
- [ ] Directory entry skip (`name.endswith("/")`)

## Gotchas

- Never extract to disk — use `BytesIO(zf.read(name))`. Disk extraction requires temp dir cleanup and has security implications (zip slip attack if not validated).
- Zip slip: if the ZIP contains entries with `../` in the name, `zf.read(name)` is safe (it reads bytes), but passing the name to any disk path operation is not. Since we use BytesIO only, this is not an issue here.
- Nested ZIPs work automatically because the child pipeline will route inner `.zip` files back through `ZipConverter`.
- Large ZIP entries are fully loaded into RAM before conversion. For very large files inside ZIPs this could be a problem.

## Origin

https://github.com/microsoft/markitdown — `packages/markitdown/src/markitdown/converters/_zip_converter.py`
