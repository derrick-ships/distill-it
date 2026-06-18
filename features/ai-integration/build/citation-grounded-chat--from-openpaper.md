# Citation-Grounded Chat (build spec) — distilled from openpaper

## Summary

A RAG chat where the LLM answers **only from pre-extracted evidence snippets** and tags every claim
with an inline `@cite[n]` marker that is parsed back into clickable, source-anchored footnotes. Works
for a single document and for a multi-document corpus. Two-phase: (1) an agentic **evidence-gathering**
pass extracts verbatim snippets relevant to the question; (2) a **generation** pass answers from those
snippets and emits inline citation markers. A no-embeddings re-anchoring step maps citations from
compacted summaries back to original quotes. Streaming uses a delimiter-framed JSON protocol.

## Core logic (inlined)

### The citation grammar + evidence block

Evidence handed to the model is a single labelled text block. Single-paper marker is `@cite[key]`;
multi-paper is `@cite[key|paper_id]`. Builder (from `CitationHandler.format_citations`):

```python
def format_citations(citations: list[dict]) -> str:
    out = "---EVIDENCE---\n"
    parts = []
    for c in citations:
        if "paper_id" in c:
            marker = f"@cite[{c['key']}|{c['paper_id']}]"   # multi-paper
        else:
            marker = f"@cite[{c['key']}]"                    # single paper
        parts.append(f"{marker}\n{c['reference']}")
    out += "\n".join(parts) + "\n---END-EVIDENCE---"
    return out
```

