# Claude CLI Subprocess Agent — from [open-carrusel](https://github.com/Hainrixz/open-carrusel)

> Domain: [[_domain]] · Source: https://github.com/Hainrixz/open-carrusel · NotebookLM: <link once added>

## What it does

Open Carrusel lets you *chat* your way to an Instagram carousel. You type "make me a 5-slide carousel about our new pricing," and slides appear in a live editor. The thing doing the work isn't an API call to a hosted model — it's the **Claude Code CLI running as a subprocess on your own machine**, spawned fresh for each message. The web app is essentially a thin shell around `claude -p "..."`, streaming the agent's tokens back to the browser as they arrive.

## Why it exists

The product's whole pitch is "local-first, no cloud, no vendor lock-in, no API key to manage." If you already have Claude Code installed and authenticated, the app piggybacks on *that* — your existing subscription/auth — instead of asking you for an Anthropic API key and billing you separately. It turns the desktop agent you already pay for into the brain of a web app. That's the trick: the moat isn't the model, it's "you already have the agent, so this is free to run."

It also sidesteps building a tool-calling protocol. Instead of defining custom tools and wiring a function-call loop, the app gives Claude the **Bash** and **WebFetch** tools and lets it `curl` slide HTML back into the app's own REST API. The agent is a normal Claude Code session that happens to have the carousel app's endpoints in its system prompt.

## How it actually works

1. **A message comes in** to `/api/chat`. The server gathers context — the brand config, the current carousel's slides, the chosen style preset — and assembles a **system prompt** describing the product, the slide format, and the API endpoints Claude should `curl`.

2. **It finds the `claude` binary.** A dedicated path-finder checks `CLAUDE_CLI_PATH`, then a list of well-known install locations per OS (`~/.local/bin/claude`, `/usr/local/bin/claude`, `/opt/homebrew/bin/claude`, Windows `npm/claude.cmd`, etc.), then falls back to `command -v claude` / `where claude`. If nothing's found it throws a friendly "install Claude Code" error.

3. **It spawns the subprocess** with flags that turn Claude Code into a headless, streaming, budget-capped worker:
   - `-p "<message>"` — the prompt (one-shot, non-interactive)
   - `--output-format stream-json` — emit newline-delimited JSON events instead of prose
   - `--append-system-prompt "<built prompt>"` — inject the carousel context
   - `--allowedTools Bash WebFetch Read` — the only tools it may use
   - `--max-budget-usd 1.00` — hard cost ceiling per turn
   - `--resume <sessionId>` — continue the same conversation across messages
   - stdin is closed immediately; the app never feeds it interactively.

4. **It streams.** The subprocess's stdout emits one JSON object per line. The server parses each line and re-emits it to the browser as **Server-Sent Events** (`text/event-stream`). Three event kinds matter: the *init* event (carries the session id, which the app stores so the next message can `--resume`), *assistant* messages (text deltas that show up in the chat), and the final *result* event.

5. **Claude builds the slides itself.** Using its Bash tool, it writes slide HTML and `curl`s it into the app's `/api/carousels/.../slides` endpoints. The browser, already subscribed, sees the new slides render. The agent is both the chat *and* the hands.

6. **Safety rails:** a 480-second timeout kills a hung subprocess; stderr is captured but capped at ~8 KB so a chatty failure can't blow up memory; an `AbortController` lets the user cancel a generation mid-flight.

## The non-obvious parts

- **The agent is stateless per request, conversational via `--resume`.** Each chat message is a brand-new process. Continuity comes entirely from passing the saved `sessionId` back in. There's no long-lived agent process to manage or crash.
- **No custom tool protocol.** Most "AI app" builders define JSON tool schemas and run a function-call loop. Open Carrusel refuses to: it just hands Claude `Bash` + `WebFetch` and documents the REST API in the system prompt. The agent writes files and `curl`s — the "tools" are the shell and the app's own HTTP surface. Far less code, but it leans on Claude being good at following an API contract in prose.
- **`stream-json` is the integration seam.** Because Claude Code can emit structured streaming events, the app gets token streaming, session ids, and result metadata without parsing prose. The whole web layer is a JSON-event relay.
- **Budget cap as a product feature.** `--max-budget-usd 1.00` means a runaway generation can't quietly rack up cost — important when the agent has Bash and can loop.
- **Cross-platform binary discovery is half the battle.** A surprising amount of the robustness lives in *finding `claude`* across macOS/Linux/Windows install layouts before you can spawn anything.

## Related

- [[staged-actions-queue--from-open-carrusel]] (the confirmation queue that reviews what the agent proposes before it lands)
- [[html-to-png-export--from-open-carrusel]] (what turns the agent's HTML into shippable PNGs)
- [[conversation-memory--from-whatsapp-agentkit]] (different take on agent continuity — a DB table vs. CLI `--resume`)
- [[ordered-backend-routing--from-agent-reach]] (another "the agent is config, not code" pattern)
