# PDF Highlights & Annotations — from [openpaper](https://github.com/khoj-ai/openpaper)

> Domain: [[_domain]] · Source: https://github.com/khoj-ai/openpaper · NotebookLM: <link once added>

## What it does

You drag-select a sentence in the PDF and it stays lit up in a color of your choice. You can attach a
note to that highlight ("this is the key claim"), and later jump straight back to it. There's also a
single free-form scratchpad note per paper. Some highlights aren't yours — the AI can drop its own
highlights on the passages it cited, color-coded by what kind of thing they are (method, result,
motivation…). Those AI ones you can see but can't edit or delete.

## Why it exists

Reading a dense paper is an act of marking-up. The highlights and notes are how a reader externalizes
understanding, and — crucially — they become **searchable memory**: the knowledge-base search indexes
your highlight text and note content, so "that thing I marked about transformers last month" is
findable. Highlights are also the substrate the AI uses to point at evidence, so the same machinery
serves both human and assistant.

## How it actually works

A highlight stores two things: the **raw selected text** (so it's human-readable and searchable even
if the document re-renders), and a **position** describing *where on the page* it sits. The position
is the interesting bit. Open Paper keeps two anchoring schemes side by side:

- A modern **`position` blob** — a "scaled position" JSON (bounding rectangle + per-line rectangles +
  page number, with coordinates normalized to the page size). This is the react-pdf-highlighter style
  of anchor: because the rects are scaled to the page rather than absolute pixels, the highlight lands
  in the right place no matter the zoom level or viewport width.
- **Legacy character offsets** — `start_offset` / `end_offset` / `page_number`. Kept around for
  backwards compatibility with older highlights that were anchored by position-in-text.

An **annotation** is a note *attached to a highlight* — it has a `highlight_id`, a `paper_id`, and
the note `content`. So the data model is: paper → highlights → annotations. Deleting a highlight
cascades and removes its annotations.

A **paper note** is separate: one free-form markdown note per paper (enforced unique on `paper_id`),
a scratchpad rather than an anchored mark.

Everything is **role-stamped** `user` or `assistant`. The API refuses to let a user edit or delete an
`assistant` highlight or annotation (HTTP 403). AI highlights additionally carry a `type` from a small
enum — topic, motivation, method, evidence, result, impact, general — which is how the UI color-codes
or labels them.

The endpoints are plain CRUD:
- Highlights: `POST` create, `GET /{paper_id}` list-for-doc, `PATCH /{id}` update, `DELETE /{id}`.
- Annotations: same shape, plus the create requires both `paper_id` and `highlight_id`.

There's one more quiet detail: a highlight can carry a `zotero_annotation_key`, with a partial unique
index on `(paper_id, zotero_annotation_key)`. That's the hook that lets the Zotero import bring in a
user's existing Zotero highlights without creating duplicates on re-sync.

## The non-obvious parts

- **Two anchoring schemes coexist** on purpose. New highlights use the scaled-rects `position` blob;
  old ones still resolve via char offsets. A port should pick the scaled-rects model and treat offsets
  as a fallback.
- **`raw_text` is stored redundantly** with the position. That redundancy is a feature: it survives
  re-parsing, powers search, and gives the AI something to quote even if the geometry drifts.
- **Annotations hang off highlights, not off the page.** You can't annotate arbitrary coordinates —
  you annotate a thing you already highlighted. Simpler model, fewer orphans.
- **Role-based immutability.** AI-authored marks are first-class rows but protected from user edits,
  which keeps the "evidence the AI cited" stable.
- **Zotero dedupe key baked into the schema.** The partial unique index is what makes re-importing a
  Zotero library idempotent.

## Related
- [[citation-grounded-chat--from-openpaper]] (AI writes `assistant`-role highlights for cited passages — same table)
- [[corpus-and-academic-search--from-openpaper]] (highlight `raw_text` and annotation `content` are searched by the knowledge-base query)
- [[multi-path-auth--from-openpaper]] (Zotero OAuth is what feeds the `zotero_annotation_key` dedupe path)
- See also: react-pdf-highlighter, W3C Web Annotation / Hypothesis position-and-quote anchoring.
