# Resumable Streaming Search (build spec) — distilled from scira

## Summary

Make LLM streams survive client disconnects and support real mid-stream Stop. Decouple **generation**
(runs to completion server-side, buffered to Redis) from **delivery** (a stream the client can drop
and re-attach to). A POST creates the stream + buffers it; a GET resumes by replaying Redis chunks (or
returns the just-saved message within a freshness window); a DELETE aborts via a shared
AbortController. Built on the Vercel AI SDK + the `ai-resumable-stream` package + Redis pub/sub.

## Core logic (inlined)

**POST `/api/search` — create + buffer:**

```ts
const streamId = 'stream-' + uuidv7();
await createStreamId({ streamId, chatId });           // append row to Postgres `stream` table

const stream = createUIMessageStream<ChatMessage>({
  execute: ({ writer }) => {
    const result = streamText({ model, messages, tools, abortSignal: abortController.signal, /*...*/ });
    result.consumeStream();                            // PULL to completion even if client drops
    writer.merge(result.toUIMessageStream());
  },
  onFinish: async ({ messages }) => {
    const latest = await getLatestStreamIdByChatId({ chatId });
    if (latest !== streamId) return;                   // staleness guard #1: newer stream exists
    if (requestLastUserMessageId !== currentLastUserMessageId) return; // guard #2: newer user turn
    await saveMessages(/* assistant messages + token counts */);
  },
});

const clients = await getResumableStreamClients();     // null if REDIS_URL unset -> fallback
if (!clients) return new Response(stream.pipeThrough(new JsonToSseTransformStream())); // non-resumable

const context = await createResumableUIMessageStream({
  streamId, publisher: clients.publisher, subscriber: clients.subscriber,
  abortController,                                      // shared with streamText for STOP
  waitUntil: after,                                     // Next.js after() — survive past response
});
const resumable = await context.startStream(stream);
return new Response(resumable.pipeThrough(new JsonToSseTransformStream()));
```

**GET `/api/search/[id]/stream` — resume:**

```ts
// auth + chat-ownership check first
const streamIds = await getStreamIdsByChatId({ chatId });   // ASC by createdAt
const recent = streamIds.at(-1);
const context = await createResumableUIMessageStream({ streamId: recent, publisher, subscriber });
const stream = await context.resumeStream();                // replay buffered Redis chunks

if (stream) return new Response(stream.pipeThrough(new JsonToSseTransformStream())); // still live -> catch up

// already ended: replay the just-saved message if fresh
const msg = await getLastMessageByChatId({ chatId });
if (msg?.role === 'assistant' && differenceInSeconds(now, msg.createdAt) <= 15) {
  return oneShotStream({ type: 'data-appendMessage', data: JSON.stringify(msg), transient: true });
}
return emptyDataStream();  // 200, nothing to resume
```

**DELETE `/api/search/[id]/stop` — abort:**

```ts
// NOTE: exports DELETE, not POST, despite the /stop path
const latest = await getLatestStreamIdByChatId({ chatId });   // DESC + id tiebreak
if (!latest) return new Response(null, { status: 204 });
const context = await createResumableUIMessageStream({ streamId: latest, publisher, subscriber });
await context.stopStream();   // signals via Redis -> trips the POST's abortController -> aborts streamText
return new Response(null, { status: 200 });
```

## Data contracts

Postgres `stream` table:
```
id        text PK     -- 'stream-' + uuidv7()
chatId    text FK     -- -> chat.id (cascade delete)
createdAt timestamp
-- index: stream_chatId_idx on (chatId)
```
Resume fallback event:
```ts
{ type: 'data-appendMessage', data: JSON.stringify(dbMessage), transient: true }
```
Redis key/value encoding is internal to `ai-resumable-stream` (you only pass `{ streamId, publisher,
subscriber }`).

## Dependencies & assumptions

- **`ai-resumable-stream`** package → `createResumableUIMessageStream` (NOT `resumable-stream` /
  `createResumableStreamContext`). It owns all Redis buffering.
- Vercel AI SDK `ai`: `createUIMessageStream`, `streamText`, `JsonToSseTransformStream`.
- **Redis** — two persistent connections (publisher + subscriber), `REDIS_URL`. Optional: absent →
  graceful fallback to non-resumable streaming.
- Next.js `after()` (or any `waitUntil`) to keep the function alive past the HTTP response.
- Postgres for stream-id rows + message persistence; `uuidv7` for sortable ids.

## To port this, you need:
- [ ] A pub/sub buffer (Redis) and the `ai-resumable-stream` lib (or equivalent that buffers chunks).
- [ ] A `stream` table (or KV) recording stream-id ↔ chat, append-only, time-sortable ids (uuidv7).
- [ ] `consumeStream()` (pull generation to completion server-side) + a `waitUntil`/`after` so the
      function outlives the response.
- [ ] A shared `AbortController` passed into the model call, tripped by the stop endpoint via the buffer.
- [ ] A resume endpoint: latest stream id → `resumeStream()`; fallback to the just-saved message within
      a freshness window (e.g. 15s); else empty 200.
- [ ] Staleness guards on save: finishing stream is still latest AND last-user-message id unchanged.
- [ ] A graceful non-resumable fallback when the buffer/Redis is unavailable.

## Gotchas

- **Wrong package name wastes hours** — it's `ai-resumable-stream` / `createResumableUIMessageStream`.
- **`consumeStream()` is mandatory**, not optional. Without it the generation pauses when the client
  drops and there's nothing in Redis to resume.
- **The stop route is `DELETE`** even though it's at `/stop`. Wire the client to DELETE, not POST.
- **Forget `waitUntil`/`after` and serverless kills the function** at response end, truncating both
  the generation and the Redis buffer.
- **Both staleness guards matter.** Only checking the stream id misses the case where the user edits/
  resends before the old generation finishes — you'd save a superseded answer.
- **The 15s resume window means late reconnects get nothing** rather than a stale replay — intentional;
  tune to your latency expectations.
- **Multiple stream ids accumulate per chat** — always select the latest (`.at(-1)` ASC, or DESC for
  stop), never assume one stream per chat.

## Origin (reference only)

- Repo: https://github.com/zaidmukaddam/scira
- `app/api/search/route.ts` (POST create+buffer; note line-1 comment mislabels it `/app/api/chat/`),
  `app/api/search/[id]/stream/route.ts` (GET resume), `app/api/search/[id]/stop/route.ts` (DELETE
  abort), `lib/redis.ts` (publisher/subscriber singletons), `lib/db/queries.ts` (`createStreamId`,
  `getStreamIdsByChatId`, `getLatestStreamIdByChatId`), `lib/db/schema.ts` (`stream` table).
- **Verify before relying on:** Redis key/value layout (internal to `ai-resumable-stream`) and the
  client-side resume wiring (whether via `useChat` `experimental_resume` or a manual fetch) were not
  read — confirm against the package + UI component if you need them exact.
