# Snippets / Text Expansion (build spec) — distilled from asyar

## Summary

Two-mode text expansion system: (1) in-launcher selection → paste, (2) background keyword detection → replace-in-place. Rust handles the global keyboard listener; TypeScript orchestrates clipboard hijack + backspace-erase + paste + clipboard restore. Snippets stored in SQLite with template variable support.

## Core logic (inlined)

### Snippet storage (SQLite + Svelte store)
```typescript
// snippetStore.svelte.ts
const snippets = $state<Snippet[]>([]);

async function loadAll() {
  snippets.value = await invoke<Snippet[]>('get_snippets');
}

export function getAll() { return snippets; }
export async function create(s: Snippet) {
  await invoke('create_snippet', s);
  await loadAll();
}
// Also: update(), delete()
```

```sql
CREATE TABLE snippets (
  id         TEXT PRIMARY KEY,
  keyword    TEXT NOT NULL UNIQUE,
  expansion  TEXT NOT NULL,
  name       TEXT NOT NULL,
  created_at INTEGER
);
```

### Template resolution
```typescript
// snippetService.ts
function resolveTemplate(expansion: string): { text: string; cursorOffset: number } {
  const now = new Date();
  let text = expansion
    .replace('{date}', now.toLocaleDateString())
    .replace('{time}', now.toLocaleTimeString())
    .replace('{datetime}', now.toLocaleString());

  const cursorOffset = text.indexOf('{cursor}');
  text = text.replace('{cursor}', '');
  return { text, cursorOffset };
}
```

### In-launcher paste (no background trigger needed)
```typescript
async function simulatePaste(expansion: string) {
  const original = await readText(); // save clipboard
  await writeText(expansion);        // set expansion
  await simulateKeyCombo('ctrl+v'); // or cmd+v on macOS
  setTimeout(() => writeText(original), 200); // restore
}
```

### Background trigger — Rust key listener → TypeScript expansion
```rust
// Rust: global key listener buffers last N chars
// On keyword match, emits event to TypeScript:
app.emit_all("snippet:trigger", SnippetTriggerPayload {
    keyword_length: keyword.len(),
    expansion: snippet.expansion.clone(),
}).unwrap();
```

```typescript
// TypeScript listener (app initializer)
listen<SnippetTriggerPayload>('snippet:trigger', async ({ payload }) => {
  const { keywordLength, expansion } = payload;
  const { text: resolved, cursorOffset } = resolveTemplate(expansion);
  await expandAndPaste(keywordLength, resolved, cursorOffset);
});

async function expandAndPaste(keywordLength: number, text: string, cursorOffset: number) {
  const original = await readText();           // 1. save clipboard
  await writeText(text);                        // 2. set expansion
  await simulateBackspaces(keywordLength);      // 3. erase the typed keyword
  await simulateKeyCombo('ctrl+v');             // 4. paste expansion
  // 5. if {cursor}, reposition caret (platform-specific)
  setTimeout(() => writeText(original), 200);  // 6. restore clipboard
}
```

### Rust: sync keywords to listener
```rust
// Called at init and after any snippet CRUD:
fn sync_snippet_keywords(keywords: Vec<(String, String)>) {
    // keywords = Vec<(keyword, expansion)>
    // Stores in atomic RwLock for the key-listener thread
    *SNIPPET_MAP.write().unwrap() = keywords.into_iter().collect();
}
```

## Data contracts

**Snippet** (TypeScript):
```typescript
{
  id: string;
  keyword: string;   // e.g. "addr"
  expansion: string; // e.g. "123 Main St, City, ST 12345"
  name: string;      // display label
  createdAt: number; // unix ms
}
```

**SnippetTriggerPayload** (Rust → TypeScript event):
```typescript
{
  keywordLength: number;   // how many backspaces to send
  expansion: string;       // raw (pre-template-resolve) expansion text
}
```

## Dependencies & assumptions

- **Tauri v2** with `tauri-plugin-clipboard-manager` for clipboard read/write
- **Tauri v2** with `tauri-plugin-global-shortcut` or equivalent for key simulation
- **rusqlite** for snippet persistence
- **Accessibility permission** (macOS) / equivalent for global key listening
- **`@tauri-apps/api/event` `listen()`** for Rust → TypeScript event delivery

## To port this, you need:

- [ ] A global keyboard listener that runs in the background (OS accessibility API or Tauri plugin)
- [ ] A rolling character buffer in Rust to detect keyword suffixes
- [ ] Clipboard save/write/restore sequence with 200ms delay
- [ ] Backspace simulation equal to keyword length (N × keydown Backspace)
- [ ] Template variable resolver (at minimum: `{date}`, `{time}`, `{cursor}`)
- [ ] SQLite table for snippet storage
- [ ] Accessibility permission check + graceful degradation (in-launcher only mode)

## Gotchas

- **200ms delay is fragile**: On slow machines or apps with clipboard hooks, 200ms may not be enough. Consider making this configurable (250-500ms for power users on slow setups).
- **Backspace-based replacement breaks on non-sequential input**: If the user typed `a`, then clicked, then typed `ddr` in a different position, keyword detection fires but the backspaces delete the wrong chars. No known clean fix — this is a fundamental limitation of keystroke-simulation text replacement.
- **Apps that disable paste simulation**: Some security-sensitive apps (password managers, banking) intercept or block synthetic paste events. The expansion silently fails.
- **`{cursor}` repositioning**: After paste, repositioning the cursor requires simulating arrow-key presses (counting characters from the end). This is fragile in rich-text editors. Consider `{cursor}` as a best-effort feature.
- **Thread safety**: The Rust keyword map must be behind a `RwLock` — the key listener reads it on every keystroke from a separate thread.

## Origin (reference only)

Repo: https://github.com/Xoshbin/asyar  
Key files: `asyar-launcher/src/built-in-features/snippets/snippetService.ts`, `snippetStore.svelte.ts`, `snippetUiState.svelte.ts`, `DefaultView.svelte`
