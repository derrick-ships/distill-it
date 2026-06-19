# PDF Highlights & Annotations (build spec) — distilled from openpaper

## Summary

Anchored highlights on a rendered PDF, with notes ("annotations") attached to highlights, plus one
free-form note per paper. Highlights store both the **raw selected text** and a **scaled-rects
position blob** (react-pdf-highlighter style, zoom-invariant), with legacy char-offset fields kept for
back-compat. Every row is role-stamped `user`/`assistant`; assistant rows are immutable via the API.
A `zotero_annotation_key` + partial unique index makes Zotero highlight import idempotent.

## Core logic (inlined)

### Data model (SQLAlchemy, Postgres)

```python
class HighlightType(str, Enum):           # AI highlight categories
    TOPIC="topic"; MOTIVATION="motivation"; METHOD="method"; EVIDENCE="evidence"
    RESULT="result"; IMPACT="impact"; GENERAL="general"

class Highlight(Base):
    __tablename__ = "highlights"
    id            = Column(UUID, primary_key=True, default=uuid4)
    paper_id      = Column(UUID, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    raw_text      = Column(Text, nullable=False)              # the selected text, stored redundantly
    type          = Column(String, nullable=True)             # HighlightType value (AI highlights)
    # legacy text-offset anchoring (kept for back-compat):
    start_offset  = Column(Integer, nullable=True)
    end_offset    = Column(Integer, nullable=True)
    page_number   = Column(Integer, nullable=True)
    # modern anchoring: scaled-rects "ScaledPosition" JSON
    position      = Column(JSONB, nullable=True)
    role          = Column(String, nullable=False, default="user")   # 'user' | 'assistant'
    user_id       = Column(UUID, ForeignKey("users.id"), nullable=True)
    color         = Column(String, nullable=True, default="blue")    # yellow|green|blue|pink|purple
    zotero_annotation_key = Column(String, nullable=True)
    __table_args__ = (
        Index("uq_highlight_paper_zotero_annotation_key", "paper_id", "zotero_annotation_key",
              unique=True, postgresql_where=(zotero_annotation_key.isnot(None))),   # partial unique → idempotent Zotero import
    )
    annotations = relationship("Annotation", back_populates="highlight",
                               cascade="all, delete-orphan")

class Annotation(Base):
    __tablename__ = "annotations"
    id           = Column(UUID, primary_key=True, default=uuid4)
    highlight_id = Column(UUID, ForeignKey("highlights.id"), nullable=False)   # note hangs off a highlight
    paper_id     = Column(UUID, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False)
    content      = Column(Text, nullable=False)
    role         = Column(String, nullable=False, default="user")              # 'user' | 'assistant'
    user_id      = Column(UUID, ForeignKey("users.id"), nullable=False)

class PaperNote(Base):                     # one scratchpad note per paper
    __tablename__ = "paper_notes"
    id       = Column(UUID, primary_key=True, default=uuid4)
    paper_id = Column(UUID, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False, unique=True)
    content  = Column(Text, nullable=False)
    user_id  = Column(UUID, ForeignKey("users.id"), nullable=True)
```

### The `position` / ScaledPosition blob (the anchor)

The `position` JSONB is the react-pdf-highlighter "ScaledPosition" shape — coordinates normalized
against page dimensions so they survive zoom/resize. Concrete shape (verify against the client; the
server stores it opaquely as `dict[str, Any]`):

```jsonc
{
  "boundingRect": { "x1":  .., "y1":  .., "x2":  .., "y2":  ..,
                    "width": <pageWidthAtCapture>, "height": <pageHeightAtCapture>, "pageNumber": 3 },
  "rects": [ { "x1": .., "y1": .., "x2": .., "y2": ..,
               "width": .., "height": .., "pageNumber": 3 } ],   // one per visual line
  "pageNumber": 3
}
```
To re-render: for each rect, multiply normalized coords by the *current* rendered page size → absolute
pixels → draw a colored box. Because width/height captured at selection time are stored, the viewer
rescales correctly at any zoom.

### API (FastAPI; all routes require an authenticated user)

