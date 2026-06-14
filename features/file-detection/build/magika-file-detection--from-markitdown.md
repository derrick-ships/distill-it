# Content-Aware File Detection / Magika (build spec) — distilled from markitdown

## Summary

Layered file type detection producing a ranked list of `StreamInfo` candidates. Layer 1: parse available hints (filename extension, explicit MIME). Layer 2: bidirectional `mimetypes` enrichment. Layer 3: Magika ML content scan. Layer 4: charset detection for text files. Returns `[magika_guess, hint_guess]` ordered most-confident first.

## Core logic (inlined)

```python
import mimetypes
from pathlib import Path
from typing import List, Optional
import charset_normalizer

# Optional — graceful degradation if not installed
try:
    from magika import Magika
    _magika = Magika()
except ImportError:
    _magika = None

def get_stream_info_guesses(
    stream,                       # BinaryIO, seekable
    base_hint: StreamInfo,        # whatever the caller knows
) -> List[StreamInfo]:
    guesses = []

    # ---- Layer 1+2: hint-based + mimetypes enrichment ----
    hint = base_hint

    # extension → mimetype
    if hint.mimetype is None and hint.extension:
        guessed_mime, _ = mimetypes.guess_type("placeholder" + hint.extension, strict=False)
        if guessed_mime:
            hint = hint.copy_and_update(mimetype=guessed_mime)

    # mimetype → extension
    if hint.extension is None and hint.mimetype:
        exts = mimetypes.guess_all_extensions(hint.mimetype, strict=False)
        if exts:
            hint = hint.copy_and_update(extension=exts[0])

    # ---- Layer 3: Magika ML scan ----
    magika_guess: Optional[StreamInfo] = None
    if _magika is not None:
        stream.seek(0)
        result = _magika.identify_stream(stream)
        stream.seek(0)
        if result.status == "ok" and result.prediction.output.label != "unknown":
            pred = result.prediction.output
            ext = "." + pred.extensions[0] if pred.extensions else None
            mime = pred.mime_type if hasattr(pred, "mime_type") else None
            magika_info = hint.copy_and_update(extension=ext, mimetype=mime)

            # ---- Layer 4: charset for text files ----
            if pred.is_text:
                stream.seek(0)
                sample = stream.read(4096)
                stream.seek(0)
                charset_result = charset_normalizer.from_bytes(sample).best()
                if charset_result:
                    charset = _normalize_charset(str(charset_result.encoding))
                    magika_info = magika_info.copy_and_update(charset=charset)

            magika_guess = magika_info

    # Build ordered list: Magika first (more confident), hint second
    if magika_guess:
        guesses.append(magika_guess)
    guesses.append(hint)
    return guesses

def _normalize_charset(encoding: str) -> str:
    # Normalize charset aliases to standard names
    mapping = {"utf_8": "utf-8", "utf_16": "utf-16", "iso8859_1": "latin-1"}
    return mapping.get(encoding.lower().replace("-", "_"), encoding)
```

## Data contracts

- **Input**: seekable `BinaryIO` stream + `StreamInfo` base hint
- **Output**: `List[StreamInfo]` ordered most-confident first; always at least 1 element (the hint)
- `StreamInfo` fields: `mimetype: str`, `extension: str` (with dot), `charset: str`, `filename: str`, `url: str`, `local_path: str` — all optional

## Dependencies & assumptions

```
magika >= 0.5         # optional; graceful fallback if absent
charset-normalizer >= 3.0   # optional; for charset detection on text files
```

## To port this, you need:

- [ ] `StreamInfo` frozen dataclass with `copy_and_update()` (from [[converter-pipeline--from-markitdown]])
- [ ] `mimetypes.guess_type()` and `mimetypes.guess_all_extensions()` calls for bidirectional enrichment
- [ ] `Magika().identify_stream(stream)` call with `seek(0)` before and after
- [ ] `charset_normalizer.from_bytes(sample).best()` for text file charset detection
- [ ] `_normalize_charset()` to canonicalize encoding names
- [ ] Graceful `ImportError` handling for both `magika` and `charset_normalizer`
- [ ] The function returns a LIST — the dispatch loop tries each in order

## Gotchas

- Always `seek(0)` before Magika and again after — Magika reads the stream.
- `mimetypes` module is locale-sensitive on some systems. Call `mimetypes.init()` once at startup if you need reliable cross-platform behavior.
- Magika's `pred.extensions` is a list; take index 0. It may be empty for unusual types.
- The empty `StreamInfo()` fallback in the dispatch loop (see [[converter-pipeline--from-markitdown]]) is the safety net — this function only needs to return its best guesses.

## Origin

https://github.com/microsoft/markitdown — `packages/markitdown/src/markitdown/_markitdown.py` (`_get_stream_info_guesses`), `_stream_info.py`
