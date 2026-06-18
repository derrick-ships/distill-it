# Claude CLI Subprocess Agent (build spec) — distilled from open-carrusel

## Summary

Drive an AI feature by spawning the **Claude Code CLI as a one-shot subprocess** per user message, instead of calling a hosted LLM API. The subprocess runs headless with `--output-format stream-json`, its stdout JSON events are relayed to the browser as SSE, conversation continuity comes from `--resume <sessionId>`, and the agent acts on the world via the **Bash/WebFetch** tools (e.g. `curl`-ing results back into your own REST API) rather than a custom tool-calling protocol. Cost is bounded per turn with `--max-budget-usd`.

## Core logic (inlined)

### 1. Locate the `claude` binary (cross-platform, do this once and cache)

```ts
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { spawnSync } from "node:child_process";

export function findClaudePath(): string | null {
  // 1. explicit override
  const env = process.env.CLAUDE_CLI_PATH;
  if (env && fs.existsSync(env)) return env;

  // 2. well-known install locations
  const home = os.homedir();
  const candidates: string[] = [];
  if (process.platform === "win32") {
    const appData = process.env.APPDATA ?? "";
    const localAppData = process.env.LOCALAPPDATA ?? "";
    candidates.push(
      path.join(appData, "npm", "claude.cmd"),
      path.join(appData, "npm", "claude.exe"),
      path.join(localAppData, "Programs", "claude", "claude.exe"),
    );
  } else {
    candidates.push(
      path.join(home, ".local/bin/claude"),
      "/usr/local/bin/claude",
      "/opt/homebrew/bin/claude",
    );
  }
  for (const c of candidates) if (c && fs.existsSync(c)) return c;

  // 3. probe PATH
  const cmd = process.platform === "win32" ? "where" : "command";
  const args = process.platform === "win32" ? ["claude"] : ["-v", "claude"];
  const r = spawnSync(cmd, args, { encoding: "utf8", shell: process.platform !== "win32" });
  if (r.status === 0) {
    const p = r.stdout.split(/\r?\n/)[0]?.trim();
    if (p && fs.existsSync(p)) return p;
  }
  return null;
}

export function getClaudePath(): string {
  const p = findClaudePath();
  if (!p) throw new Error("Claude CLI not found. Install Claude Code and/or set CLAUDE_CLI_PATH.");
  return p;
}
```

### 2. Spawn it headless and relay stream-json → SSE

```ts
import { spawn } from "node:child_process";
// On Windows, prefer `cross-spawn` to handle .cmd shims:
//   import crossSpawn from "cross-spawn";

export async function POST(req: Request) {
  const { message, sessionId, ...ctx } = await req.json();
  const claudePath = getClaudePath();
  const systemPrompt = buildSystemPrompt(ctx.brand, ctx.carousel, ctx.stylePreset);

  const args = [
    "-p", message,
    "--output-format", "stream-json",
    "--append-system-prompt", systemPrompt,
    "--allowedTools", "Bash", "WebFetch", "Read",
    "--max-budget-usd", "1.00",
  ];
  if (sessionId) args.push("--resume", sessionId);

  const abort = new AbortController();
  const spawner = process.platform === "win32" ? crossSpawn : spawn;
  const child = spawner(claudePath, args, {
    cwd: process.cwd(),
    signal: abort.signal,
    stdio: ["pipe", "pipe", "pipe"],
  });
  child.stdin?.end(); // no interactive input

  // kill a hung run
  const timeout = setTimeout(() => abort.abort(), 480_000); // 480s

  let stderr = "";
  child.stderr?.on("data", (b: Buffer) => {
    if (stderr.length < 8192) stderr += b.toString();   // cap stderr at ~8KB
  });

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      let buf = "";
      child.stdout?.on("data", (chunk: Buffer) => {
        buf += chunk.toString();
        let nl: number;
        while ((nl = buf.indexOf("\n")) !== -1) {
          const line = buf.slice(0, nl).trim();
          buf = buf.slice(nl + 1);
          if (!line) continue;
          let event: any;
          try { event = JSON.parse(line); } catch { continue; } // tolerate partial/garbage lines
          handleEvent(event, controller, encoder);
        }
      });
      child.on("close", (code) => {
        clearTimeout(timeout);
        if (code !== 0) {
          controller.enqueue(encoder.encode(
            `data: ${JSON.stringify({ type: "error", error: stderr || `exited ${code}` })}\n\n`));
        }
        controller.close();
      });
    },
    cancel() { abort.abort(); }, // browser disconnected
  });

  return new Response(stream, {
    headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache", Connection: "keep-alive" },
  });
}

function handleEvent(event: any, controller: ReadableStreamDefaultController, enc: TextEncoder) {
  const send = (o: unknown) => controller.enqueue(enc.encode(`data: ${JSON.stringify(o)}\n\n`));
  switch (event.type) {
    case "system": // init event — carries session_id; persist it for the next turn's --resume
      if (event.session_id) send({ type: "session", sessionId: event.session_id });
      break;
    case "assistant": // text deltas
      for (const block of event.message?.content ?? [])
        if (block.type === "text") send({ type: "token", text: block.text });
      break;
    case "result": // final
      send({ type: "done", sessionId: event.session_id, result: event.result });
      break;
  }
}
```