Highlights (`highlight_router`):
- `POST ""` body `CreateHighlightRequest{paper_id, raw_text, position?, color?, start_offset?, end_offset?, page_number?}` → 201 `highlight.to_dict()`.
- `GET "/{paper_id}"` → list of `to_dict()` for that doc.
- `PATCH "/{highlight_id}"` body `UpdateHighlightRequest{raw_text, position?, color?, start_offset?, end_offset?}` → 200. **403 if `role == assistant`.**
- `DELETE "/{highlight_id}"` → 200. **403 if `role == assistant`; 404 if not owned.**

Annotations (`annotation_router`), identical pattern:
- `POST ""` body `{paper_id, highlight_id, content}` → 201. (create REQUIRES an existing highlight_id)
- `GET "/{paper_id}"`, `PATCH "/{annotation_id}"` body `{content}`, `DELETE "/{annotation_id}"`.
- Same **assistant-immutability 403** guard on update/delete.

Create handler shape:
```python
@highlight_router.post("")
async def create_highlight(request, db, current_user=Depends(get_required_user)):
    h = highlight_crud.create(db, obj_in=HighlightCreate(
        paper_id=UUID(request.paper_id), raw_text=request.raw_text,
        start_offset=request.start_offset, end_offset=request.end_offset,
        page_number=request.page_number, position=request.position,
        role=RoleType.USER, color=request.color), user=current_user)
    track_event("highlight_created", user_id=str(current_user.id), db=db)
    return JSONResponse(201, h.to_dict())
```

## Data contracts

- **Create highlight (req):** `{paper_id:str, raw_text:str, position?:ScaledPosition, color?:str, start_offset?:int, end_offset?:int, page_number?:int}`
- **Create annotation (req):** `{paper_id:str, highlight_id:str, content:str}`
- **Highlight (resp `to_dict`):** highlight columns above + ids as strings.
- **Colors:** `yellow|green|blue|pink|purple` (default `blue`).
- **Roles:** `user|assistant` (string). Assistant rows are read-only to users.

## Dependencies & assumptions

- **Postgres** (JSONB for `position`, partial unique index for Zotero dedupe).
- **FastAPI + SQLAlchemy**; an auth dependency `get_required_user`; a `track_event` telemetry hook (optional).
- **Frontend:** a PDF viewer that can (a) capture a selection as a ScaledPosition and (b) re-draw
  rects. openpaper's client uses a react-pdf-highlighter-style layer over pdf.js (client file not
  fetched — verify exact lib).
- Cascade deletes assume FK `ON DELETE CASCADE` on `paper_id`, and ORM `cascade="all, delete-orphan"`
  from highlight → annotations.

## To port this, you need:

- [ ] Highlights, annotations, paper_notes tables (schema above) with the partial unique Zotero index.
- [ ] A client selection→ScaledPosition capture and a rect re-render layer over your PDF renderer.
- [ ] CRUD endpoints with the **assistant-role immutability** guard.
- [ ] `raw_text` stored alongside `position` (don't rely on geometry alone).
- [ ] If importing Zotero highlights: set `zotero_annotation_key` so re-sync is idempotent.

## Gotchas

- **Don't anchor by absolute pixels.** Use scaled rects + stored capture dimensions or highlights drift on zoom/resize.
- **Store `raw_text` redundantly** — it's the search payload and the AI-quote source; geometry alone is brittle across re-parse.
- **Annotations require a highlight_id** — there's no free-floating page annotation; model it as note-on-highlight.
- **PaperNote is unique per paper** — upsert, don't insert, or you hit the unique constraint.
- **Assistant rows are first-class but immutable via API** — enforce the 403 or AI-cited evidence becomes user-mutable.
- **Two anchoring schemes** — new code should prefer `position`; keep offsets only to read old rows.

## Origin (reference only)

khoj-ai/openpaper @ `master`:
`server/app/api/highlight_api.py`, `server/app/api/annotation_api.py` (endpoints — inlined above),
`server/app/database/models.py` (Highlight/Annotation/PaperNote classes — inlined verbatim),
`server/app/database/crud/highlight_crud.py`, `.../annotation_crud.py`, `.../paper_note_crud.py`.

**Gaps to verify:** exact client-side ScaledPosition capture/render code (client/ not fetched) and the
precise JSON keys in `position`; `to_dict()` output fields; how Zotero import sets `zotero_annotation_key`.
