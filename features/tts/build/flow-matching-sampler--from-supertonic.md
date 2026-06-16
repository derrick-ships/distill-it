# Flow-Matching Sampler (build spec) — distilled from supertonic

## Summary
The generative core of the TTS pipeline: iteratively denoise a random latent into a clean speech
latent using a single learned "velocity field" model (`vector_estimator.onnx`) called `total_steps`
times. Exposes one runtime quality/latency dial (`total_steps`, 5–12, default 8). Sits between the
text encoder and the vocoder in [[onnx-tts-pipeline]].

## Core logic (inlined)
```python
# Preconditions from upstream stages:
#   text_emb     <- text_encoder.onnx
#   style.ttl    <- voice style JSON
#   text_mask    <- length_to_mask([T])                  float32 [B,1,T]
#   latent_len   <- derived from duration_predictor output (after speed scaling)
#   latent_dim   <- from model config
latent_mask   = length_to_mask([latent_len])             # float32 [B,1,latent_len]
total_step_np = np.array([total_steps] * bsz, dtype=np.float32)

# 1. INIT: start from gaussian noise shaped like a speech latent
xt = sample_noisy_latent(shape=(bsz, latent_dim, latent_len))   # np.random.randn(...), float32

# 2. REFINE: walk the noise -> speech trajectory in `total_steps` discrete steps
for step in range(total_steps):
    current_step = np.array([step] * bsz, dtype=np.float32)      # which step we're on
    xt, *_ = vector_est_ort.run(None, {
        "noisy_latent": xt,            # previous latent feeds back in
        "text_emb":     text_emb,
        "style_ttl":    style.ttl,
        "text_mask":    text_mask,
        "latent_mask":  latent_mask,
        "current_step": current_step,  # <-- FED EVERY ITERATION (not a constant)
        "total_step":   total_step_np, # <-- enables runtime step-count without retrain
    })
    # xt is the refined latent; becomes input to the next step

# 3. xt is now a clean speech latent -> hand to vocoder.onnx
```

**Why it's only ~8 steps:** flow matching learns a velocity field that transports the noise
distribution to the data distribution along a near-straight path, so a few Euler-style steps
suffice (vs. 25–50 for classic diffusion). The network internally uses `current_step`/`total_step`
to scale each update, which is why the *same weights* sample correctly at 5 or 12 steps.

**Length-Aware RoPE (architectural note):** the estimator aligns the text sequence (length T) with
the speech latent sequence (length `latent_len`) via a length-aware rotary positional encoding.
This is baked into the trained ONNX graph — you don't implement it at inference time, but it's the
reason alignment stays stable and repeat/skip errors are low. If you retrain, this is the key piece.

## Data contracts
- `noisy_latent` / `xt`: float32, shape `(B, latent_dim, latent_len)`.
- `text_emb`: float32, output of text_encoder (opaque embedding — pass through unchanged).
- `style_ttl`: float32, from voice JSON `style_ttl` field, batch-stacked.
- `text_mask`: float32 `(B, 1, T)`; `latent_mask`: float32 `(B, 1, latent_len)`.
- `current_step`: float32 `(B,)`, value = loop index. `total_step`: float32 `(B,)` (or scalar),
  value = `total_steps`.
- Output `xt`: float32, same shape as `noisy_latent`.

## Dependencies & assumptions
- `onnxruntime` + `numpy`. Only the `vector_estimator.onnx` graph (plus upstream `text_emb` and
  duration-derived `latent_len`).
- `total_steps` default 8; valid 5–12. Higher = better quality, linearly slower (N extra ORT runs).
- **Gap (verify):** `derive_latent_len(dur, sample_rate)` — the exact formula mapping predicted
  durations to `latent_len` (i.e. the latent frame rate vs. the 44.1 kHz sample rate) was not fully
  confirmed from source. Confirm the AE downsample factor before relying on exact frame counts.

## To port this, you need:
- [ ] `vector_estimator.onnx` loaded in ORT.
- [ ] Upstream `text_emb`, `style.ttl`, `text_mask`, and a computed `latent_len` + `latent_mask`.
- [ ] A gaussian noise generator for the initial latent (seed it for reproducibility).
- [ ] The loop that re-feeds `xt` and passes fresh `current_step` each iteration with constant `total_step`.

## Gotchas
- **`current_step` must change each iteration; `total_step` must stay constant.** Swapping or
  hardcoding these is the #1 porting bug — output degrades to noise or muffled audio with no error.
- **Feed `xt` back in.** The loop is stateful: each step's output is the next step's `noisy_latent`.
- **float32 everywhere** for latents/masks/steps. Don't pass `current_step` as int.
- **Noise seed = determinism.** Tests must fix the RNG or outputs vary run-to-run.
- **Don't confuse with diffusion schedulers** — there's no separate beta/alpha schedule to manage;
  the step indices are the entire schedule and they're inputs to the graph.

## Origin (reference only)
Repo: https://github.com/supertone-inc/supertonic — `py/helper.py`, the `_infer()` method's
`for step in range(total_step)` loop over `vector_est_ort.run(...)`, and `sample_noisy_latent()`.
Model: HF `Supertone/supertonic-3`, `vector_estimator.onnx`.
