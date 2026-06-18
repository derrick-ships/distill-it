# Per-Contact Conversation Memory (build spec) — distilled from whatsapp-agentkit

## Summary
A minimal, async, per-contact chat memory: one table keyed by a contact id (here a phone number), storing every `user`/`assistant` turn; reads return a rolling window of the last N turns in chronological order, shaped exactly like an LLM `messages` array. SQLAlchemy async engine; same code on SQLite (local, zero-setup) or PostgreSQL (prod) via one env var. The cost-control strategy is the window cap — no summarization, no embeddings.

## Core logic (inlined)
```python
import os
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, Integer, select
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentkit.db")
# auto-upgrade a sync postgres URL to the async driver so prod works unchanged:
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase): pass

class Mensaje(Base):
    __tablename__ = "mensajes"
    id:        Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    telefono:  Mapped[str]      = mapped_column(String(50), index=True)   # contact id — INDEXED
    role:      Mapped[str]      = mapped_column(String(20))               # "user" | "assistant"
    content:   Mapped[str]      = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

async def inicializar_db():                       # call once at startup (lifespan)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def guardar_mensaje(telefono: str, role: str, content: str):
    async with async_session() as s:
        s.add(Mensaje(telefono=telefono, role=role, content=content, timestamp=datetime.utcnow()))
        await s.commit()

async def obtener_historial(telefono: str, limite: int = 20) -> list[dict]:
    async with async_session() as s:
        q = (select(Mensaje)
             .where(Mensaje.telefono == telefono)
             .order_by(Mensaje.timestamp.desc())   # newest first...
             .limit(limite))                        # ...take last N
        rows = (await s.execute(q)).scalars().all()
        rows.reverse()                              # ...then flip to chronological
        return [{"role": m.role, "content": m.content} for m in rows]

async def limpiar_historial(telefono: str):         # wipe one contact's thread
    async with async_session() as s:
        rows = (await s.execute(select(Mensaje).where(Mensaje.telefono == telefono))).scalars().all()
        for m in rows: s.delete(m)
        await s.commit()
```

### Caller contract (the ordering rule)
```python
historial = await obtener_historial(telefono)          # 1) READ first
respuesta = await generar_respuesta(texto, historial)  # 2) brain appends the new msg itself
await guardar_mensaje(telefono, "user", texto)         # 3) THEN save both turns
await guardar_mensaje(telefono, "assistant", respuesta)
```
Fetch-before-save: the brain adds the current user message to the array it sends to the model, so saving it first would duplicate it in the prompt.

## Data contracts
- **Table `mensajes`:** `id:int pk autoinc`, `telefono:str(50) indexed`, `role:str(20) ∈ {user,assistant}`, `content:text`, `timestamp:datetime (UTC, default utcnow)`.
- **`obtener_historial` returns:** `list[{"role": "user"|"assistant", "content": str}]` in chronological order — directly usable as the Claude API `messages` array.
- **`DATABASE_URL`:** `sqlite+aiosqlite:///./agentkit.db` (local) or `postgresql+asyncpg://user:pass@host:5432/db` (prod). A `postgresql://` value is auto-rewritten to `postgresql+asyncpg://`.

## Dependencies & assumptions
- `sqlalchemy>=2.0` (async ORM, typed `Mapped`/`mapped_column`), `aiosqlite` (local driver), `asyncpg` (prod driver), `python-dotenv`.
- Runs inside an async app (FastAPI here) — `inicializar_db()` is called in the startup lifespan.
- Contact id is a phone number string; swap the column meaning for any stable per-user key.
- `datetime.utcnow` is naive-UTC (note: deprecated in Python 3.12+; prefer `datetime.now(timezone.utc)` in a port).

## To port this, you need:
- [ ] An async SQL engine/session (or adapt to your ORM); call the init once at startup.
- [ ] A messages table keyed + indexed on your contact/session id, with `role`/`content`/`timestamp`.
- [ ] A read that takes the latest N by timestamp then reverses to chronological, returning LLM-shaped dicts.
- [ ] A caller that fetches history *before* persisting the new turn.
- [ ] (Optional) a clear/reset function per contact.

## Gotchas
- **Reverse after the DESC+LIMIT query** — forget it and the model gets history backwards.
- **Fetch-then-save ordering** — save-then-fetch duplicates the current message in the prompt.
- **The window silently drops old context** — 20 turns only. For long or high-stakes threads add summarization or raise the cap; know it forgets.
- **Phone number == identity** — shared numbers share memory; a number change orphans history. No auth boundary.
- **No automatic pruning** — the table grows forever; only reads are bounded. Add retention/archival for volume.
- **`datetime.utcnow` deprecation** on 3.12+ — switch to timezone-aware `now(timezone.utc)` when porting.
- **Index on `telefono` is load-bearing** — every read filters on it; dropping the index tanks performance as the table grows.

## Origin (reference only)
Repo: https://github.com/Hainrixz/whatsapp-agentkit · Code lives inline in `CLAUDE.md` (§3.6), generated into `agent/memory.py` at build time.
