# Office Document Conversion DOCX/PPTX/XLSX (build spec) — distilled from markitdown

## Summary

Three converters — one per Office format — each reading native XML via python-docx / python-pptx / pandas+openpyxl. Tables in all three formats go through an HTML→Markdown round-trip using the HtmlConverter's `convert_string()` method. PPTX additionally supports LLM image captioning for embedded images.

## Core logic (inlined)

### DOCX

```python
class DocxConverter(DocumentConverter):
    def accepts(self, stream, stream_info, **kwargs):
        return stream_info.mimetype == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" \
            or (stream_info.extension or "").lower() == ".docx"

    def convert(self, stream, stream_info, **kwargs):
        doc = docx.Document(stream)
        parts = []
        for block in doc.element.body:
            if block.tag.endswith("}p"):      # paragraph
                para = docx.text.paragraph.Paragraph(block, doc)
                md = self._para_to_md(para)
                if md: parts.append(md)
            elif block.tag.endswith("}tbl"):  # table
                table = docx.table.Table(block, doc)
                html = self._table_to_html(table)
                parts.append(html_converter.convert_string(html))
        return DocumentConverterResult(text_content="\n\n".join(parts))

    def _para_to_md(self, para) -> str:
        style = para.style.name.lower()
        text = para.text.strip()
        if not text: return ""
        if "heading 1" in style: return f"# {text}"
        if "heading 2" in style: return f"## {text}"
        if "heading 3" in style: return f"### {text}"
        return text
```

### PPTX

```python
class PptxConverter(DocumentConverter):
    def convert(self, stream, stream_info, **kwargs):
        prs = pptx.Presentation(stream)
        parts = []
        for slide_num, slide in enumerate(prs.slides, 1):
            parts.append(f"<!-- Slide {slide_num} -->")
            for shape in slide.shapes:
                if shape.has_text_frame:
                    if shape.shape_type == MSO_SHAPE_TYPE.TITLE:
                        parts.append(f"# {shape.text_frame.text}")
                    else:
                        parts.append(shape.text_frame.text)
                elif shape.has_table:
                    html = self._table_to_html(shape.table)
                    parts.append(html_converter.convert_string(html))
                elif shape.has_chart:
                    parts.append(self._chart_to_md(shape.chart))
                elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                    parts.append(self._image_to_md(shape, kwargs))
            # Speaker notes
            if slide.has_notes_slide:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes: parts.append(f"### Notes:\n{notes}")
        return DocumentConverterResult(text_content="\n\n".join(parts))

    def _image_to_md(self, shape, kwargs) -> str:
        alt_text = shape._element.nvPicPr.cNvPr.get("descr", "")
        llm_caption = llm_caption_helper(shape.image.blob, kwargs)  # optional
        caption = " ".join(filter(None, [llm_caption, alt_text]))
        return f"![{caption}](placeholder.png)"
```

### XLSX

```python
class XlsxConverter(DocumentConverter):
    def convert(self, stream, stream_info, **kwargs):
        sheets = pd.read_excel(stream, sheet_name=None, engine="openpyxl")
        parts = []
        for name, df in sheets.items():
            parts.append(f"## {name}")
            html = df.to_html(index=False)
            parts.append(html_converter.convert_string(html))
        return DocumentConverterResult(text_content="\n\n".join(parts))
```

## Data contracts

- **DOCX input**: `application/vnd.openxmlformats-officedocument.wordprocessingml.document` / `.docx`
- **PPTX input**: `application/vnd.openxmlformats-officedocument.presentationml.presentation` / `.pptx`
- **XLSX input**: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` / `.xlsx`
- **XLS input**: `application/vnd.ms-excel` / `.xls` (uses `xlrd` engine instead of `openpyxl`)
- **Output**: Markdown string — headings, paragraphs, tables, slide separators

## Dependencies & assumptions

```
python-docx >= 1.1
python-pptx >= 1.0
pandas >= 2.0
openpyxl >= 3.1    # for xlsx
xlrd >= 2.0        # for xls
```
Requires `HtmlConverter.convert_string()` available from [[html-web-conversion--from-markitdown]].

## To port this, you need:

- [ ] `python-docx`, `python-pptx`, `pandas`, `openpyxl` installed
- [ ] `HtmlConverter.convert_string(html: str) -> str` helper for table rendering
- [ ] `_para_to_md()` mapping Word heading styles to `#`/`##`/`###`
- [ ] `_table_to_html()` shared helper — render table XML as HTML string
- [ ] PPTX: shape-type dispatch (text frame / table / chart / picture)
- [ ] PPTX: `_chart_to_md()` extracting series/category data from chart XML
- [ ] Optional: `llm_caption_helper()` for PPTX image shapes — see [[image-llm-captioning--from-markitdown]]
- [ ] XLSX: `pd.read_excel(sheet_name=None)` → dict of DataFrames → HTML → Markdown

## Gotchas

- PPTX charts with unsupported types (e.g., sunburst, waterfall) should emit `[unsupported chart]` rather than erroring.
- Word heading style names are locale-dependent (`"Heading 1"` in English, different in other Office locales). Normalize with `.lower()` and substring match.
- `page.close()` pattern from PDF doesn't apply here — python-docx/pptx load entirely into memory.
- XLS needs `xlrd` engine; XLSX needs `openpyxl`. Don't mix them — pandas will error.

## Origin

https://github.com/microsoft/markitdown — `converters/_docx_converter.py`, `_pptx_converter.py`, `_xlsx_converter.py`
