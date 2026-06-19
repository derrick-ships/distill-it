# Local Backup & Restore (build spec) — distilled from asyar

## Summary

Full-snapshot local backup of all user data to a single file, with optional AES-256-GCM password encryption (Argon2 key derivation). Export: collect SQLite data → serialize JSON → optionally encrypt → write to user-chosen path. Import: read file → optionally decrypt → validate schema version → merge into SQLite → refresh UI. No cloud involved.

## Core logic (inlined)

### Export
```rust
// Rust Tauri command
#[tauri::command]
async fn export_backup(
    password: Option<String>,
    path: String,
    db: State<DbConnection>,
) -> Result<(), Error> {
    // 1. Collect all user data from SQLite
    let payload = BackupPayload {
        schema_version: CURRENT_SCHEMA_VERSION,
        exported_at: chrono::Utc::now().timestamp(),
        snippets: db.query_all::<Snippet>("SELECT * FROM snippets")?,
        agents: db.query_all::<Agent>("SELECT * FROM agents")?,
        aliases: db.query_all::<Alias>("SELECT * FROM aliases")?,
        scripts: db.query_all::<Script>("SELECT * FROM scripts")?,
        mcp_servers: db.query_all::<McpServerConfig>("SELECT * FROM mcp_servers")?,
        extension_prefs: db.query_all::<ExtensionPref>("SELECT * FROM extension_preferences")?,
        // Clipboard content NOT included — privacy
    };

    // 2. Serialize to JSON
    let json = serde_json::to_vec(&payload)?;

    // 3. Encrypt if password provided
    let file_bytes = if let Some(pwd) = password {
        encrypt_backup(&json, &pwd)?
    } else {
        json
    };

    // 4. Write to user path
    std::fs::write(&path, file_bytes)?;
    Ok(())
}
```

### Encryption (AES-256-GCM + Argon2)
```rust
use argon2::{Argon2, Params};
use aes_gcm::{Aes256Gcm, Key, Nonce, aead::{Aead, NewAead}};

const MAGIC: &[u8] = b"ASYARENC\x01"; // 9-byte header for detection

fn encrypt_backup(plaintext: &[u8], password: &str) -> Result<Vec<u8>, Error> {
    // Random salt for Argon2
    let salt: [u8; 16] = rand::random();
    // Derive 32-byte key from password
    let mut key = [0u8; 32];
    Argon2::default().hash_password_into(
        password.as_bytes(), &salt,
        &mut key,
    )?;

    // Random 12-byte nonce for AES-GCM
    let nonce_bytes: [u8; 12] = rand::random();
    let cipher = Aes256Gcm::new(Key::from_slice(&key));
    let ciphertext = cipher.encrypt(Nonce::from_slice(&nonce_bytes), plaintext)?;

    // Format: MAGIC(9) + salt(16) + nonce(12) + ciphertext
    let mut out = Vec::with_capacity(9 + 16 + 12 + ciphertext.len());
    out.extend_from_slice(MAGIC);
    out.extend_from_slice(&salt);
    out.extend_from_slice(&nonce_bytes);
    out.extend_from_slice(&ciphertext);
    Ok(out)
}

fn decrypt_backup(data: &[u8], password: &str) -> Result<Vec<u8>, Error> {
    if !data.starts_with(MAGIC) {
        return Err(Error::NotEncrypted);
    }
    let salt = &data[9..25];
    let nonce_bytes = &data[25..37];
    let ciphertext = &data[37..];

    let mut key = [0u8; 32];
    Argon2::default().hash_password_into(password.as_bytes(), salt, &mut key)?;

    let cipher = Aes256Gcm::new(Key::from_slice(&key));
    let plaintext = cipher.decrypt(Nonce::from_slice(nonce_bytes), ciphertext)
        .map_err(|_| Error::WrongPassword)?;
    Ok(plaintext)
}
```

### Import
```rust
#[tauri::command]
async fn import_backup(
    password: Option<String>,
    path: String,
    merge_mode: MergeMode, // Replace | Merge
    db: State<DbConnection>,
    app: AppHandle,
) -> Result<(), Error> {
    let raw = std::fs::read(&path)?;

    // Detect and decrypt
    let json = if raw.starts_with(MAGIC) {
        let pwd = password.ok_or(Error::PasswordRequired)?;
        decrypt_backup(&raw, &pwd)?
    } else {
        raw
    };

    let payload: BackupPayload = serde_json::from_slice(&json)?;

    // Version check
    if payload.schema_version > CURRENT_SCHEMA_VERSION {
        return Err(Error::BackupTooNew(payload.schema_version));
    }
    // Apply migrations if payload is older
    let payload = migrate_backup(payload)?;

    // Write to DB
    let tx = db.transaction()?;
    match merge_mode {
        MergeMode::Replace => {
            tx.execute("DELETE FROM snippets", [])?;
            tx.execute("DELETE FROM agents", [])?;
            // ... truncate all tables
        }
        MergeMode::Merge => {} // INSERT OR REPLACE handles conflicts
    }
    for s in &payload.snippets { tx.insert_snippet(s)?; }
    for a in &payload.agents   { tx.insert_agent(a)?; }
    // ...
    tx.commit()?;

    // Notify frontend to reload
    app.emit_all("backup:restored", ()).ok();
    Ok(())
}
```

## Data contracts

**BackupPayload** (JSON):
```typescript
{
  schemaVersion: number;    // e.g. 3
  exportedAt: number;       // unix timestamp
  snippets: Snippet[];
  agents: AgentDef[];
  aliases: AliasEntry[];
  scripts: Script[];
  mcpServers: McpServerConfig[];
  extensionPrefs: ExtensionPref[];
}
```

**Encrypted file format** (binary):
```
[9 bytes magic] [16 bytes Argon2 salt] [12 bytes AES-GCM nonce] [N bytes ciphertext+tag]
```

## Dependencies & assumptions

- **argon2** crate for password-based key derivation
- **aes-gcm** crate for authenticated encryption
- **serde_json** for serialization
- **rand** crate for cryptographically random salt and nonce
- Tauri file dialog (or equivalent) for path selection
- Schema version migration system (same as DB migration system)

## To port this, you need:

- [ ] Collect all user-owned data tables into a single serializable struct
- [ ] AES-256-GCM + Argon2 implementation (or libsodium equivalent)
- [ ] Random salt + nonce per export (never reuse)
- [ ] Magic header bytes for encrypted vs plaintext detection
- [ ] Schema version field + migration chain for import compatibility
- [ ] Two merge modes: Replace (full overwrite) and Merge (upsert)
- [ ] Frontend refresh event after successful import

## Gotchas

- **Never reuse nonce**: AES-GCM is catastrophically broken if the same (key, nonce) pair is used twice. Always generate fresh random nonce per export.
- **Argon2 parameters**: Default Argon2 params (64MB memory, 3 iterations) add ~0.5s delay on export/import — acceptable for a security-sensitive operation. Don't lower these.
- **Wrong password = same error as corrupt file**: AES-GCM decryption failure (bad tag) can mean wrong password OR corrupted file. Surface a single clear error to the user; don't reveal which.
- **Extension code not backed up**: Only preferences and configs, not the extension's `dist/` assets. Importing on a new machine still requires re-installing extensions from the store.
- **Clipboard content exclusion**: The clipboard content database can be large and contains sensitive data. Always exclude it from the default export; offer it as an advanced option if needed.

## Origin (reference only)

Repo: https://github.com/Xoshbin/asyar  
Key files: `asyar-launcher/src-tauri/src/commands/sync.rs`, `asyar-launcher/src-tauri/src/crypto.rs`
