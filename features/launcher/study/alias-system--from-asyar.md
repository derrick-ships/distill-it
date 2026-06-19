# Alias System — from [asyar](https://github.com/Xoshbin/asyar)

> Domain: [[_domain]] · Source: https://github.com/Xoshbin/asyar · NotebookLM:

## What it does

Asyar's alias system lets you assign short custom names to any app or command. Type the alias in the launcher and it resolves instantly to the real target. For example: alias `"gm"` → Gmail web app, `"ss"` → a specific screenshot script. One registration, permanent shortcut — no memorizing exact names or scrolling through lists.

## Why it exists

Even with fuzzy search, typing partial names is still effort. Power users have a fixed repertoire of frequently used commands. Aliases eliminate that friction entirely: `gm` ↵ is faster than typing "Gmail" or clicking a dock icon. It's the manual complement to the automatic frequency ranking.

## How it actually works

**Client-server split**: The TypeScript frontend is a thin typed wrapper. It calls five Tauri IPC commands: `register_alias`, `remove_alias`, `list_aliases`, `get_alias_target`, and `check_alias_conflict`. All state storage, validation, and conflict detection live in the Rust backend.

**Registration**: When a user opens an app or command's detail view and clicks "Add Alias," the UI shows a text input captured by `AliasCapture.svelte`. On submit, the frontend calls `aliasService.register(alias, objectId)`, which invokes Rust via `invoke('register_alias', { alias, objectId })`. The Rust side validates the alias (no whitespace, no reserved keywords), checks for conflicts, and writes to SQLite.

**Conflict detection**: Before registering, the system checks if the alias string is already taken by another object. The check optionally excludes the current object's existing alias (for rename flows). The conflict result is shown inline in the capture UI before the user saves.

**Validation rules** (`aliasValidation.ts`): Aliases must be non-empty, single-word (no spaces), and not already registered to a different item. The same rules run client-side for instant feedback and server-side for correctness.

**Search integration**: At launcher startup, the Rust backend materializes all registered aliases as synthetic `AliasEntry` items in the search pool. When the user types an alias that matches exactly, the alias entry appears at the top of results (priority-boosted), and selecting it executes the underlying target as if selected directly.

**Persistence**: Aliases are stored in the main SQLite database in an `aliases` table with columns `(alias_text, target_object_id, created_at)`. They survive app restarts. The in-memory search index is rebuilt from this table at launch.

## The non-obvious parts

**Rust owns correctness**: The client-side validation is a UX nicety, not a trust boundary. The Rust layer re-validates before writing to prevent IPC-level bypass or concurrent edit races.

**Object ID stability**: Aliases bind to an internal object ID (e.g., `app:com.google.Chrome`), not a display name. This means renaming an app's label doesn't break its aliases.

**Alias vs. keyword**: Built-in features have built-in keywords in their manifests (e.g., `"clip"` finds clipboard history). Aliases are user-defined overrides that live in a separate namespace and always win on exact match.

**No wildcard aliases**: Aliases are exact-match only. There is no glob or prefix pattern support. This keeps the resolution logic simple and avoids ambiguity.

## Related

- [[command-palette-launcher--from-asyar]] (aliases appear as top-priority results here)
- [[sandboxed-extension-system--from-asyar]] (extension commands can be aliased just like built-ins)
