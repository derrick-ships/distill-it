# Azure Document Intelligence Integration (build spec) — distilled from markitdown

## Summary

Sends document bytes to Azure Document Intelligence's `prebuilt-layout` model and returns cleaned Markdown. Accepts PDFs, images (JPEG/PNG/BMP/TIFF), and Office files. OCR features (high-resolution, formulas, font styles) are enabled only for PDF and images. Output is Azure's native Markdown with HTML comments stripped.

## Core logic (inlined)

```python
import re
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import (
    AnalyzeDocumentRequest, DocumentAnalysisFeature, ContentFormat
)
from azure.core.credentials import AzureKeyCredential

# File types that get OCR analysis features
OCR_TYPES = {".pdf", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
OCR_MIMES = {"application/pdf", "image/jpeg", "image/png", "image/bmp", "image/tiff"}

class DocumentIntelligenceConverter(DocumentConverter):
    def __init__(self, endpoint: str, credential):
        # credential: AzureKeyCredential(api_key) or DefaultAzureCredential()
        self.client = DocumentIntelligenceClient(endpoint=endpoint, credential=credential)

    def accepts(self, stream, stream_info, **kwargs):
        ext = (stream_info.extension or "").lower()
        mime = stream_info.mimetype or ""
        supported_ext = {".pdf", ".docx", ".pptx", ".xlsx", ".html",
                         ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
        supported_mime = {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/html", "image/jpeg", "image/png", "image/bmp", "image/tiff",
        }
        return ext in supported_ext or mime in supported_mime

    def _analysis_features(self, stream_info) -> list:
        ext = (stream_info.extension or "").lower()
        mime = stream_info.mimetype or ""
        if ext in OCR_TYPES or mime in OCR_MIMES:
            return [
                DocumentAnalysisFeature.FORMULAS,
                DocumentAnalysisFeature.STYLE_FONT,
                DocumentAnalysisFeature.OCR_HIGH_RESOLUTION,
            ]
        return []  # Office docs / HTML don't need OCR features

    def convert(self, stream, stream_info, **kwargs):
        file_bytes = stream.read()
        poller = self.client.begin_analyze_document(
            model_id="prebuilt-layout",
            body=AnalyzeDocumentRequest(bytes_source=file_bytes),
            features=self._analysis_features(stream_info),
            output_content_format=ContentFormat.MARKDOWN,
        )
        result = poller.result()
        markdown = result.content

        # Strip HTML comments Azure inserts as layout annotations
        markdown = re.sub(r"<!--.*?-->", "", markdown, flags=re.DOTALL)
        markdown = markdown.strip()

        return DocumentConverterResult(text_content=markdown)
```

```python
# Registration example — register BEFORE local PDF/image converters to take priority,
# OR after them (at same priority, later insertion wins) to make it the default:
md = MarkItDown()
credential = AzureKeyCredential(os.environ["AZURE_DOC_INTEL_KEY"])
md.register_converter(
    DocumentIntelligenceConverter(
        endpoint=os.environ["AZURE_DOC_INTEL_ENDPOINT"],
        credential=credential,
    ),
    priority=PRIORITY_SPECIFIC_FILE_FORMAT,  # 0.0 — same priority as local converters
)
```

## Data contracts

- **Input**: any supported file as bytes — PDF, Office docs, JPEG/PNG/BMP/TIFF
- **Output**: Markdown string; Azure natively outputs Markdown from `prebuilt-layout`
- **Credentials env vars**: `AZURE_DOC_INTEL_ENDPOINT` (URL), `AZURE_DOC_INTEL_KEY` (API key)
- **Alternative auth**: `DefaultAzureCredential()` from `azure.identity` — tries managed identity, env vars, Azure CLI in sequence

## Dependencies & assumptions

```
azure-ai-documentintelligence >= 1.0
azure-core >= 1.30
azure-identity >= 1.16    # for DefaultAzureCredential
```
Requires network access to Azure endpoint. Per-page cost applies (check Azure pricing).

## To port this, you need:

- [ ] `DocumentIntelligenceClient` with endpoint + credential
- [ ] `_analysis_features()` that returns OCR features only for PDF/image types
- [ ] `begin_analyze_document()` with `output_content_format=ContentFormat.MARKDOWN`
- [ ] `re.sub(r"<!--.*?-->", "", markdown, flags=re.DOTALL)` to strip Azure's HTML comments
- [ ] Environment variable pattern for endpoint + key (or `DefaultAzureCredential`)
- [ ] Registration at appropriate priority relative to local converters

## Gotchas

- `begin_analyze_document()` is async (returns a poller). Call `.result()` to block until done. For large documents this can take 10-30+ seconds.
- `prebuilt-layout` is a general model. More specialized models (invoices, receipts, IDs) exist but require different `model_id` values.
- Azure bills per page. A 100-page PDF costs 100x more than a 1-page PDF. Add document size limits in `accepts()` if cost is a concern.
- `DefaultAzureCredential` tries ~7 credential sources in sequence. In local dev with no managed identity, it will try and fail several before landing on Azure CLI credentials — this adds latency on first call (~2-5s).
- HTML comments (`<!-- ... -->`) in Azure's output are layout annotations (page breaks, section markers). Strip them unless you need that metadata.

## Origin

https://github.com/microsoft/markitdown — `converters/_doc_intel_converter.py`, `converters/_cu_converter.py`
