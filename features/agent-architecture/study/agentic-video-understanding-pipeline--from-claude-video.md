# Agentic Video-Understanding Pipeline (`/watch`) — from [claude-video](https://github.com/bradautomates/claude-video)

> Domain: [[_domain]] · Source: https://github.com/bradautomates/claude-video · NotebookLM: <link once added>

## What it does

`/watch` is a Claude Code skill that lets the model **actually watch a video**. You paste a URL (YouTube, TikTok, Vimeo, Instagram, X) or a local file path plus a question — "what does she say about pricing at the end?", "what's the code on screen at 2:10?" — and Claude answers from the real visual and audio content, not the title or description.

The trick is that Claude can't ingest video directly. So the skill turns a video into two things Claude *can* read: a set of timestamped still frames (images) and a timestamped transcript (text). It does the heavy lifting in a Python script, prints a markdown report listing the frame file paths and the transcript, and then **Claude reads each frame image and answers**. The model is the reasoning engine; the script is its eyes and ears.

## Why it exists

LLMs are multimodal for images and text but not for video. Every "let an agent understand a video" product has to bridge that gap somehow. The elegant move here is to **not build a video model at all** — instead, decompose video into the modalities the model already has (frames + transcript), and let the model's existing intelligence do the understanding.

The job-to-be-done: give a coding agent the ability to reference video content as casually as it references a file. Tutorials, demos, recorded meetings, screen recordings — all become queryable. And it's packaged as a skill so it drops into Claude Code with one command.

## How it actually works

It's a five-step contract between the skill (instructions Claude follows) and the scripts (the muscle):

**Step 0 — Preflight.** Before anything, a `setup.py --check` runs. It verifies the external tools (`yt-dlp`, `ffmpeg`) are installed and that an API key exists if needed, returning specific exit codes (missing binaries vs. missing key) so the skill can either proceed silently or prompt to fix the gap. This keeps failures legible instead of cryptic ffmpeg errors deep in a run.

**Step 1 — Parse the request.** Claude pulls the video source (URL or path) and the question out of the user's message.

**Step 2 — Run the watch script.** One Python entry point orchestrates everything: it makes a temp working directory, downloads the video with yt-dlp (or resolves the local file), probes its duration, budgets and extracts frames at an auto-scaled rate, and produces a transcript (captions first, Whisper fallback). It downloads at ≤720p — enough to read the screen, small enough to be fast.

**Step 3 — Claude reads the frames.** The script's output is a markdown report: metadata, then a list of frame file paths each tagged with its absolute timestamp (`t=2:10`), then the transcript in a code block. Claude reads every frame path with its Read tool (in parallel) — that's the moment the model "sees" the video.

**Step 4 — Answer.** Now holding the frames (timestamped visuals) and the transcript (timestamped words), Claude answers the question, able to cross-reference what was shown against what was said at any moment.

**Step 5 — Clean up.** The temp directory is deleted unless follow-up questions are likely.

Flags let you steer: `--start/--end` to focus on a section (which also switches frame extraction into a denser mode and filters the transcript to that window), `--resolution 1024` to read small on-screen text or code, `--max-frames` to trim token cost, `--no-whisper` for frames-only, `--whisper groq|openai` to force a backend.

## The non-obvious parts

- **The model IS the video model.** There's no ML here beyond Whisper. The entire "understanding" is Claude reading stills and text. The engineering is all about *preparing* the right stills and text — which frames, how many, what timestamps — so the model can reason well.
- **Timestamps are the connective tissue.** Both frames and transcript carry absolute source timestamps. That's what lets Claude say "at 2:10 the screen shows X while she says Y" — the two modalities are aligned on a shared clock. Lose the timestamps and you lose the ability to correlate sight and sound.
- **It's a skill contract, not just a script.** The power is in the division of labor: the SKILL.md tells Claude *when and how* to call the script and *what to do with the output* (read the frames, then answer). The script never talks to the model; it just emits paths. This is a clean, reusable pattern for "give an agent a new sense."
- **Graceful degradation everywhere.** No captions? Use Whisper. No API key? Frames-only with a clear note. Subtitle download 429'd but video is fine? Proceed. Over 10 minutes? Warn that coverage is sparse and suggest a focus range. The pipeline almost never hard-fails — it does the best it can and tells the model what it got.
- **Cost-consciousness is baked in.** ≤720p download, 512px frames by default, frame budgets capped at 100, captions-before-Whisper, tiny 16kHz audio. Every stage is tuned to keep both token cost and API cost down, because an agent might call this often.
- **Self-contained-by-design temp dir.** Everything for a run lives in one `watch-XXXX` temp folder (video, frames, audio, subtitles) and gets `rm -rf`'d after. No state leaks between runs.

## Related

- [[duration-aware-frame-budgeting--from-claude-video]] (Step 2's frame half)
- [[captions-first-transcription-cascade--from-claude-video]] (Step 2's audio half)
- See also: [[agents-as-teammates--from-multica]], [[autonomous-execution-lifecycle--from-multica]] — other agent-architecture patterns; this one is "give an agent a new sensory modality via a skill contract."
