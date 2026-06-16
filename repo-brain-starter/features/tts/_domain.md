# tts — domain

**What this domain means across repos studied:** on-device / local text-to-speech — turning
text into a speech waveform without a cloud API. The interesting engineering lives in the
*pipeline* (how text becomes audio), the *generative core* (how the acoustic content is sampled),
and the *control surface* (how a caller steers voice, language, speed, and prosody).

## Features filed here
| Feature | Repo | Study | Build |
|---------|------|-------|-------|
| ONNX TTS Pipeline | supertonic | [study](study/onnx-tts-pipeline--from-supertonic.md) | [build](build/onnx-tts-pipeline--from-supertonic.md) |
| Flow-Matching Sampler | supertonic | [study](study/flow-matching-sampler--from-supertonic.md) | [build](build/flow-matching-sampler--from-supertonic.md) |
| Expression Tags | supertonic | [study](study/expression-tags--from-supertonic.md) | [build](build/expression-tags--from-supertonic.md) |

## Mental model
A modern small TTS system is **four ONNX graphs in a row**:
1. **Duration predictor** — how long should each input token sound?
2. **Text encoder** — turn tokens into a conditioning embedding.
3. **Vector estimator** (the generative core) — iteratively denoise a random latent into a
   speech latent, conditioned on text + speaker style. This is the *flow-matching sampler*.
4. **Vocoder / autoencoder decoder** — turn the latent into a 44.1 kHz waveform.

Voice identity and prosody are **side-channels** into this pipeline: a speaker "style" vector
conditions steps 1–3, and inline **expression tags** ride through the text front-end as special
tokens. Keeping these decoupled is what makes the system controllable.
