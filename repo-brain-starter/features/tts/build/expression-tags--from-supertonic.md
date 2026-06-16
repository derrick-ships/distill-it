# Expression Tags (build spec) — distilled from supertonic

## Summary
Add inline prosody control to a TTS system via a closed vocabulary of ~10 text tags
(`<laugh>`, `<breath>`, `<sigh>`, …). The tags are recognized in the **text front-end** and mapped
to reserved token IDs so they flow through the duration predictor, text encoder, and flow-matching
generator as ordinary tokens — the trained models render them as acoustic events. No DSP, no
reference audio, no separate model. Extends the tokenizer of [[onnx-tts-pipeline]].

## Core logic (inlined)
```python
EXPRESSION_TAGS = ["<laugh>", "<breath>", "<sigh>", ...]   # ~10, fixed by model version (Supertonic 3)

# In the text front-end, BEFORE per-character ord() tokenization:
#   - language wrapper is added: "<{lang}>" + text + "</{lang}>"
#   - expression tags embedded in `text` (e.g. "Oh really? <laugh> wild.") must be detected
#     and mapped to their reserved token id(s), NOT split into '<','l','a','u','g','h','>'.
#
# Conceptual tokenization (the tag is matched as a unit, then everything else is char-wise):
def tokenize(text, lang, indexer, tag_ids):
    s = standardize(nfkd(strip_emoji(text)))            # same cleaning as base pipeline
    s = f"<{lang}>" + s + f"</{lang}>"
    ids = []
    i = 0
    while i < len(s):
        tag = match_expression_tag(s, i)                # longest-match against EXPRESSION_TAGS
        if tag is not None:
            ids.append(tag_ids[tag])                    # reserved token id for the whole tag
            i += len(tag)
        else:
            ids.append(indexer[str(ord(s[i]))])         # normal: codepoint -> unicode_indexer.json
            i += 1
    return np.array([ids], dtype=np.int64)              # [1, T]
```
Once the tag is a token in `text_ids`, it propagates automatically:
- **duration_predictor** allocates time for it (a laugh has real duration),
- **text_encoder** folds it into `text_emb`,
- **vector_estimator** (flow-matching) generates the actual acoustic event,
- **vocoder** renders it into the waveform — blended with neighboring words, not spliced.

## Data contracts
- Input: user text with inline `<tag>` markup, same `(text, lang, ...)` call as the base pipeline.
- Tag → token-id map: a small lookup (the tag string → reserved int64 id understood by the models).
- Output: identical to the base pipeline (44.1 kHz float32 WAV); the tag manifests as audio, never
  as spoken characters.

## Dependencies & assumptions
- Sits entirely inside the existing tokenizer; no new ONNX model. Requires models trained with the
  tag vocabulary (Supertonic 3). Older/other weights ignore or mangle unknown tags.
- **Gap (verify before relying):** the precise storage of the tag→id mapping was NOT confirmed from
  source. Three plausible mechanisms: (a) the tags are entries inside `unicode_indexer.json` keyed by
  a sentinel, (b) a separate tag table merged into the indexer at load, or (c) a regex pre-pass that
  substitutes tags for reserved ids before `ord()` tokenization. Inspect the real tokenizer
  (`UnicodeProcessor` in `py/helper.py`) to pick the correct one. The *behavior* (inline tag →
  rendered prosody) is solid; the lookup wiring is the unverified part.

## To port this, you need:
- [ ] The base pipeline tokenizer ([[onnx-tts-pipeline]]) in place.
- [ ] The exact `EXPRESSION_TAGS` list + their reserved token ids for the model version you ship.
- [ ] Longest-match tag detection in the tokenizer loop, BEFORE per-character `ord()` mapping,
      and AFTER the `<lang>` wrapping (so wrapper markers and expression tags don't collide).
- [ ] Models trained on those tags (can't be added post-hoc without retraining).

## Gotchas
- **Closed vocabulary** — only trained tags do anything; `<yawn>` silently no-ops or corrupts.
- **Bracket collision** — the pipeline already uses `<lang>…</lang>`; ensure tag matching doesn't
  consume the language wrapper, and warn users that literal `<…>` in their text may be misparsed.
- **Tag must map to a single token unit**, not be char-split — otherwise the model sees `<`,`l`,`a`…
  and speaks "less-than-l-a-u-g-h-greater-than" or garbage.
- **Duration is automatic** — don't try to hand-time the laugh; the duration predictor handles it
  once the token is in the sequence.

## Origin (reference only)
Repo: https://github.com/supertone-inc/supertonic — text processing in `py/helper.py`
(`UnicodeProcessor.__call__`, `_preprocess_text`, `unicode_indexer.json`). Tag list documented in
the top-level README (Supertonic 3, ~10 inline expression tags). Model: HF `Supertone/supertonic-3`.
