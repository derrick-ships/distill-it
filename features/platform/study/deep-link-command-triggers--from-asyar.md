# Deep Link Command Triggers — from [asyar](https://github.com/Xoshbin/asyar)

> Domain: [[_domain]] · Source: https://github.com/Xoshbin/asyar · NotebookLM:

## What it does

Asyar registers the `asyar://` custom URL scheme at the OS level. Any application — a browser, a note-taking app, a script, another desktop app — can fire a URL like `asyar://extensions/com.example.weather/check` and Asyar will activate and run the specified extension command with optional arguments.

## Why it exists

A launcher's value multiplies when other tools can reach into it. Deep links make Asyar scriptable from anywhere: a button in Notion, a hyperlink in a browser, a cron job, a Raycast-style menu bar — all can trigger a specific Asyar command without the user manually opening and typing in the launcher. It's the outward-facing automation API.

## How it actually works

**URL scheme registration**: Tauri registers `asyar://` as a custom URL handler at OS-level during app install (via `tauri.conf.json` deep link configuration). When any application opens an `asyar://` URL, the OS routes it to the running Asyar instance.

**URL format**:
```
asyar://extensions/{extensionId}/{commandId}?arg1=value1&arg2=value2
```

- The host must be `extensions` (the only supported path currently)
- `extensionId`: alphanumerics, dots, hyphens, underscores (e.g. `com.example.weather`)
- `commandId`: alphanumerics, hyphens, underscores (e.g. `check`)
- Query parameters are URL-decoded and passed as arguments to the command

**Parsing and validation** (`deeplink.rs`): The `parse_extension_deeplink()` function:
1. Validates the scheme is `asyar://`
2. Confirms the host is `extensions`
3. Extracts and validates `extensionId` and `commandId` from the path segments using character allowlists
4. URL-decodes query parameters into a key→value map
5. Returns `None` (with a logged warning) if any check fails — invalid deep links are silently ignored

**Dispatch**: A valid parsed payload — `ExtensionDeeplinkPayload { extensionId, commandId, args }` — is emitted as a Tauri event named `asyar:deeplink:extension` to the frontend. The TypeScript side listens for this event and routes it to the appropriate extension worker iframe or built-in command handler.

**Security**: The character allowlists on `extensionId` and `commandId` prevent path traversal and injection attacks. Arguments are URL-decoded but passed as strings — no shell execution, no eval. Extensions receive them as structured data and are responsible for their own input validation.

## The non-obvious parts

**Single-host design**: Currently only `extensions` is a valid host. The architecture would allow adding other hosts (e.g. `asyar://builtin/calculator?expr=2+2`) but the product hasn't needed it. Extensions cover 99% of external automation use cases.

**Already-running app routing**: If Asyar is already running, the OS delivers the URL to the existing instance rather than launching a new one. Tauri handles this via `tauri://` IPC — the existing window's event listener receives the URL string. This requires the app to have registered for single-instance mode.

**No deep link authentication**: Any app on the device can trigger any extension command. This is intentional — it's a local-only API and extensions run in sandboxed iframes anyway. There's no cross-origin concern.

**URL construction tip**: Because query parameters are URL-decoded, callers can pass rich arguments: `asyar://extensions/com.example.search/query?q=hello+world` would pass `{ q: "hello world" }` to the search command.

## Related

- [[sandboxed-extension-system--from-asyar]] (deep links trigger commands inside extension workers)
- [[command-palette-launcher--from-asyar]] (same command registry, different entry point)
- [[background-command-scheduling--from-asyar]] (both are external triggers into the same command system)