The generation system prompt must instruct: *answer the question, and whenever you state something
supported by the evidence, append the matching `@cite[n]` marker.* (The exact prompt lives in
`app/llm/prompts.py`, not fetched — write your own; the contract is "cite inline using the markers
you were given.")

### Parsing markers back out of the answer

```python
def parse_evidence_block(evidence_text: str) -> list[dict]:
    citations, current, lines_buf = [], None, []
    for line in evidence_text.strip().split("\n"):
        line = line.strip()
        if line.startswith("@cite["):
            if current is not None:
                current["reference"] = " ".join(lines_buf).strip(); citations.append(current)
            m = re.search(r"@cite\[(\d+)\]", line)            # single-paper
            if m:
                current = {"key": int(m.group(1)), "reference": ""}; lines_buf = []
        elif current is not None and line:
            lines_buf.append(line)
    if current is not None and lines_buf:
        current["reference"] = " ".join(lines_buf).strip(); citations.append(current)
    return citations
```

Multi-paper variant uses `re.search(r"@cite\[(\d+)\|([^]]+)\]", line)` and stores `paper_id` too.

### Re-anchoring compacted citations (the clever, no-embeddings part)

When evidence is compacted (summarized to fit context), each summary carries `[@n]` back-pointers to
original snippets, indexed by a `"{paper_id}:{snippet_idx}"` sidecar key.

```python
def resolve_compacted_citations(citations, citation_index):
    resolved = []
    for c in citations:
        paper_id, ref = c.get("paper_id"), c.get("reference", "")
        markers = re.findall(r"\[@(\d+)\]", ref)
        if markers and paper_id:
            texts = []
            for idx in markers:
                orig = citation_index.index.get(f"{paper_id}:{idx}")
                if orig and orig.text not in texts:
                    texts.append(orig.text)
            if texts:
                resolved.append({"key": c["key"], "reference": " [...] ".join(texts), "paper_id": paper_id}); continue
        best = _find_best_match(ref, paper_id, citation_index)   # word-overlap fallback
        resolved.append({"key": c["key"], "reference": best.text, "paper_id": paper_id} if best else c)
    return resolved

def _find_best_match(reference, paper_id, citation_index):
    if not paper_id: return None
    cands = [s for k, s in citation_index.index.items() if s.paper_id == paper_id]
    ref_words = set(reference.lower().split())
    best, best_score = None, 0
    for s in cands:
        overlap = len(ref_words & set(s.text.lower().split()))
        if overlap > best_score: best_score, best = overlap, s
    return best if best_score >= 3 else None     # require >=3 word overlap
```

### Endpoint + streaming protocol (FastAPI)

Two POST routes, both return `StreamingResponse(media_type="text/event-stream")`:
- `POST /chat/paper` — body `{paper_id, conversation_id, user_query, user_references?, style?, llm_provider?}` → `operations.chat_with_paper(...)`.
- `POST /chat/everything` — body `{conversation_id, user_query, user_references?, llm_provider?, project_id?}` → first `operations.gather_evidence(...)` then `operations.chat_with_papers(...)`.

Wire format: each event is `json.dumps({...}) + "END_OF_STREAM"` (a literal string delimiter, NOT
SSE `data:` framing). Event `type`s the client must handle:

| type | content | client action |
|------|---------|---------------|
| `status` | progress string | show spinner text (dedupe consecutive dupes) |
| `content` | answer text chunk | append to message body |
| `references` | evidence list | store as the message's citations |
| `trace` | `{tool calls, status_messages}` | render the "how it searched" trajectory |
| `artifact` | rich object (e.g. citation card) | render as a card; also persisted separately |
| `error` | error string | show error |

Generation loop (multi-paper, abridged from `message_api.py`):

```python
async def response_generator():
    evidence_collection = None
    async for chunk in operations.gather_evidence(conversation_id, question, current_user,
                                                  llm_provider=LLMProvider.CEREBRAS,  # pinned fast provider
                                                  user_references=..., db=db, project_id=...):
        if chunk["type"] == "evidence_gathered":
            evidence_collection = chunk["content"]   # EvidenceCollection (evidence[], artifacts[], is_compacted, citation_index)
        elif chunk["type"] == "status":
            yield json.dumps({"type":"status","content":chunk["content"]}) + "END_OF_STREAM"

    if not evidence_collection or (not evidence_collection.evidence and not evidence_collection.artifacts):
        yield json.dumps({"type":"content","content":"couldn't find relevant papers…"}) + "END_OF_STREAM"; return

    yield json.dumps({"type":"status","content":"Generating response..."}) + "END_OF_STREAM"
    async for sc in stream_chat(operations.chat_with_papers(question, llm_provider=req.llm_provider,
                                evidence_gathered=evidence_collection, all_papers=..., db=db)):
        yield sc   # content / references / artifact chunks
    # persist user msg, assistant msg (content + references=evidence + trace), artifacts to their own table
```

After streaming, persist: user message (with `references` from `convert_references_to_dict`), then
assistant message (`content`, `references=evidence`, `trace=assistant_trace`), then any artifacts via
a separate artifacts table keyed by `message_id`.

## Data contracts

**EvidenceCollection** (returned by the evidence pass): `evidence: list[snippet]`, `artifacts: list`,
`is_compacted: bool`, `citation_index: CitationIndex`, plus `to_trace_dict()`.
**CitationIndex**: `.index: dict["{paper_id}:{idx}", OriginalSnippet]`; **OriginalSnippet**: `{paper_id, text}`.
**ResponseCitation**: `{index:int, text:str, paper_id:str}`.
**Citation dict** (internal): `{key:int, reference:str, paper_id?:str}`.
**Persisted message**: `{conversation_id, role:"user"|"assistant", content:str, references: {citations:[...]}|None, trace: dict|None}`.
**Artifact**: own table, `kind="citation"`, payload = citation-card object, linked by `message_id`.

User-supplied references (the user pasted quotes) are converted with:
```python
def convert_references_to_dict(refs): return {"citations":[{"key":i+1,"reference":r} for i,r in enumerate(refs)]}
```

## Dependencies & assumptions

- **FastAPI** streaming (`StreamingResponse`), **SQLAlchemy** for message/artifact/conversation CRUD.
- **LLM provider abstraction** (`app/llm/provider.py`, `base.py`): a fast provider (Cerebras, used for
  evidence gathering, OpenAI-compatible, multi-turn tool calls) and one or more answer providers
  selectable per request. Swappable for any provider with tool-calling + structured output.
- An **evidence-gathering agent** with file tools (`search_all_files`, `read_abstract`, `search_file`,
  `view_file`, `read_file`, `STOP`) over the corpus — see `app/llm/tools/file_tools.py`.
- Source text + page offsets must already exist per paper (see [[pdf-ingestion-pipeline--from-openpaper]]).
- Env: provider API keys. No vector DB required.

## To port this, you need:

- [ ] A per-document (and/or per-corpus) **evidence extractor** returning verbatim snippets keyed by id.
- [ ] An **evidence-block formatter** using the `@cite[key]` / `@cite[key|paper_id]` grammar.
- [ ] A **generation prompt** that instructs inline `@cite[n]` marking, fed the evidence block.
- [ ] A **parser** (`parse_evidence_block`) + **resolver** (`resolve_compacted_citations` + word-overlap fallback).
- [ ] A **streaming endpoint** emitting delimiter-framed JSON events (`content`/`references`/`status`/`trace`/`artifact`).
- [ ] Message + artifact persistence tables; a conversation model.
- [ ] A frontend that splits on the delimiter and renders footnotes from `references`.

## Gotchas

- **The model must only ever see evidence, never the raw doc**, or hallucinated citations creep back.
- **Two marker grammars** (`@cite[n]` vs `@cite[n|paper_id]`) — pick the parser variant to match the block you built, or citations silently drop.
- **Compaction is the failure mode.** If you summarize evidence you MUST keep a `{paper_id}:{idx}`
  index and `[@n]` back-pointers, or re-anchoring falls through to lossy fuzzy matching.
- **Word-overlap threshold = 3** is arbitrary; too low mis-anchors, too high drops valid citations.
- **Delimiter framing, not SSE.** Clients expecting `data:` SSE break — it's `<json>END_OF_STREAM<json>…`.
- **Persist the trace** or reloads lose the "why"; fold status messages into the trace even with no tool calls.
- Evidence pass empty → short-circuit with a friendly message before calling the answer model.

## Origin (reference only)

khoj-ai/openpaper @ `master`:
`server/app/llm/citation_handler.py` (format/parse/resolve — fully inlined above),
`server/app/api/message_api.py` (both chat endpoints + streaming),
`server/app/llm/conversation_operations.py`, `server/app/llm/operations.py` (`gather_evidence`,
`chat_with_paper`, `chat_with_papers` — orchestration; not fully fetched),
`server/app/llm/citation_recovery.py` (the *metadata* recovery agent — separate concern),
`server/app/llm/prompts.py` (generation/evidence prompts — NOT fetched; write your own).

**Gaps to verify before relying:** exact generation + evidence-gathering prompts; the precise
`EvidenceCollection`/`CitationIndex` Pydantic definitions (`app/schemas/message.py`); how
`gather_evidence` decides to compact; the artifact/citation-card payload schema.
