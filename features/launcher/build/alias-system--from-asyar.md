# Alias System (build spec) — distilled from asyar

## Summary

User-defined shorthand names (aliases) that resolve to any app or command in the launcher. Architecture: thin TypeScript IPC wrapper + Rust backend that owns storage, validation, and conflict detection. Aliases materialize as synthetic search entries at launch and win on exact match.

## Core logic (inlined)

### TypeScript service (thin IPC wrapper)
```typescript
// asyar-launcher/src/built-in-features/aliases/aliasService.ts
class AliasService {
  async register(alias: string, objectId: string): Promise<void> {
    await invoke('register_alias', { alias, objectId });
  }
  async remove(alias: string): Promise<void> {
    await invoke('remove_alias', { alias });
  }
  async list(): Promise<AliasEntry[]> {
    return await invoke('list_aliases');
  }
  async checkConflict(alias: string, excludeObjectId?: string): Promise<boolean> {
    return await invoke('check_alias_conflict', { alias, excludeObjectId });
  }
}
export const aliasService = new AliasService(); // module singleton
```

### Validation (runs on both sides)
```typescript
// aliasValidation.ts
export function validateAlias(alias: string): string | null {
  if (!alias || alias.trim().length === 0) return 'Alias cannot be empty';
  if (/\s/.test(alias)) return 'Alias must be a single word (no spaces)';
  if (alias.length > 50) return 'Alias too long';
  return null; // valid
}
```

### Rust storage (SQLite)
```rust
// In Rust commands layer
#[tauri::command]
fn register_alias(alias: String, object_id: String, db: State<DbConnection>) -> Result<(), Error> {
    // Re-validate (never trust client)
    validate_alias(&alias)?;
    check_no_conflict(&alias, None, &db)?;
    db.execute(
        "INSERT INTO aliases (alias_text, target_object_id, created_at) VALUES (?1, ?2, ?3)",
        params![alias, object_id, chrono::Utc::now().timestamp()],
    )?;
    Ok(())
}

#[tauri::command]
fn check_alias_conflict(alias: String, exclude_object_id: Option<String>, db: State<DbConnection>) -> bool {
    // Returns true if alias is taken by a DIFFERENT object
    let existing: Option<String> = db.query_row(
        "SELECT target_object_id FROM aliases WHERE alias_text = ?1",
        params![alias], |row| row.get(0)
    ).optional().unwrap_or(None);

    match (existing, exclude_object_id) {
        (Some(owner), Some(excluded)) => owner != excluded,
        (Some(_), None) => true,
        (None, _) => false,
    }
}
```

### Search pool injection
```typescript
// At launcher init, aliases are merged into the search pool:
const aliases = await aliasService.list();
const aliasCommands: SearchEntry[] = aliases.map(a => ({
  id: `alias:${a.aliasText}`,
  name: a.aliasText,
  resolvedTarget: a.targetObjectId,
  type: 'alias',
  score: 1000, // exact-match aliases always win
}));
```

## Data contracts

**AliasEntry** (Rust → TypeScript):
```typescript
{
  aliasText: string;       // the shorthand (e.g. "gm")
  targetObjectId: string;  // stable object id (e.g. "app:com.google.Chrome")
  createdAt: number;       // unix timestamp
}
```

**SQLite schema**:
```sql
CREATE TABLE aliases (
  alias_text       TEXT PRIMARY KEY,
  target_object_id TEXT NOT NULL,
  created_at       INTEGER NOT NULL
);
```

## Dependencies & assumptions

- **Tauri v2** IPC (`invoke`) for TS → Rust calls
- **rusqlite** for SQLite persistence
- The search pool must support injecting synthetic entries with boosted scores
- Object IDs must be stable across renames (bind to internal ID, not display name)

## To port this, you need:

- [ ] A stable object ID scheme for every aliasable command/app
- [ ] SQLite (or KV store) for alias persistence with conflict-safe writes
- [ ] Server-side validation mirroring the client validation (no trust boundary on IPC)
- [ ] Search pool injection: aliases as synthetic top-priority entries
- [ ] A UI component for alias capture with inline conflict feedback (`AliasCapture.svelte` pattern)

## Gotchas

- **Double-validate**: Client validation is for UX only. The Rust layer must re-run the same rules — IPC messages can be crafted or race conditions can bypass the client check.
- **Bind to ID not name**: Aliases that reference display names break when the user renames apps. Always store the internal stable ID.
- **Reserved keywords**: Block aliases that shadow built-in launcher keywords (e.g., "help", "settings") or warn the user — otherwise a built-in becomes unreachable by keyword.
- **Case sensitivity**: Decide once and be consistent. Asyar appears to be case-insensitive on lookup (lowercased on store). Mixed-case stores then fail exact-match lookups.

## Origin (reference only)

Repo: https://github.com/Xoshbin/asyar  
Key files: `asyar-launcher/src/built-in-features/aliases/aliasService.ts`, `aliasValidation.ts`, `aliasStore.svelte.ts`, `AliasCapture.svelte`
