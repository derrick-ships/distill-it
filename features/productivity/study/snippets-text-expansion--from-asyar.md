# Snippets / Text Expansion — from [asyar](https://github.com/Xoshbin/asyar)

> Domain: [[_domain]] · Source: https://github.com/Xoshbin/asyar · NotebookLM:

## What it does

Asyar's snippet system lets you define short keywords that automatically expand to longer text — addresses, boilerplate phrases, code fragments, template strings. Expansion happens in two modes:

1. **In-launcher**: Open the launcher, type the snippet keyword, select it → it pastes the expansion into whatever app had focus before.
2. **Background trigger**: While typing normally in any app, the moment you finish typing a registered keyword (followed by a space or punctuation), Asyar detects it in the background and replaces it in-place — without the launcher ever appearing.

## Why it exists

Text expansion is one of the oldest and highest-ROI productivity tools. Typing `addr` → a full address, `csig` → an email signature, `dt` → the current date. The background trigger mode (like TextExpander or Espanso) makes expansion invisible and seamless: you never leave your workflow.

## How it actually works

**Data layer**: Snippets are stored in SQLite as `(keyword, expansion, name)` records. The `snippetStore.svelte.ts` is a Svelte reactive store that loads them from the DB via Tauri `invoke`, caches them in reactive state, and exposes `getAll()` / CRUD operations to the UI.

**In-launcher mode**: The snippet built-in feature registers itself in the launcher index. When selected, its `DefaultView.svelte` shows a searchable list of snippets. Selecting one calls `simulatePaste(expansion)` — which writes the expansion to the clipboard and simulates Ctrl+V / ⌘+V. After 200ms, the original clipboard is restored.

**Background trigger mode (the clever bit)**: This requires OS-level keyboard monitoring (accessibility permission). The Rust backend runs a global key listener that buffers the last N characters typed. On each character, it checks the buffer tail against all registered keywords. On a match, it:
1. Calls `expandAndPaste(keyword.length, expansion)` in TypeScript
2. The TypeScript side writes the expansion to clipboard
3. Simulates `Backspace × keyword.length` to erase the typed keyword
4. Simulates Paste (`⌘+V` / `Ctrl+V`) to insert the expansion
5. Restores the original clipboard after 200ms

**Template placeholders**: The `resolveTemplate(expansion)` function processes variables like `{date}`, `{time}`, `{cursor}`. The resolved string is what gets pasted. `{cursor}` marks the insertion point — after pasting, the cursor is repositioned there.

**Privacy / secret redaction**: Before syncing snippet keywords to the Rust key-listener, the service passes expansions through `secretRedactionService` which detects and redacts patterns matching API keys, JWTs, credit cards, and similar secrets. The redacted kinds are tracked but expansions with secrets are handled carefully.

**Permission model**: The background trigger requires Accessibility permission (macOS) or equivalent on other platforms. The service checks this at init and at view open; if permission is missing, it shows a prompt and disables background mode (in-launcher mode still works).

## The non-obvious parts

**Clipboard save/restore**: The paste simulation must hijack the clipboard momentarily. The 200ms restore delay is the minimum to avoid a race where the target app reads the clipboard before the paste completes. Some apps with clipboard listeners may still see the intermediate state — this is a known limitation of the OS paste simulation approach.

**Backspace-based replacement**: The background trigger can't "select the keyword" with OS APIs because it doesn't know what application has focus. It simulates Backspace presses equal to keyword length to delete what was typed, then pastes. This fails if the user typed the keyword non-sequentially (e.g., pasted part of it).

**Keyword detection window**: The Rust key buffer doesn't store the full session's typing — just the last N characters needed for the longest keyword. This is efficient and privacy-preserving.

**No cross-app clipboard leaks**: The 200ms restore ensures snippets don't pollute the clipboard for the user's next paste in a different app.

## Related

- [[command-palette-launcher--from-asyar]] (in-launcher snippet selection uses the same window)
- [[pattern-based-secret-redaction--from-asyar]] (redaction runs on snippet expansions before broadcast)
