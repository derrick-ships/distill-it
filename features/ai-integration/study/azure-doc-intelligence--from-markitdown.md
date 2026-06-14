# Azure Document Intelligence Integration — from [markitdown](https://github.com/microsoft/markitdown)

> Domain: [[_domain]] · Source: https://github.com/microsoft/markitdown · NotebookLM:

## What it does

Sends documents to Azure's Document Intelligence cloud service (formerly Form Recognizer) and returns the result as Markdown. This is the heavy-duty path for documents that simpler converters can't handle: scanned PDFs with no text layer, handwritten forms, complex multi-column layouts, and images of documents.

## Why it exists

Azure Document Intelligence uses Microsoft's production OCR models, trained on billions of documents. For scanned PDFs or photographed documents, no local library can match it. The integration exists so MarkItDown can leverage cloud-grade extraction without bundling heavy ML models locally.

## How it actually works

**Authentication:** The converter accepts either an `AzureKeyCredential` (API key) or a `TokenCredential` (Azure DefaultAzureCredential, which tries managed identity, environment variables, Azure CLI, etc.). The credential is passed at construction time.

**Supported file types:** Two categories are handled differently:
- *No OCR needed* (DOCX, PPTX, XLSX, HTML): sent directly to the API; no special analysis features enabled.
- *OCR-enabled* (PDF, JPEG, PNG, BMP, TIFF): sent with additional analysis features: `FORMULAS`, `STYLE_FONT`, `OCR_HIGH_RESOLUTION`.

**API call:** The converter calls `doc_intel_client.begin_analyze_document()` with:
- `model_id="prebuilt-layout"` — Azure's general-purpose layout model
- `body=AnalyzeDocumentRequest(bytes_source=file_stream.read())` — the document bytes
- `features=` — the feature list depending on file type
- `output_content_format=CONTENT_FORMAT` — requests Markdown output directly

**Output processing:** Azure returns the result as Markdown. The converter strips HTML comments from the output using regex (`<!--...-->`), which Azure sometimes inserts as layout annotations, then wraps the cleaned text in a `DocumentConverterResult`.

## The non-obvious parts

- The `prebuilt-layout` model is Azure's general-purpose layout model — not a domain-specific one. It handles tables, headings, lists, and multi-column layouts. There are more specialized Azure models (receipts, invoices, IDs) that this integration doesn't use.
- Azure charges per page. Sending large documents incurs real cost.
- This converter is registered at the same priority as the local PDF converter. If both are registered, Azure wins only if it's registered later (insertion order) or at a lower priority value.
- `DefaultAzureCredential` is powerful but fragile in local dev — it tries a sequence of credential sources, and failures in early sources can delay the first request.

## Related

- [[converter-pipeline--from-markitdown]] — dispatches to this converter; local PDF fallback is [[pdf-conversion--from-markitdown]]
- [[image-llm-captioning--from-markitdown]] — alternative AI path for images (description vs. OCR)
