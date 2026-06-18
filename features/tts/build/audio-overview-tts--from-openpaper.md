# Audio Overview (TTS) (build spec) — distilled from openpaper

## Summary

Generate a spoken "audio overview" of a paper or a multi-paper project. Two stages: (1) an LLM writes a
podcast-style narrative script to a target length with `[^n]` citation markers + a citations list +
title (structured output); (2) strip markers, clean markdown, chunk at ~10k chars, synthesize each
chunk via **Azure OpenAI `gpt-4o-mini-tts`**, concatenate to one WAV (custom RIFF writer), upload to S3.
Runs as a FastAPI BackgroundTask; client polls status; playback via presigned S3 URL.

## Core logic (inlined)

### Flow

```
POST /papers/{id}/audio/         |  POST /projects/audio/{project_id}/
  (project path) can_user_create_audio_overview()  -> 403 if over weekly limit   # paper path NOT gated
  INSERT AudioOverviewJob{status=PENDING}
  BackgroundTasks.add_task(generate_audio_overview_async, ...)  -> return 202 {job_id, status:"pending"}

generate_audio_overview_async():   # opens its OWN SessionLocal()
  job -> RUNNING, status_message="Starting"
  if paper:   summary_obj = operations.create_narrative_summary(paper, length, additional_instructions)
  if project: summary_obj = await operations.create_multi_paper_narrative_summary(...)  # evidence-gather loop first
  status_message="Transcript generated"
  text = re.sub(r"\[\^\d+\]", "", summary_obj.summary)         # strip [^n] before TTS
  wav  = await asyncio.to_thread(speaker.generate_speech_from_text, text, voice)  # sync TTS in threadpool
  s3_key = s3.upload_any_file(wav, content_type="audio/wav")
  INSERT AudioOverview{s3_object_key, transcript=summary_obj.summary, citations, title}
  job -> COMPLETED

GET status: /papers/{id}/audio/{id}/status | /projects/audio/jobs/{project_id}
  -> {job_id, status, status_message, conversable_id, conversable_type}
  (paper status endpoint also force-FAILs a RUNNING job older than 20 min — client-triggered, no server watchdog)

GET file: /papers/{id}/audio/file | /projects/audio/file/{project_id}/{audio_overview_id}
  -> {..., audio_url: s3.generate_presigned_url(s3_object_key)}
```

### Script generation