> Note: exact event field names (`type`, `session_id`, `message.content[]`) follow Claude Code's `stream-json` schema; verify against the installed CLI version — the shape has evolved. The relay pattern (parse NDJSON line → re-emit as SSE) is the stable part.

### 3. The system prompt is where "tools" actually live

Rather than a function-call schema, the system prompt *documents the app's own REST API* and tells the agent to use Bash + `curl` to act:

```
You are designing Instagram carousel slides. Brand: {name}, colors {…}, fonts {…}.
Current carousel id: {id}. Existing slides: {summaries}.
To add/replace a slide, write body-level HTML and POST it:
  curl -X PUT http://localhost:3000/api/carousels/{id}/slides/{n} \
       -H 'Content-Type: application/json' -d '{"html": "<...>"}'
Rules: body-level HTML only (no <html>/<head>), use only the brand fonts, …
```

The agent reads this, generates HTML, and `curl`s it back. No tool protocol to maintain.

## Data contracts

**Request → `/api/chat`:**
```ts
{ message: string; sessionId?: string; brand: BrandConfig; carousel: Carousel; stylePreset?: StylePreset }
```

**SSE events → browser** (your own normalized shape):
```ts
{ type: "session"; sessionId: string }
{ type: "token";   text: string }
{ type: "done";    sessionId: string; result: string }
{ type: "error";   error: string }
```

**CLI flags (the real contract with Claude Code):** `-p`, `--output-format stream-json`, `--append-system-prompt`, `--allowedTools <names…>`, `--max-budget-usd <n>`, `--resume <sessionId>`.

## Dependencies & assumptions

- **Claude Code CLI installed and authenticated** on the host running the server. This is a *local-first / self-hosted* assumption — there is no per-request API key; it uses the user's existing Claude auth. **Will not work on stateless serverless** (no persistent binary, no auth, no Bash).
- Node `child_process` (`spawn`/`spawnSync`); optional `cross-spawn` for Windows `.cmd` shims.
- The host shell must be able to reach your own API (the agent `curl`s `localhost`).
- Swappable: replace the subprocess with the Anthropic Messages API + real tool definitions if you need cloud/serverless — but then you lose the "free, uses existing auth" property and must build a tool loop.

## To port this, you need:
- [ ] A non-serverless runtime that can spawn long-lived child processes and stream responses (Next.js route handler on a Node server, Express, etc.).
- [ ] Claude Code installed on that host; a `CLAUDE_CLI_PATH` env override for non-standard installs.
- [ ] A binary-discovery helper (section 1) — do not hardcode the path.
- [ ] An SSE (or WebSocket) channel to the client for streaming tokens.
- [ ] Session persistence: store the `session_id` from the init event keyed to the conversation; pass it as `--resume` next turn.
- [ ] A system-prompt builder that documents whatever "tools" (REST endpoints/files) you want the agent to drive via Bash.
- [ ] A per-turn timeout, an `AbortController` wired to client disconnect, and a bounded stderr buffer.

## Gotchas

- **Serverless is a non-starter** — needs a persistent process host and the CLI on disk.
- **`--allowedTools` is your security boundary.** Granting `Bash` means the agent can run arbitrary shell on the host. Acceptable for a single-user local app; **dangerous if exposed to untrusted users** — it's effectively RCE-as-a-feature. Lock the network, never expose this server publicly without sandboxing.
- **`--max-budget-usd` matters** precisely because Bash lets the agent loop; without it a stuck agent burns money/quota.
- **Partial JSON lines:** stdout chunks split mid-line — buffer and split on `\n`, and `try/catch` each `JSON.parse` (skip non-JSON lines the CLI may print).
- **Session id timing:** it arrives in the *init/system* event, not the result — capture it early or `--resume` breaks next turn.
- **Cap stderr** (8 KB here) or a verbose failure can balloon memory.
- **Binary discovery is the #1 portability failure** — install layouts differ across macOS/Linux/Windows; always provide the env override.
- **CLI flag/event-schema drift:** `stream-json` event shapes and flag names track the Claude Code version; pin/verify on upgrade.

## Origin (reference only)

- `src/app/api/chat/route.ts` — spawn + stream-json → SSE relay, timeout, abort, stderr cap.
- `src/lib/claude-path.ts` — cross-platform binary discovery (`getClaudePath`).
- `src/lib/chat-system-prompt.ts` — `buildSystemPrompt(brand, carousel, stylePreset)`.
- Repo: https://github.com/Hainrixz/open-carrusel
