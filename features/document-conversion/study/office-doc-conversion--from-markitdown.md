# Office Document Conversion (DOCX / PPTX / XLSX) — from [markitdown](https://github.com/microsoft/markitdown)

> Domain: [[_domain]] · Source: https://github.com/microsoft/markitdown · NotebookLM:

## What it does

Converts Microsoft Office documents — Word (.docx), PowerPoint (.pptx), and Excel (.xlsx/.xls) — into structured Markdown. Each format gets a dedicated converter that understands the native structure: Word becomes headed paragraphs, PowerPoint becomes per-slide sections with titles and notes, Excel becomes per-sheet Markdown tables.

## Why it exists

Office formats are ubiquitous in enterprise workflows. Feeding a Word document or a spreadsheet directly to an LLM is impractical; converting them to Markdown gives the model semantic structure (headings, tables, lists) without the XML noise of the native formats.

## How it actually works

**DOCX (python-docx):** The DocxConverter reads the document using python-docx, which parses the underlying Open XML. It iterates through the document body, handling paragraphs and tables. Paragraphs are converted using a helper that maps Word heading styles to Markdown heading levels (`# H1`, `## H2`, etc.). Tables go through an intermediate step: they're rendered as HTML, then the HtmlConverter converts that HTML to Markdown. This reuse of the HTML converter avoids duplicating table formatting logic.

**PPTX (python-pptx):** The PptxConverter processes slides one by one. For each slide it extracts: the title (as a `#` heading), body text frames, embedded images (with optional LLM captions), tables (via the HTML→Markdown path), charts (rendered as Markdown tables of categories/values), and speaker notes (as `### Notes:` sections). Slides are separated by HTML comments for reference. Images can be output as base64 data URIs (`keep_data_uris=True`) or as placeholder filenames.

**XLSX / XLS (pandas + openpyxl/xlrd):** The XlsxConverter reads all sheets using `pd.read_excel(sheet_name=None)` which returns a dict of DataFrames. Each sheet becomes a `## SheetName` section followed by the sheet's data as a Markdown table (again via the HTML→Markdown path). XLSX uses openpyxl, XLS uses xlrd.

## The non-obvious parts

- All three converters reuse the HtmlConverter's `convert_string()` method for table formatting — tables are rendered as HTML then converted. This keeps table logic in one place.
- PPTX charts are handled specially: the converter extracts the underlying data series and categories from the chart XML and renders them as a Markdown table. Unsupported chart types get a `[unsupported chart]` placeholder.
- LLM captioning in PPTX is the same path as [[image-llm-captioning--from-markitdown]] — it passes the image bytes to an OpenAI-compatible vision API if configured.

## Related

- [[converter-pipeline--from-markitdown]] — dispatches to these converters
- [[image-llm-captioning--from-markitdown]] — reused inside PptxConverter for slide images
- [[html-web-conversion--from-markitdown]] — HtmlConverter is reused for table formatting
