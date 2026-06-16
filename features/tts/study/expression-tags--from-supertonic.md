# Expression Tags — from [supertonic](https://github.com/supertone-inc/supertonic)

> Domain: [[_domain]] · Source: https://github.com/supertone-inc/supertonic · NotebookLM: <add link>

## What it does
Lets you sprinkle inline cues into your text — like `<laugh>`, `<breath>`, `<sigh>` — and the
synthesized voice will actually laugh, take a breath, or sigh at that spot. Ten such tags ship in
Supertonic 3. It's a way to add natural, human prosody without recording a reference clip or
fiddling with prompt engineering. You just write `Oh really? <laugh> that's wild.`

## Why it exists
Flat TTS reads everything in the same even tone — it's the giveaway that something is synthetic.
The usual fixes are heavy: supply a reference audio clip with the emotion you want, or train
emotion-conditioned models. Expression tags are the lightweight alternative: a vocabulary of
discrete, named prosodic events the user can place *exactly where they want them*, inline, as
plain text. Cheap to use, precise, and language-independent. For products like audiobook readers
or character voices, this is the difference between "robot" and "alive."

## How it actually works
The tags ride through the **text front-end** (stage 1 of [[onnx-tts-pipeline]]) rather than being
a separate model. The key insight: the system already tokenizes text by walking characters and
looking them up in `unicode_indexer.json`. Expression tags are handled in that same tokenization
layer — a tag like `<laugh>` is recognized during preprocessing and mapped to its own token(s),
so by the time the text reaches the duration predictor and text encoder, the "laugh" is just
another token in the sequence. The downstream models were trained to render that token as the
corresponding acoustic event, with the surrounding words flowing naturally into and out of it.

Because the tag becomes a real token in the sequence:
- the **duration predictor** allocates time for it (a laugh takes real seconds),
- the **text encoder** folds it into the conditioning embedding, and
- the **flow-matching generator** ([[flow-matching-sampler]]) produces the actual laugh audio.

So a single inline tag automatically propagates through every stage — you don't wire it in four
places, you just add it to the text.

> **Gap (verify before relying):** the exact mechanism by which a multi-character tag like
> `<laugh>` is matched and mapped to a reserved token ID — whether via entries in
> `unicode_indexer.json`, a separate tag table, or a regex pre-pass — was not fully confirmed from
> the source during distillation. The *effect* (inline tags → rendered prosody) is documented; the
> precise lookup path should be checked in the tokenizer before reimplementing.

## The non-obvious parts
- **Tags are tokens, not effects.** There's no DSP or post-processing bolting a laugh onto the
  audio. The model *generates* the laugh because the tag is part of its input sequence. That's why
  it sounds blended rather than spliced.
- **They reuse the angle-bracket convention.** The pipeline already wraps text in `<lang>…</lang>`
  markers, so `<laugh>`-style tags fit the same "special markup in the character stream" pattern —
  elegant, but it means your literal text must not contain stray `<…>` that could be misread.
- **It's a closed vocabulary.** Only the trained set (~10 tags) works; inventing `<yawn>` won't do
  anything unless the model was trained on it. The list is fixed by the model version.
- **Prosody control without reference audio** is the strategic point: it lowers the skill floor for
  getting expressive output, which matters for consumer-facing products.

## Related
- [[onnx-tts-pipeline]] — tags enter at the text front-end (stage 1) and propagate through.
- [[flow-matching-sampler]] — the stage that actually renders the tagged prosody.
- See also: reference-audio / zero-shot emotion cloning (the heavier alternative this avoids).
