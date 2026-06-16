# Flow-Matching Sampler — from [supertonic](https://github.com/supertone-inc/supertonic)

> Domain: [[_domain]] · Source: https://github.com/supertone-inc/supertonic · NotebookLM: <add link>

## What it does
This is the generative heart of the TTS system — the part that actually *invents* the sound.
It takes random noise and, in a handful of refinement steps, sculpts it into a "speech latent"
that, once decoded, sounds like the requested text in the requested voice. The caller gets a
single dial, `total_steps` (5–12, default 8), that trades speed for quality: fewer steps = faster
and rougher, more steps = slower and cleaner.

## Why it exists
Older TTS used either autoregressive models (slow — generate audio one frame at a time) or
one-shot models (fast but lower quality). **Flow matching** is the middle path that's currently
winning: it learns a smooth "velocity field" that transports random noise to clean data, and you
can sample it in just a few steps. That's exactly what an on-device system needs — near-real-time
generation with a tunable quality/latency knob, all on CPU. It's the reason a 99M-param model can
turn a webpage into audio in under a second.

## How it actually works
Picture the speech latent as a point that needs to travel from "pure noise" to "clean speech."
The model (`vector_estimator.onnx`) has learned, for any point along the way, which *direction*
to move. Sampling is just walking that path in a few discrete steps:

1. **Start from noise.** A latent tensor shaped `(batch, latent_dim, latent_len)` is filled with
   random noise. Its *length* isn't arbitrary — it comes from the duration predictor (total
   predicted duration drives how many latent frames to allocate), so the clip is the right length
   before generation even starts.

2. **Refine in a loop.** For each step from 0 to `total_steps-1`, the current noisy latent is fed
   to the estimator along with: the text embedding, the speaker style vector, the text mask, the
   latent mask, and — crucially — *which step we're on* (`current_step`) and *how many total*
   (`total_step`). The network returns a refined latent. That output becomes the input to the next
   step. Each pass moves the point further along the noise→speech trajectory.

3. **Stop and decode.** After the last step the latent is "clean" and gets handed to the vocoder.

The reason `current_step` and `total_step` are *explicit inputs* (not baked in) is what gives the
runtime quality dial: the same trained network can be sampled in 5 steps or 12 steps, and it
adjusts its step size accordingly. You're not retraining anything — you're choosing how finely to
walk the same path.

Two architectural ideas the repo highlights as making this work well at small scale:
- **Length-Aware RoPE** — a positional-encoding scheme that keeps text and the (separately-lengthed)
  speech latent aligned, so words land in the right place even though the two sequences differ in
  length. This is what cuts the "repeat / skip" failures common in small TTS.
- **RobustSpeechFlow / self-purifying training** — training-time techniques (augmentation-based
  contrastive matching, robustness to noisy labels) that aren't part of inference but explain why
  the few-step sampler stays stable and high-fidelity.

## The non-obvious parts
- **The quality knob is an *input tensor*, not a config flag.** Because `current_step`/`total_step`
  are fed into the ONNX graph each call, `total_steps` is a true runtime parameter — no recompile,
  no reload. This is subtle and easy to get wrong when porting (people hardcode it).
- **Latent length is decided *before* sampling**, by the duration predictor — generation doesn't
  "decide when to stop," it fills a pre-sized canvas. That's why duration prediction and the
  sampler are tightly coupled even though they're separate models.
- **It's not classic diffusion.** Flow matching looks similar (iterative denoising) but learns a
  velocity field directly, which is why 8 steps suffices where diffusion often wants 25–50.
- **Determinism depends on the noise seed.** The starting noise is random; for reproducible output
  you must fix the RNG. Worth knowing for testing.

## Related
- [[onnx-tts-pipeline]] — the full four-model chain this sampler sits inside (stage 4).
- [[expression-tags]] — prosody control that conditions the same generator via the text embedding.
- See also: any other repo's diffusion/flow vocoder for a `similar-pattern` comparison.
