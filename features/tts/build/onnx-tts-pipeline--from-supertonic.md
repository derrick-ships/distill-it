# ONNX TTS Pipeline (build spec) — distilled from supertonic

## Summary
Build an on-device text-to-speech engine that turns `(text, lang, voice_style, total_steps, speed)`
into a 44.1 kHz float32 waveform by chaining **four ONNX models** through ONNX Runtime:
`duration_predictor` → `text_encoder` → `vector_estimator` (looped) → `vocoder`. No GPU required;
runs anywhere ONNX Runtime runs. Speaker identity is a small JSON "style" object; language and
prosody enter through a Unicode-based text tokenizer.

## Core logic (inlined)

### The four ONNX graphs and their I/O
```
1. duration_predictor.onnx
   inputs : text_ids (int64 [B,T]), style_dp (float32), text_mask (float32 [B,1,T])
   output : dur_onnx          # per-token duration (frames/seconds-ish), float32 [B,T]

2. text_encoder.onnx
   inputs : text_ids (int64 [B,T]), style_ttl (float32), text_mask (float32 [B,1,T])
   output : text_emb_onnx     # conditioning embedding, float32

3. vector_estimator.onnx       # the flow-matching velocity field — see flow-matching-sampler build
   inputs : noisy_latent (float32 [B, latent_dim, latent_len]),
            text_emb (float32), style_ttl (float32),
            text_mask (float32 [B,1,T]), latent_mask (float32 [B,1,latent_len]),
            current_step (float32 [B]), total_step (float32 [B] or scalar)
   output : xt                 # refined latent, same shape as noisy_latent

4. vocoder.onnx
   input  : latent (float32 [B, latent_dim, latent_len])
   output : wav (float32 [B, num_samples])   # 44.1 kHz
```

### End-to-end control flow (pseudocode)
```python
# --- setup (once) ---
sessions = {name: ort.InferenceSession(f"{onnx_dir}/{name}.onnx", providers=providers)
            for name in ["duration_predictor","text_encoder","vector_estimator","vocoder"]}
sample_rate = cfgs["ae"]["sample_rate"]          # 44100
indexer     = json.load(open("unicode_indexer.json"))   # {unicode_value(str/int) -> token_id(int)}

# --- per request: synthesize(text, lang, style, total_steps=8, speed=1.05) ---
# 1. TEXT FRONT-END  (see expression-tags + onnx-tts text processing)
s = nfkd_normalize(text); s = strip_emoji(s); s = standardize_quotes_dashes(s)
s = f"<{lang}>" + s + f"</{lang}>"               # lang in AVAILABLE_LANGS, or "na" = agnostic
codepoints = [ord(ch) for ch in s]               # uint16 per char
text_ids   = np.array([[indexer[str(cp)] for cp in codepoints]], dtype=np.int64)  # [1,T]
text_mask  = length_to_mask([len(codepoints)])   # float32 [1,1,T]

# 2. DURATION
dur = sessions["duration_predictor"].run(None,
        {"text_ids": text_ids, "style_dp": style.dp, "text_mask": text_mask})[0]
dur = dur / speed                                # speed knob is pure arithmetic on durations
latent_len = derive_latent_len(dur, sample_rate) # total predicted duration -> #latent frames
latent_mask = length_to_mask([latent_len])       # float32 [1,1,latent_len]

# 3. TEXT ENCODE
text_emb = sessions["text_encoder"].run(None,
        {"text_ids": text_ids, "style_ttl": style.ttl, "text_mask": text_mask})[0]

# 4. FLOW-MATCHING SAMPLER  (detail in flow-matching-sampler build spec)
xt = sample_noisy_latent(shape=(1, latent_dim, latent_len))   # gaussian noise
total_step_np = np.array([total_steps], dtype=np.float32)
for step in range(total_steps):
    current_step = np.array([step], dtype=np.float32)
    xt = sessions["vector_estimator"].run(None, {
        "noisy_latent": xt, "text_emb": text_emb, "style_ttl": style.ttl,
        "text_mask": text_mask, "latent_mask": latent_mask,
        "current_step": current_step, "total_step": total_step_np})[0]

# 5. VOCODE
wav = sessions["vocoder"].run(None, {"latent": xt})[0]          # [1, num_samples], 44.1kHz

# 6. TRIM + (multi-chunk) STITCH
duration_sec = total_predicted_duration(dur)
w = wav[0, : int(sample_rate * duration_sec)]
# for multi-sentence input: synth each chunk, then concat with silence:
#   np.zeros((1, int(silence_duration * sample_rate)))  between chunks
soundfile.write(out_path, w, sample_rate)
```