```python
word_count_map = {"short":450,   # ~3 min @150wpm
                  "medium":1000, # ~7 min
                  "long":2000}   # ~14 min
# Single paper prompt (GENERATE_NARRATIVE_SUMMARY), key load-bearing lines:
#   "generate a narrative summary ... key findings, methodologies, and conclusions"
#   "approximately {length} words long (this is important - aim to hit this target)"
#   "narrative style ... without ... special headings or formatting"
#   "could be read on a podcast or in a blog post"
#   "Citations should be formatted as [^1], [^2], ... corresponds to the idx of the list of citations"
# Output schema AudioOverviewForLLM = {summary:str(with [^n]), citations:list[str raw quotes], title:str}
```
Multi-paper: runs an evidence-gathering agentic loop (`EVIDENCE_GATHERING_SYSTEM_PROMPT`, tools
`search_all_files/read_abstract/search_file/view_file/read_file/STOP`) across project papers, then
`GENERATE_MULTI_PAPER_NARRATIVE_SUMMARY` ("synthesize across papers, highlight agreements and
disagreements, ~{length} words"), same output schema.

### TTS — `app/llm/speech.py`

```python
self.client = openai.AzureOpenAI(api_key=KEY, azure_endpoint=ENDPOINT,
                                 api_version=VERSION or "2025-04-01-preview", timeout=300.0)
self.model  = "gpt-4o-mini-tts"
VOICES = [alloy,ash,ballad,coral,echo,fable,onyx,nova,sage,shimmer,verse]   # default "nova"
TTS_INSTRUCTION = "Speak in a cheerful and positive tone."   # hardcoded

MAX_CHUNK_SIZE = 10000
# chunk split priority: paragraph (\n\n past 50%) > newline > sentence ([.!?]\s) > comma/semicolon > word > hard cut
# per chunk: client.audio.speech.with_streaming_response.create(model, voice, input=chunk,
#            instructions=TTS_INSTRUCTION, response_format="wav") -> temp .wav
# concatenate_wav_files(): hand-write RIFF header (cap size fields at 0xFFFFFFFF) to dodge wave-module 4GB overflow
# clean_markdown_for_speech(): strip headers/bold/italic/code/blockquote/bullets/numbers/links/images

speaker = OpenAISpeaker() if os.getenv("AZURE_OPENAI_API_KEY") else None   # None -> AttributeError at call
```

## Data contracts

```python
class AudioOverviewJob(Base):
    id; user_id(FK,CASCADE); conversable_id:UUID; conversable_type:str  # "paper"|"project"
    status:str  # PENDING|RUNNING|COMPLETED|FAILED|CANCELLED
    status_message:str|None; started_at; completed_at

class AudioOverview(Base):
    id; user_id(FK,CASCADE); conversable_id:UUID; conversable_type:str
    s3_object_key:str; transcript:Text|None  # full script with [^n]
    citations:JSONB|None  # [{index,text}]; title:str|None

class ProjectAudioOverview(Base):  # join: project_id + audio_overview_id
```
- **POST req:** `{additional_instructions?:str, length?:"short"|"medium"|"long"=medium, voice?:str=nova}`.
- **POST resp (202):** `{message, job_id, status:"pending"}`.
- **status resp:** `{job_id, status, status_message, conversable_id, conversable_type}`.
- **file resp:** AudioOverview fields + `paper_id` (back-compat alias) + `audio_url` (presigned).

## Dependencies & assumptions

- `openai` (AzureOpenAI client), `fastapi` (BackgroundTasks), `sqlalchemy` (sync `SessionLocal`),
  `boto3`/custom `s3_service`, stdlib `wave`/`struct`/`tempfile`/`re`/`asyncio`.
- **Env:** `AZURE_OPENAI_API_KEY` (gates the `speaker` singleton), `AZURE_OPENAI_ENDPOINT`,
  `AZURE_OPENAI_VERSION` (default `2025-04-01-preview`), S3 vars.
- Script-gen LLM provider/model (`operations.py`/`provider.py`) NOT confirmed — wire your own.
- Swappable: Azure TTS ↔ any TTS (OpenAI.com, ElevenLabs, on-device); BackgroundTasks ↔ Celery for durability.

## To port this, you need:

- [ ] A script-gen step: structured-output LLM, target-length map, `[^n]` citation convention, single-voice narrative.
- [ ] (multi-doc) an evidence-gathering pass before synthesis.
- [ ] A TTS step: marker-strip + markdown-clean + chunking + per-chunk synth + WAV concat.
- [ ] Job + overview tables, a background runner with its own DB session, a status endpoint, presigned-URL playback.
- [ ] A usage/quota gate if you meter it (and decide whether single-doc is gated — openpaper's isn't).

## Gotchas

- **Strip `[^n]` markers before TTS** or the narrator reads "caret one".
- **Concatenate WAV by hand** (cap RIFF size fields) — Python's `wave` overflows past 4 GB.
- **`speaker` is None without the Azure key** → `AttributeError` at call time, not at startup. Guard it.
- **Paper path drops `length`** (always medium) — forward it if you want short/long on single papers.
- **Timeout is client-triggered** (20 min) — add a real watchdog if jobs can hang.
- **No dedupe/caching** — every request = new job + new file; add an idempotency check if needed.
- **Per-chunk 300s timeout** — a 10k-char chunk on a slow gen can approach it; tune chunk size.
- **Cost gating asymmetry** — function named "...used_this_month" actually checks the week; verify your own limit window.

## Origin (reference only)

khoj-ai/openpaper @ `master`:
`server/app/api/paper_audio_api.py`, `server/app/api/project_audio_api.py`, `server/app/llm/speech.py`
(TTS — inlined), `server/app/llm/paper_operations.py` + `multi_paper_operations.py` (script gen),
`server/app/database/crud/audio_overview_crud.py`, `.../projects/project_audio_overview_crud.py`,
`server/app/database/models.py` (AudioOverviewJob/AudioOverview), `server/app/llm/prompts.py`.

**Gaps to verify:** the LLM model used for script generation (`operations.py`/`provider.py` not fetched);
exact `ResponseCitation` schema; whether `ProjectAudioOverview` join is populated by the task; S3 env var names.
