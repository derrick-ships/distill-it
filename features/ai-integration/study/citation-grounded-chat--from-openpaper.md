# Citation-Grounded Chat — from [openpaper](https://github.com/khoj-ai/openpaper)

> Domain: [[_domain]] · Source: https://github.com/khoj-ai/openpaper · NotebookLM: <link once added>

## What it does

You're reading a paper and you ask the assistant a question — "what dataset did they train on?" The
answer comes back, and every claim in it is footnoted with the **exact sentence from the PDF** it
came from. Click a footnote and you jump to that spot in the document. It's the difference between a
chatbot that *sounds* confident and one that *shows its receipts*. Open Paper does this for a single
paper and for your whole library at once.

## Why it exists

The whole product premise is "understand papers you'd otherwise skim." A generic LLM chat over a PDF
hallucinates — it'll invent a citation or paraphrase something the paper never said. For research,
that's worse than useless. So Open Paper forces the model to answer **only from evidence it has
pulled out of the actual document**, and to tag every statement with which piece of evidence backs
it. The grounding is the feature; the chat is just the delivery mechanism.

## How it actually works

There are two phases, and keeping them separate is the clever part.

**Phase 1 — gather evidence.** Before the model writes a single word of answer, a separate agentic
pass reads the paper(s) and pulls out the specific quotes relevant to your question. For one paper
this is fast; for "search everything" it's an agent with file-reading tools (search, read abstract,
read section) that hunts across your corpus and stops when it has enough. The output is an
**evidence collection**: a numbered list of verbatim snippets, each tagged with which paper it came
from.

**Phase 2 — answer from evidence.** Those snippets get formatted into a labelled block that looks
like:

```
---EVIDENCE---
@cite[1]
"We fine-tuned on the 12k-example SQuAD subset."
@cite[2]
"All experiments used a single A100."
---END-EVIDENCE---
```

The model is told: answer the question, and whenever you assert something, mark it with the matching
`@cite[1]` tag. The answer streams back to the screen token-by-token. On the way out, the system
parses those `@cite[n]` tags back into structured citations, attaches the real source text to each,
and the UI turns them into clickable footnotes.

**The streaming protocol** is deliberately simple: the server emits a sequence of small JSON objects,
each followed by a literal `END_OF_STREAM` delimiter, of types `status` (progress: "Generating
response…"), `content` (a chunk of the answer), `references` (the evidence), `trace` (the agent's
thinking trajectory, so it survives a page reload), and `artifact` (a richer object like a citation
card). The client splits on the delimiter and routes each by type.

**The recovery trick.** For big corpora the evidence is sometimes *compacted* — the agent summarizes
many snippets to fit the context window, leaving little `[@3]` markers pointing back to the originals.
When the model then cites the summary, the system has to walk those markers back to the *real*
sentences (looked up by a `paper_id:index` key). If a citation can't be resolved by marker, it falls
back to **word-overlap matching** — find the original snippet that shares the most words with what
the model cited, and only accept it if at least three words overlap. It's a cheap, no-embeddings way
to re-anchor a paraphrased citation to a real quote.

There's a second, unrelated "recovery" agent in the codebase worth not confusing with this one: a
**metadata** recovery agent that, when a paper is missing its journal/DOI/date, runs a small
web-search-plus-scrape loop (Exa + Firecrawl) to find them, and only writes back fields it's ≥70%
confident about, never overwriting what's already there. Same "be honest about confidence" spirit,
different job.

## The non-obvious parts

- **Evidence-first, not answer-first.** The model never sees the raw PDF and "decides" what to cite.
  It only ever sees a pre-extracted evidence block. This is what makes hallucinated citations nearly
  impossible — there's nothing to cite *except* the snippets it was handed.
- **Two citation grammars.** Single-paper uses `@cite[1]`; multi-paper uses `@cite[1|paper_id]` so a
  footnote knows which document to open. The parser handles both.
- **Word-overlap fallback over embeddings.** They chose a dumb-but-instant heuristic (set
  intersection of lowercased words, threshold 3) rather than a vector similarity call. For
  re-anchoring a citation it's good enough and adds zero latency or cost.
- **The provider split.** Evidence gathering is pinned to one fast provider (Cerebras); the final
  answer's model is user-selectable. Cheap fast model does the grunt reading; the nicer model writes.
- **The trace is persisted.** The agent's status messages and tool calls are saved with the message,
  so reopening a conversation still shows *how* it found the answer, not just the answer.

## Related
- [[corpus-and-academic-search--from-openpaper]] (the "search everything" evidence pass leans on the
  same corpus the search feature queries)
- [[pdf-ingestion-pipeline--from-openpaper]] (evidence snippets come from the `raw_text` + page
  offsets that the ingestion pipeline produced)
- [[pdf-highlights-annotations--from-openpaper]] (AI can write `assistant`-role highlights — citations
  and highlights share the same anchoring substrate)
- See also: any RAG chat — the differentiator here is *forced* inline attribution + a no-embeddings
  re-anchor step.
