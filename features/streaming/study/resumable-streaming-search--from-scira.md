# Resumable Streaming Search — from [scira](https://github.com/zaidmukaddam/scira)

> Domain: [[_domain]] · Source: https://github.com/zaidmukaddam/scira · NotebookLM: <link once added>

## What it does

When Scira is mid-answer and you refresh the page, switch tabs, or briefly lose your connection, you
don't lose the generation — reconnect and the answer keeps streaming from where it was, or if it
already finished while you were gone, you get the completed message. There's also a Stop button that
genuinely halts the model mid-stream, not just hides the output.

## Why it exists

LLM answers take many seconds, sometimes minutes (deep research). Over that window, browsers reload,
phones sleep, networks blip. A naive `fetch`-and-stream loses everything on disconnect — the server
keeps paying for tokens you'll never see, and the user has to start over. Resumable streaming
decouples *generating* the answer (server-side, runs to completion no matter what the client does)
from *delivering* it (a stream the client can drop and re-attach to). The result feels robust:
generation is durable, viewing is reconnectable.

## How it actually works

The trick is buffering the stream through Redis so multiple connections can read the same generation.

**Starting (POST `/api/search`).** Before generating, the server mints a stream id
(`'stream-' + uuidv7()`) and writes it to a Postgres `stream` table row `{ id, chatId, createdAt }`
(append-only — a chat can have many streams). It builds the model's output stream, then wraps it with
`createResumableUIMessageStream({ streamId, publisher, subscriber, abortController, waitUntil })` from
the `ai-resumable-stream` package. That library publishes every chunk to Redis under the stream id as
it flows. Crucially the server calls `result.consumeStream()` so the model stream is pulled to
completion **even if the client disconnects**, and passes Next.js's `after()` as `waitUntil` so the
serverless function stays alive past the HTTP response to finish publishing. The response to the
client is the same stream, piped through `JsonToSseTransformStream`.

**Resuming (GET `/api/search/[id]/stream`).** On reconnect the client hits this route. It finds the
chat's latest stream id (`getStreamIdsByChatId` → `.at(-1)`), re-opens the resumable context for that
id, and calls `context.resumeStream()`, which replays the buffered Redis chunks. If the stream is
still live, the client catches up to real-time. If it already ended (`resumeStream()` returns null),
the route looks at the last saved assistant message: if it was created within the **last 15 seconds**,
it synthesizes a one-shot stream emitting a `data-appendMessage` event with the serialized message
(marked `transient`); older than 15s, it returns an empty 200. That 15s window avoids replaying stale
content after a long absence.

**Stopping (DELETE `/api/search/[id]/stop`).** The Stop button calls this. It looks up the latest
stream id and calls `context.stopStream()`, which signals through Redis; that trips the shared
`abortController` from the POST handler, whose signal was passed to the model call — so generation
actually aborts. (Note: the file is `stop/route.ts` but it exports `DELETE`, not `POST`.)

**Persistence.** When the stream finishes (or aborts with partial output), an `onFinish` callback
saves the assistant message — but only after two staleness guards: the finishing stream must still be
the latest stream for the chat, and the request's last user-message id must still match (the user
hasn't sent a newer turn). On abort, only messages with at least one non-empty part are saved.

Redis is *optional*: if `REDIS_URL` isn't set, both routes detect the missing clients and fall back to
plain, non-resumable streaming.

## The non-obvious parts

- **Generation is durable; delivery is reconnectable.** The model stream runs to completion server-
  side via `consumeStream()` + `after()` regardless of the client — that's what makes resume possible.
- **It's `ai-resumable-stream`, not `resumable-stream`.** The function is
  `createResumableUIMessageStream`, not the older Vercel `createResumableStreamContext`. Searching for
  the wrong name finds nothing.
- **Stop is a real abort, plumbed through Redis → abortController → the model call.** Not a UI trick.
- **Two independent staleness guards** (stream id *and* last-user-message id) before saving — either
  one being stale means a newer turn superseded this one.
- **The 15-second resume window** is a deliberate freshness cutoff for the "already finished" case.
- **The stop route exports `DELETE`** despite living at `/stop` — easy to mis-wire on the client.

## Related
- [[agentic-research-planning--from-scira]] (the long generations that make resume necessary)
- [[stream-output-transcoding--from-vlc]] (streaming in a very different domain — media)
- [[streaming-partial-objects--from-llm-scraper]] (streaming partial LLM output, different mechanism)