### Text tokenizer (UnicodeProcessor) — the language-agnostic trick
- Normalize NFKD, strip emoji (Unicode-range filter), standardize dashes/quotes.
- Wrap: `"<{lang}>" + text + "</{lang}>"`.
- `ord(ch)` per character → uint16 code points.
- Map each code point through `unicode_indexer.json` → int64 token id. **One table, all 31 langs.**
- `length_to_mask(lengths)` → attention mask shape `(B, 1, max_len)`.
- `lang="na"` = no language tag / agnostic processing.

## Data contracts

**Voice style JSON** (`<VoiceName>.json`, e.g. `M1.json`):
```json
{ "style_ttl": [[ ... ]],   // float32, shape [dims[1], dims[2]] — conditions text_encoder + vector_estimator
  "style_dp":  [[ ... ]] }  // float32, shape [dims[1], dims[2]] — conditions duration_predictor
```
Loaded into a `Style` object with `.ttl` and `.dp` arrays, batch-stacked across the request batch.
Preset voices: M1,M3,M4,M5 (male), F1,F3,F4,F5 (female). New voices = new JSON (Voice Builder tool).

**Config** (`cfgs`): contains `cfgs["ae"]["sample_rate"] == 44100` and latent dims.

**Synthesize params:** `total_steps` 5–12 (default 8); `speed` 0.7–2.0 (example default 1.05);
`lang` ∈ AVAILABLE_LANGS ∪ {"na"} (31 langs incl. en, ko, ja, ar, bg, …).

## Dependencies & assumptions
- `onnxruntime` (CPU is fine; GPU optional via providers). `numpy`. `soundfile` (WAV write).
- Model assets: 4 `.onnx` files + `unicode_indexer.json` + config + voice-style JSONs. Fetched from
  Hugging Face: `git clone https://huggingface.co/Supertone/supertonic-3 assets` (or `auto_download=True`
  in the SDK). OnnxSlim-optimized variants exist for speed.
- Swappable: providers (CPU/CUDA/CoreML/WebGPU), vocoder/estimator weights (v2-compatible interface),
  the WAV writer.

## To port this, you need:
- [ ] ONNX Runtime bindings in the target language (exist for Py/Node/Java/C++/C#/Go/Swift/Rust/Flutter/Web).
- [ ] The 4 `.onnx` files + `unicode_indexer.json` + config + at least one voice-style JSON, bundled or downloadable.
- [ ] A Unicode text normalizer (NFKD, emoji strip, quote/dash fold) and the `ord()`→indexer tokenizer.
- [ ] A `length_to_mask` helper producing `(B,1,T)` float masks.
- [ ] The sampler loop calling `vector_estimator` `total_steps` times (feed `current_step`/`total_step` each call).
- [ ] WAV writer at 44100 Hz; trim to `int(sample_rate * duration)`.

## Gotchas
- **`total_step`/`current_step` are tensor inputs**, not config — must be passed every estimator call,
  or quality silently collapses. Don't hardcode.
- **Latent length comes from the duration predictor** *before* sampling. Get this wrong → wrong-length
  or garbled audio. `speed` must be applied to durations *before* deriving `latent_len`.
- **Tokenizer must match the trained vocab exactly** — same normalization, same `unicode_indexer.json`,
  same `<lang>` wrapping. A mismatched front-end produces gibberish even with correct models.
- **Trim the output**: the vocoder emits a padded canvas; slice to `sample_rate * duration`.
- **dtype discipline**: `text_ids` int64; masks/latents/steps float32. ORT is strict.
- **Multi-sentence**: chunk long text, synth per chunk, concat with silence — single-shot very long
  inputs strain the duration/latent sizing.

## Origin (reference only)
Repo: https://github.com/supertone-inc/supertonic — Python files `py/helper.py` (`load_onnx_all`,
`UnicodeProcessor`, `_infer`, `load_voice_style`, `Style`) and `py/example_onnx.py`
(`load_text_to_speech`, `text_to_speech(...)`, WAV write). Models: HF `Supertone/supertonic-3`.
