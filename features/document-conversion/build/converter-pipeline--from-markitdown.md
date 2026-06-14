# Converter Pipeline Architecture (build spec) — distilled from markitdown

## Summary

A priority-sorted, pluggable converter dispatch engine. Accepts any source (file path, URL, HTTP response, byte stream), normalizes it to a binary stream + StreamInfo metadata, runs layered type detection, then tries registered converters in priority order until one succeeds. Returns a `DocumentConverterResult` with normalized Markdown.

## Core logic (inlined)

```python
# Data contracts
@dataclass(frozen=True, kw_only=True)
class StreamInfo:
    mimetype: Optional[str] = None
    extension: Optional[str] = None   # includes dot: ".pdf"
    charset: Optional[str] = None
    filename: Optional[str] = None
    local_path: Optional[str] = None
    url: Optional[str] = None

    def copy_and_update(self, *others, **kwargs) -> "StreamInfo":
        # merge non-None fields from others + kwargs into a new instance
        ...

@dataclass
class DocumentConverterResult:
    text_content: str   # the Markdown output
    title: Optional[str] = None

# Converter interface (abstract base)
class DocumentConverter(ABC):
    def accepts(self, stream: BinaryIO, stream_info: StreamInfo, **kwargs) -> bool: ...
    def convert(self, stream: BinaryIO, stream_info: StreamInfo, **kwargs) -> DocumentConverterResult: ...

# Priority constants
PRIORITY_SPECIFIC_FILE_FORMAT = 0.0   # tried first
PRIORITY_GENERIC_FILE_FORMAT  = 10.0  # fallback

@dataclass(frozen=True, kw_only=True)
class ConverterRegistration:
    converter: DocumentConverter
    priority: float
```

```python
# Registration
def register_converter(self, converter, *, priority=PRIORITY_SPECIFIC_FILE_FORMAT):
    self._converters.insert(0, ConverterRegistration(converter=converter, priority=priority))
    # Note: insert at 0, then stable-sort by priority at dispatch time.
    # Last-registered wins among equal-priority converters.
```

```python
# Main dispatch loop
def _convert(self, *, file_stream, stream_info_guesses, **kwargs):
    sorted_registrations = sorted(self._converters, key=lambda x: x.priority)
    failed_attempts = []

    for stream_info in stream_info_guesses + [StreamInfo()]:  # empty StreamInfo as final fallback
        for reg in sorted_registrations:
            file_stream.seek(0)
            if reg.converter.accepts(file_stream, stream_info, **kwargs):
                file_stream.seek(0)
                try:
                    res = reg.converter.convert(file_stream, stream_info, **kwargs)
                    # normalize: strip trailing whitespace per line
                    res.text_content = "\n".join(
                        line.rstrip() for line in res.text_content.splitlines()
                    )
                    return res
                except Exception as e:
                    failed_attempts.append((reg.converter, stream_info, e))

    raise UnsupportedFormatException(failed_attempts)
```

```python
# Source normalization entry point
def convert(self, source, *, stream_info=None, **kwargs):
    if isinstance(source, str):
        if source.startswith(("http:", "https:", "file:", "data:")):
            return self.convert_uri(source, stream_info=stream_info, **kwargs)
        else:
            return self.convert_local(source, stream_info=stream_info, **kwargs)
    elif isinstance(source, Path):
        return self.convert_local(source, stream_info=stream_info, **kwargs)
    elif isinstance(source, requests.Response):
        return self.convert_response(source, stream_info=stream_info, **kwargs)
    else:  # BinaryIO
        return self.convert_stream(source, stream_info=stream_info, **kwargs)
```

## Data contracts

- **Input**: any of `str` (path or URL), `pathlib.Path`, `requests.Response`, `BinaryIO`
- **Output**: `DocumentConverterResult.text_content` — Markdown string, trailing whitespace stripped per line, `\r\n` normalized to `\n`
- **StreamInfo**: immutable, all fields optional, used as hints not guarantees

## Dependencies & assumptions

- Python 3.10+
- `requests` for URL fetching
- `magika` (optional) for ML-based type detection — see build spec for [[magika-file-detection--from-markitdown]]
- `charset_normalizer` (optional) for charset detection

## To port this, you need:

- [ ] `DocumentConverter` ABC with `accepts()` and `convert()` methods
- [ ] `StreamInfo` frozen dataclass with `copy_and_update()`
- [ ] `DocumentConverterResult` dataclass with `text_content: str`
- [ ] `ConverterRegistration` dataclass wrapping converter + float priority
- [ ] `MarkItDown.__init__()` that builds `self._converters: list[ConverterRegistration]` and registers built-ins
- [ ] `register_converter()` with priority param
- [ ] `_convert()` dispatch loop (sort → iterate stream_info guesses → iterate converters → first accepts+succeeds wins)
- [ ] `convert()` source-type dispatch
- [ ] `convert_local()`, `convert_uri()`, `convert_response()`, `convert_stream()` — each opens a stream and calls `_convert()`
- [ ] `_get_stream_info_guesses()` — type detection, see [[magika-file-detection--from-markitdown]] build spec
- [ ] Plugin loading via `enable_plugins` flag — see [[plugin-system--from-markitdown]] build spec

## Gotchas

- Always `seek(0)` before calling `accepts()` and again before `convert()` — stream position is not reset automatically.
- The empty `StreamInfo()` at the end of the guesses list is important: it lets PlainTextConverter (registered at priority 10.0) catch anything that slipped through.
- Output normalization (`\r\n` → `\n`, strip trailing whitespace) must happen at the pipeline level, not in individual converters.
- `convert_local()` is safer than `convert()` for untrusted input — it won't follow HTTP URLs.

## Origin

https://github.com/microsoft/markitdown — `packages/markitdown/src/markitdown/_markitdown.py`, `_base_converter.py`, `_stream_info.py`, `_exceptions.py`
