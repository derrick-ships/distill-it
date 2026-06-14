# Image Conversion + LLM Captioning (build spec) — distilled from markitdown

## Summary

JPEG/PNG converter with two optional enhancement layers: exiftool subprocess for EXIF metadata, and an OpenAI-compatible vision API call for image description. Both layers are optional and independently activated. Output is Markdown with metadata key-values and a `## Description` section.

## Core logic (inlined)

```python
import base64
import subprocess
from io import BytesIO

EXIF_FIELDS = [
    "ImageSize", "Title", "Caption", "Description", "Keywords",
    "Artist", "Author", "DateTimeOriginal", "CreateDate", "GPSPosition",
]

class ImageConverter(DocumentConverter):
    def accepts(self, stream, stream_info, **kwargs):
        ext = (stream_info.extension or "").lower()
        mime = stream_info.mimetype or ""
        return ext in (".jpg", ".jpeg", ".png") or mime in ("image/jpeg", "image/png")

    def convert(self, stream, stream_info, **kwargs):
        image_bytes = stream.read()
        parts = []

        # Layer 1: EXIF metadata via exiftool subprocess
        exif = _run_exiftool(image_bytes, EXIF_FIELDS)
        for key, value in exif.items():
            parts.append(f"**{key}**: {value}")

        # Layer 2: LLM vision captioning
        llm_client = kwargs.get("llm_client")
        llm_model = kwargs.get("llm_model")
        llm_prompt = kwargs.get("llm_prompt", "Write a detailed caption for this image.")
        if llm_client and llm_model:
            caption = _llm_caption(image_bytes, stream_info, llm_client, llm_model, llm_prompt)
            if caption:
                parts.append(f"\n## Description\n{caption}")

        return DocumentConverterResult(text_content="\n".join(parts))


def _run_exiftool(image_bytes: bytes, fields: list[str]) -> dict[str, str]:
    field_args = []
    for f in fields:
        field_args += [f"-{f}"]
    try:
        result = subprocess.run(
            ["exiftool", "-s", "-s", "-s"] + field_args + ["-"],
            input=image_bytes,
            capture_output=True,
        )
        output = {}
        for line in result.stdout.decode("utf-8", errors="replace").splitlines():
            if ": " in line:
                k, v = line.split(": ", 1)
                output[k.strip()] = v.strip()
        return output
    except (FileNotFoundError, Exception):
        return {}  # exiftool not installed or failed — silently skip


def _llm_caption(image_bytes, stream_info, client, model, prompt) -> str:
    ext = (stream_info.extension or ".jpg").lstrip(".")
    mime = stream_info.mimetype or f"image/{ext}"
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    data_uri = f"data:{mime};base64,{b64}"

    response = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ],
        }],
    )
    return response.choices[0].message.content
```

## Data contracts

- **Input**: JPEG or PNG bytes in stream; `stream_info.extension` or `.mimetype` for format hint
- **Output**: Markdown string — EXIF key-values (if exiftool available), then `## Description` + caption (if LLM configured)
- **kwargs consumed**: `llm_client` (OpenAI-compatible client), `llm_model` (str), `llm_prompt` (str, optional)
- **exiftool output format**: `-s -s -s` flag produces `FieldName: value` lines, one per field

## Dependencies & assumptions

```
# exiftool: system binary (brew install exiftool / apt install libimage-exiftool-perl)
# LLM client: any OpenAI-compatible (openai, anthropic with compatibility layer, etc.)
openai >= 1.0   # if using OpenAI directly
```

## To port this, you need:

- [ ] `accepts()` matching JPEG/PNG by extension or MIME
- [ ] `_run_exiftool(bytes, fields)` — subprocess call, `-s -s -s` for clean output, stdin piping, `FileNotFoundError` catch
- [ ] `_llm_caption(bytes, ...)` — base64 encode, build data URI, call `chat.completions.create` with image_url content part
- [ ] kwargs passthrough: `llm_client`, `llm_model`, `llm_prompt` read from kwargs
- [ ] Graceful degradation: both layers produce empty output if their dependency is absent

## Gotchas

- `exiftool` is a Perl binary, not a Python package. It must be on system PATH. Use `FileNotFoundError` catch around `subprocess.run`.
- `-s -s -s` (triple `-s`) gives the cleanest output format: `FieldName: value`. Single or double `-s` gives different indentation.
- The data URI approach means image bytes travel over the API as a base64 string. For large images, this can exceed token limits. Consider resizing before encoding for very large images.
- `llm_prompt` is intentionally user-configurable — different use cases want different questions ("describe the chart", "list visible text", "identify the people").

## Origin

https://github.com/microsoft/markitdown — `converters/_image_converter.py`, `converters/_exiftool.py`, `converters/_llm_caption.py`
