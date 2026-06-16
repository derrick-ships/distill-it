# ONNX TTS Pipeline — from [supertonic](https://github.com/supertone-inc/supertonic)

> Domain: [[_domain]] · Source: https://github.com/supertone-inc/supertonic · NotebookLM: <add link>

## What it does
You hand it a string of text, a language code, and a voice, and it hands back a 44.1 kHz WAV of
that text spoken aloud — generated entirely on the local machine, no internet, no GPU required.
An entire webpage's worth of text turns into audio in under a second. The whole model is ~99M
parameters, small enough to run on a Raspberry Pi or an e-reader in airplane mode.

## Why it exists
Cloud TTS is expensive, slow (network round-trips), and privacy-hostile (your text leaves the
device). Supertone's bet is that a *small, fast, on-device* model is good enough for real use —
e-readers, accessibility tools, browser extensions, embedded devices — and that it can ship the
exact same model to a dozen languages/runtimes (Python, Node, browser, Swift, Rust, …) because
it's all just **ONNX**. The job-to-be-done: "speak this text, instantly, anywhere, privately."

## How it actually works
The system is **four neural networks chained together**, each shipped as a separate `.onnx` file
and run with ONNX Runtime. Think of it as an assembly line:

1. **Text front-end.** The raw string is cleaned (Unicode NFKD normalization, emoji stripped,
   smart-quotes/dashes standardized), wrapped with language markers like `<en>…</en>`, then turned
   into a list of integer token IDs. The clever trick: instead of a hand-built phoneme dictionary
   per language, every *character* is converted to its Unicode code point and looked up in one big
   `unicode_indexer.json` table. That's how one model covers 31 languages without 31 tokenizers.

2. **Duration predictor.** Given the tokens and the voice's "style" vector, a small network
   predicts how long each token should sound. This sets the rhythm and total length of the clip.
   The caller's `speed` knob simply divides these durations (faster speed → shorter durations).

3. **Text encoder.** The tokens (again with the style vector) become a rich embedding — the
   "what to say and how" conditioning signal that the generator will lean on.

4. **The generator (vector estimator).** This is the heart. It starts from pure random noise
   shaped like a speech latent, then refines it in a handful of steps (default 8, range 5–12),
   each step nudging the noise closer to a clean speech latent that matches the text embedding and
   the voice style. More steps = higher quality but slower. (Detailed in [[flow-matching-sampler]].)

5. **Vocoder.** The finished latent is decoded by one more network into the actual audio waveform
   at 44.1 kHz. No separate upsampler is needed — it produces full-quality audio directly.

Finally, multiple sentence-chunks are stitched together with short silences and trimmed to the
predicted duration, and written to a WAV.

The elegant part: **the voice and the language are both just inputs**, not separate models. Swap
the style vector → different speaker. Change the `<lang>` wrapper → different language. The four
ONNX graphs never change.

## The non-obvious parts
- **Unicode-as-tokenizer.** Using raw code points + one JSON index instead of per-language
  phonemizers is what makes 31-language support tractable in 99M params. It also means a
  `lang="na"` ("not applicable") mode can process mixed/unknown-language text.
- **Four small models beat one big one.** Splitting duration / encoding / generation / vocoding
  into separate ONNX files keeps each graph small, swappable, and individually optimizable
  (they ship OnnxSlim-optimized variants). It's also why porting to a new runtime is "load 4
  files and wire them up" rather than "reimplement a monolith."
- **Style is a side-channel, not a model.** Speaker identity lives in a tiny JSON of two arrays
  (`style_ttl`, `style_dp`) that condition stages 1–3. New voices are new JSON files, not new
  weights — the Voice Builder tool generates these from reference audio.
- **Speed is free.** Because duration is an explicit predicted quantity, changing speech rate is
  just arithmetic on those durations — no re-generation tricks.
- **The same WAV everywhere.** Because it's all ONNX, the Python output and the browser-WebGPU
  output and the Swift output are byte-for-byte the same pipeline. That cross-runtime parity is a
  product feature, not an accident.

## Related
- [[flow-matching-sampler]] — the iterative-refinement core (stage 4), in depth.
- [[expression-tags]] — inline `<laugh>`/`<breath>` prosody, which rides through stage 1.
- See also: the `serving` candidate (OpenAI-compatible local HTTP server wrapping this pipeline).
