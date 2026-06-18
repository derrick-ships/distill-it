# Per-Contact Conversation Memory — from [whatsapp-agentkit](https://github.com/Hainrixz/whatsapp-agentkit)

> Domain: [[_domain]] · Source: https://github.com/Hainrixz/whatsapp-agentkit · NotebookLM: <add link>

## What it does
It gives the chatbot a memory so each customer's conversation continues naturally instead of resetting every message. Every inbound and outbound message is stored against the customer's phone number, and before the AI answers, the last ~20 messages for that number are pulled back and fed to the model as context. So the bot remembers "the blue one you asked about earlier" within a person's thread — and keeps every customer's thread separate.

## Why it exists
A stateless bot is infuriating: it forgets your name the moment you send a second message. But you also can't dump *all* history into every model call — it's expensive and eventually overflows the context window. The job-to-be-done is "remember enough, per person, cheaply, and survive restarts." The design is deliberately minimal: a single table, keyed by phone number, with a rolling window. Good enough for customer-service threads, and it runs on SQLite locally with zero setup but swaps to PostgreSQL in production by changing one env var.

## How it actually works
1. **One table, `mensajes`** — each row is `{id, telefono, role, content, timestamp}`. `role` is `"user"` or `"assistant"` (the same vocabulary the Claude API uses), `telefono` is indexed because every read filters on it.
2. **Save on both sides** — when a message comes in, the handler stores the user's text *and* the agent's reply, both tagged with the phone number. So the table is a full transcript per contact.
3. **Read a rolling window** — `obtener_historial(telefono, limite=20)` grabs the 20 *most recent* rows for that number (ordered newest-first by timestamp, with a SQL `LIMIT`), then reverses them in memory so they come back oldest-first — the chronological order the model expects. It returns plain `{role, content}` dicts, ready to hand straight to the Claude API.
4. **Order of operations matters** — history is fetched *before* the new message is saved, because the brain appends the new message itself. Fetch-then-save avoids the current message appearing twice.
5. **Async throughout** — built on SQLAlchemy's async engine so it never blocks the FastAPI event loop. The same code runs on `sqlite+aiosqlite` (local) or `postgresql+asyncpg` (prod); the URL is read from `DATABASE_URL`, and a `postgresql://` URL is auto-rewritten to the async `postgresql+asyncpg://` driver.
6. **A `limpiar_historial` escape hatch** wipes a contact's thread — used by the local test simulator's "limpiar" command and handy for "start over."

## The non-obvious parts
- **The rolling window is the whole cost-control strategy.** No summarization, no embeddings — just "last 20 messages." Simple, predictable token cost, and fine for short support chats. It silently forgets older context, which is an accepted trade-off, not a bug.
- **Newest-first query then in-memory reverse** is a classic pattern: you want the *latest* N (so the `ORDER BY timestamp DESC LIMIT 20`), but the model wants them *chronological*, so you flip the list after fetching. Easy to get backwards.
- **`role` reuses the LLM's own vocabulary** (`user`/`assistant`), so the stored rows map onto the Claude `messages` array with zero translation.
- **Phone number is the entire identity model.** There are no user accounts — the contact's phone *is* the session key. Simple, but it means two people sharing a number share a memory, and a number change loses history.
- **Fetch-before-save ordering is a subtle correctness rule.** Because `brain.py` adds the new user message to the array it sends, saving the new message *before* reading history would duplicate it in the prompt. The handler and the test harness both follow fetch-then-save.
- **SQLite-to-Postgres with one variable** is what makes "free local, real in prod" work without a code change — the async-driver rewrite is the small bit of glue that makes it seamless.

## Related
- [[whatsapp-provider-adapter--from-whatsapp-agentkit]] — supplies the normalized `telefono` this memory keys on.
- [[interview-driven-scaffolding--from-whatsapp-agentkit]] — the kit that generates this memory module.
- See also: [[agent-output-contract--from-last30days-skill]] — another piece of the agent-architecture domain (constraining LLM behavior rather than storing its state).
