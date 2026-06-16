# Supertonic — origin index

- **Source:** https://github.com/supertone-inc/supertonic
- **What it is:** A lightning-fast, on-device multilingual text-to-speech system (~99M params)
  built entirely on ONNX Runtime. 31 languages, 44.1 kHz output, inline expression tags, no GPU
  required. Ships reference SDKs across Python, Node.js, browser (WebGPU/WASM), Java, C++, C#, Go,
  Swift, iOS, Rust, and Flutter — all driving the same ONNX models.
- **Author:** Supertone Inc. · **Models:** Hugging Face `Supertone/supertonic-3` (current),
  `supertonic-2` (5-lang stable), `supertonic-1` (English legacy).
- **Date distilled:** 2026-06-15
- **Architecture in one line:** text → (Unicode tokenizer) → `duration_predictor` →
  `text_encoder` → `vector_estimator` (flow-matching, looped `total_steps×`) → `vocoder` → 44.1 kHz WAV.

## Features extracted
| Feature | Domain | Study | Build |
|---------|--------|-------|-------|
| ONNX TTS Pipeline | tts | [study](../features/tts/study/onnx-tts-pipeline--from-supertonic.md) | [build](../features/tts/build/onnx-tts-pipeline--from-supertonic.md) |
| Flow-Matching Sampler | tts | [study](../features/tts/study/flow-matching-sampler--from-supertonic.md) | [build](../features/tts/build/flow-matching-sampler--from-supertonic.md) |
| Expression Tags | tts | [study](../features/tts/study/expression-tags--from-supertonic.md) | [build](../features/tts/build/expression-tags--from-supertonic.md) |

## Not yet distilled (candidates)
- **Voice styles & Voice Builder** (M1–M5/F1–F5 speaker JSON; build custom voices from reference audio) → domain: `voice`
- **Language-agnostic / multilingual front-end** (31 langs, `lang="na"`, `unicode_indexer.json`) → domain: `i18n`
- **Auto model download from Hugging Face** (`auto_download=True`) → domain: `infra`
- **Local HTTP server** (`supertonic serve`; native `/v1/tts` + OpenAI-compatible `/v1/audio/speech`) → domain: `serving`
- **WebGPU/WASM browser inference** (full ONNX pipeline client-side) → domain: `web-runtime`
- **Cross-runtime SDK parity** (same ONNX driven from 10+ languages — the porting pattern itself) → domain: `portability`

## Verification gaps flagged in build docs (check before transplant)
- Exact `derive_latent_len(dur, sample_rate)` formula (AE downsample factor) — flow-matching-sampler build.
- Exact storage/lookup of expression-tag → reserved-token-id mapping — expression-tags build.
