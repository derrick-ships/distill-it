# Audio Overview (TTS) — from [openpaper](https://github.com/khoj-ai/openpaper)

> Domain: [[_domain]] · Source: https://github.com/khoj-ai/openpaper · NotebookLM: <link once added>

## What it does

Press a button and Open Paper turns a paper — or a whole project of papers — into a short spoken
"audio overview," like a mini podcast episode about the research. It writes a narrative script, reads
it aloud in a voice you pick, and gives you back an audio file to play. It's the "listen to this paper
on my walk" feature.

## Why it exists

It's a different *modality* for the same goal of understanding. Some papers are easier to absorb as a
narrated brief than as text on a screen, and audio fits dead time (commuting, chores). It's also a
visible premium hook — generation is metered, so it nudges upgrades.

## How it actually works

Two steps: **write the script**, then **speak it**.

**Script.** An LLM is asked to produce a flowing, podcast-style narrative summary of the paper, hitting
a target length you choose — short (~450 words / ~3 min), medium (~1,000 / ~7 min), or long (~2,000 /
~14 min). The prompt explicitly says: no headings, no formatting, read like something on a podcast, and
mark citations as `[^1]`, `[^2]` tied to a list of raw quotes from the paper. The model returns a
structured object: the `summary` text (with those inline markers), a `citations` list, and a `title`.
For a multi-paper project, there's an extra agentic step first — the system gathers evidence across all
the project's papers (using file tools) and then synthesizes a cross-paper narrative that calls out
agreements and disagreements between them.

**Speech.** The citation markers get stripped out (you don't want "caret one" read aloud), the markdown
is cleaned for speech, and the text is sent to Azure OpenAI's `gpt-4o-mini-tts` model with your chosen
voice (one of 11; default "nova"). Long scripts are chunked at ~10k characters on sentence/paragraph
boundaries, each chunk synthesized to a WAV, and the chunks concatenated into one file — using a custom
WAV writer that hand-rolls the RIFF header to dodge a 4 GB size-field overflow bug in Python's `wave`
module. The final WAV goes to S3.

The whole thing runs as a **FastAPI background task** (not Celery) that opens its own DB session. The
client polls a status endpoint; playback is served as a short-lived **presigned S3 URL**.

## The non-obvious parts

- **Single-voice, not a dialogue.** Despite the podcast framing, it's one narrator reading one script —
  no two-host back-and-forth.
- **WAV, not MP3** — and a hand-written RIFF header so big files don't hit the 32-bit size overflow.
- **Cost gating is project-only.** The weekly limit (5/week basic, 100/week researcher) is enforced on
  project overviews but **not** on single-paper ones — single-paper audio is effectively ungated.
- **A length bug on the paper path:** the paper endpoint accepts a `length` but never forwards it, so
  single-paper overviews are always "medium" regardless of what you asked for. The project path forwards it correctly.
- **Client-driven timeout.** A job stuck >20 minutes is marked failed — but only when someone next polls
  its status; there's no server-side watchdog.
- **No caching/dedupe.** Every request makes a new job and a new file; you can pile up many overviews
  for the same paper.
- **Azure quirk noted in code:** the TTS endpoint wouldn't accept a "file" content type, so a
  plan to feed the source doc directly to the TTS context was abandoned.

## Related
- [[pdf-ingestion-pipeline--from-openpaper]] (the summary the script builds on comes from ingestion)
- [[citation-grounded-chat--from-openpaper]] (multi-paper overviews reuse the same evidence-gathering agent + `[^n]` citation style)
- [[corpus-and-academic-search--from-openpaper]] (project overviews search across the project's papers)
- See also: [[onnx-tts-pipeline--from-supertonic]] (on-device TTS) and
  [[elevenlabs-streaming-tts--from-clicky]] (cloud TTS) — different engines, same "text → speech" job.
