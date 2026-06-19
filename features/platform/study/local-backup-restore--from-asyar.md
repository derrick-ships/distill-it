# Local Backup & Restore — from [asyar](https://github.com/Xoshbin/asyar)

> Domain: [[_domain]] · Source: https://github.com/Xoshbin/asyar · NotebookLM:

## What it does

Asyar lets users export all their data — snippets, agents, aliases, extension settings, scripts, clipboard history metadata — to a single local file. That file can be imported on a new machine or after a reinstall to restore everything. Optionally, the backup file is encrypted with a user-supplied password so it can be stored or shared without exposing sensitive configuration.

## Why it exists

Asyar is local-first by design: no cloud account, no automatic sync. The backup feature is the manual escape hatch — the user owns their data migration story. It's also a safety net: if something goes wrong with an upgrade or a system migration, the user can roll back to a known-good state.

## How it actually works

**Export flow**: The user triggers "Export" from the Settings view. The Rust backend:
1. Collects all persisted user data from SQLite (snippets, agents, aliases, shortcuts, scripts, MCP server configs, extension preferences)
2. Serializes it to JSON
3. If encryption is requested, derives an AES-256-GCM key from the password using Argon2 (password hashing resistant to brute force), then encrypts the JSON payload
4. Writes the result to a `.asyar-backup` file (or `.asyar-backup.enc` for encrypted) at a user-chosen path via a Tauri file dialog

**Import flow**: The user selects a backup file. The Rust backend:
1. Reads the file
2. Detects whether it's encrypted (by file extension or a magic header byte)
3. If encrypted, prompts for the password, derives the key via Argon2, and decrypts
4. Deserializes the JSON
5. Validates the schema version (for forward/backward compatibility)
6. Merges or replaces data in SQLite (existing items may be overwritten or merged based on user choice)
7. Emits a refresh event to the frontend so UI reloads

**Encryption**: Uses AES-256-GCM (authenticated encryption — tampering is detected). The Argon2 key derivation uses a random 16-byte salt stored alongside the ciphertext in the backup file, so the same password produces different ciphertexts across backups.

**Schema versioning**: The backup JSON carries a `schemaVersion` field. If the importing Asyar version is older than the backup, it warns the user. If it's newer, it applies a migration path (same migration system used for SQLite upgrades).

## The non-obvious parts

**Local-only by design**: The backup file never touches Asyar's servers. There is a separate optional E2EE cloud sync feature (different architecture entirely), but backup/restore is strictly local file I/O.

**Argon2 over bcrypt/PBKDF2**: Argon2 was chosen because it's memory-hard, making large-scale brute-force attacks much more expensive. For a backup file that might sit on a USB drive, this matters.

**No incremental backup**: Each export is a full snapshot. There's no diff-based incremental backup — the file is always the complete state at export time.

**Extension content excluded**: Extensions themselves (their code, assets, and `dist/` folder) are NOT included in the backup — only their per-user preferences and configuration. Re-installing extensions from the Store is separate.

**Clipboard history**: The clipboard content items are excluded by default (the user may have copied passwords, sensitive data). Only the metadata (timestamps, source app) is included if at all. The actual content stays local-only.

## Related

- [[command-palette-launcher--from-asyar]] (settings entry point for backup UI)
- [[sandboxed-extension-system--from-asyar]] (extension preferences are part of the backup)
- [[mcp-sidecar-auto-detection--from-asyar]] (MCP server configs included in backup)
