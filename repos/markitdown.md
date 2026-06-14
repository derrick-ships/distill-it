# markitdown

**Source**: https://github.com/microsoft/markitdown
**Product**: Python utility that converts diverse file formats (PDF, Office docs, images, audio, web URLs) into Markdown for LLM and text-analysis pipelines.
**Stack**: Python 3.10+, pdfplumber, python-docx, python-pptx, pandas, BeautifulSoup, markdownify, Magika (Google ML), speech_recognition, azure-ai-documentintelligence
**Stars**: ~153k · **Distilled**: 2026-06-14

## What it is

A single-call document-to-Markdown converter with a pluggable converter registry. The design philosophy: one uniform entry point (`md.convert(anything)`), priority-sorted specialist converters behind it, optional AI enhancement layers (LLM vision, Azure OCR, speech recognition), and a third-party plugin system for community extensions.

## Features distilled

### document-conversion
| Feature | Study | Build |
|---------|-------|-------|
| Converter Pipeline Architecture | [study](../features/document-conversion/study/converter-pipeline--from-markitdown.md) | [build](../features/document-conversion/build/converter-pipeline--from-markitdown.md) |
| PDF Conversion | [study](../features/document-conversion/study/pdf-conversion--from-markitdown.md) | [build](../features/document-conversion/build/pdf-conversion--from-markitdown.md) |
| Office Document Conversion (DOCX/PPTX/XLSX) | [study](../features/document-conversion/study/office-doc-conversion--from-markitdown.md) | [build](../features/document-conversion/build/office-doc-conversion--from-markitdown.md) |
| ZIP Archive Traversal | [study](../features/document-conversion/study/zip-archive-traversal--from-markitdown.md) | [build](../features/document-conversion/build/zip-archive-traversal--from-markitdown.md) |

### plugin-architecture
| Feature | Study | Build |
|---------|-------|-------|
| Plugin System | [study](../features/plugin-architecture/study/plugin-system--from-markitdown.md) | [build](../features/plugin-architecture/build/plugin-system--from-markitdown.md) |

### file-detection
| Feature | Study | Build |
|---------|-------|-------|
| Content-Aware File Detection (Magika) | [study](../features/file-detection/study/magika-file-detection--from-markitdown.md) | [build](../features/file-detection/build/magika-file-detection--from-markitdown.md) |

### media-processing
| Feature | Study | Build |
|---------|-------|-------|
| Image Conversion + LLM Captioning | [study](../features/media-processing/study/image-llm-captioning--from-markitdown.md) | [build](../features/media-processing/build/image-llm-captioning--from-markitdown.md) |
| Audio Transcription | [study](../features/media-processing/study/audio-transcription--from-markitdown.md) | [build](../features/media-processing/build/audio-transcription--from-markitdown.md) |

### web-extraction
| Feature | Study | Build |
|---------|-------|-------|
| YouTube URL Extraction | [study](../features/web-extraction/study/youtube-extraction--from-markitdown.md) | [build](../features/web-extraction/build/youtube-extraction--from-markitdown.md) |
| HTML / Web Conversion | [study](../features/web-extraction/study/html-web-conversion--from-markitdown.md) | [build](../features/web-extraction/build/html-web-conversion--from-markitdown.md) |

### ai-integration
| Feature | Study | Build |
|---------|-------|-------|
| Azure Document Intelligence | [study](../features/ai-integration/study/azure-doc-intelligence--from-markitdown.md) | [build](../features/ai-integration/build/azure-doc-intelligence--from-markitdown.md) |
