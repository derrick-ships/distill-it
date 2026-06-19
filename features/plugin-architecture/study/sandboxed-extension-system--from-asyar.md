# Sandboxed Extension System — from [asyar](https://github.com/Xoshbin/asyar)

> Domain: [[_domain]] · Source: https://github.com/Xoshbin/asyar · NotebookLM:

## What it does

Asyar's extension system lets third-party developers add new commands to the launcher — custom search sources, productivity tools, integrations — without any risk of crashing the main app or accessing data they haven't been granted permission to. Each extension runs inside a sandboxed iframe, communicates with the launcher via a typed message bridge, and must declare all required permissions in a manifest. A TypeScript SDK (published to npm) provides the extension development framework supporting Svelte, React, Vue, or vanilla JavaScript.

## Why it exists

The alternative to sandboxing is loading extension code directly into the main process — what early Electron apps did, and what caused notorious instability. A single bad extension could throw an uncaught exception, corrupt shared state, or read the host app's memory. iframes give genuine isolation: the extension runs in a separate browser context with its own JavaScript heap. It can't reach the launcher's DOM, can't access the launcher's clipboard history, and can't crash the main process even if it throws synchronously.

The permission system addresses the complementary concern: isolation stops accidents, permissions stop intentional overreach. An extension that can only read clipboard history can't exfiltrate files, even if it wanted to.

## How it actually works

**Extension packaging**: An extension is a directory with a `manifest.json` at its root and a built web app (HTML/JS/CSS). The SDK's CLI (`asyar-sdk`) scaffolds the project, handles the build step, and packages it for distribution. Extensions can be written in Svelte, React, Vue, or plain JavaScript/TypeScript — whatever the developer prefers.

**Manifest declaration**: The manifest.json declares the extension's identity (name, version, description, icon), its commands (what items appear in the launcher), and its required permissions. Permissions are coarse-grained buckets: clipboard, file system, network, shell execution, notifications, window management, background scheduling, extension storage, and launcher search.

**Iframe loading**: When the user activates an extension command, the launcher renders an `<iframe>` with the `sandbox` attribute, loading the extension's built index.html. The `sandbox` attribute strips the iframe's ability to navigate the top frame, open popups, or access the parent's DOM. Only `allow-scripts` and `allow-same-origin` are enabled.

**Message bridge**: Extension code uses the SDK's `asyar` global to call capabilities. These calls are serialized into `postMessage()` messages with a typed schema (`{ action, payload, requestId }`). The launcher's iframe host receives these, validates that the requesting extension has the declared permission for that action, then forwards the request to the Rust backend via Tauri's `invoke()` IPC. The response travels the reverse path.

**Dual-layer permission enforcement**: The TypeScript frontend validates permissions (fast path, blocks obviously unauthorized calls). The Rust backend validates them again (trust boundary, the authoritative check). Extensions can't bypass the frontend check by crafting a raw postMessage because the Rust backend independently re-checks the extension's declared manifest permissions before executing any system call.

**Live subtitles (reactive results)**: Extensions can register a `getSubtitle()` callback that the launcher calls periodically (or on demand) to update a search result's subtitle line in real time. This powers dynamic displays like "Clipboard: 47 items" or "Weather: 22°C" that update without requiring the user to activate the extension.

**Background scheduling**: Manifests can declare a `schedule` block with a recurring interval (60–86,400 seconds). The Tauri backend's Tokio async runtime wakes the extension's background handler at the declared interval, even when the launcher window is closed.

## The non-obvious parts

**iframe sandbox prevents extension crashes from propagating.** If an extension throws an unhandled exception or enters an infinite loop, the iframe context crashes, but the host launcher process keeps running. The user sees the extension fail, not the entire launcher.

**Same-origin restriction on iframes.** The `allow-same-origin` flag is needed for extensions to read their own localStorage. Without it, the extension can't use any persistent storage. This is fine because extensions are loaded from `file://` or a local server, not from the internet.

**The `requestId` in messages is how async calls work.** The extension posts `{ action: 'clipboard.read', requestId: 'uuid-123' }`. The launcher responds with `{ requestId: 'uuid-123', result: [...] }`. The SDK wraps this in a Promise so extensions use `await asyar.clipboard.read()`.

**Permission validation uses the extension's registered manifest, not what it claims at runtime.** The backend stores the permissions from the manifest at install time. When an IPC call arrives, it looks up the extension ID → stored permissions → validates. The extension cannot pass extra permissions in the message body to escalate.

**Community extensions go through a review queue.** The official asyar.org extension store has a review step to catch malicious manifests before they reach users. Self-hosted installs bypass this.

## Related

- [[plugin-system--from-markitdown]] — entry-point-based Python plugin system (different language, same discovery concept)
- [[plugin-ecosystem--from-open-design]] — 3-tier plugin discovery (official/community/custom) similar to Asyar's extension store
- [[skills-system--from-open-design]] — SKILL.md-based agent skill system; similar to Asyar's manifest-declared commands
- [[pattern-based-secret-redaction--from-asyar]] — the privacy layer that extensions don't bypass (they don't get raw clipboard data)
- [[ai-agent-tool-calling--from-asyar]] — extensions can register tools that AI agents can call
