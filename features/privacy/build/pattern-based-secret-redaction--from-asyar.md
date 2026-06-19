# Pattern-Based Secret Redaction (build spec) — distilled from asyar

## Summary

A three-layer privacy pipeline: (1) capture-time OS clipboard privacy flag exclusion, (2) regex-based redaction of well-known secret patterns (API keys, JWTs, credit cards, private keys, env-var secrets) applied before storage and AI context assembly, (3) AES-256-GCM encryption at rest with OS keychain-managed keys. Replacements are in-place `[REDACTED]` markers so redaction is visible. User-extensible with custom patterns.

## Core logic (inlined)

### Layer 1: Capture-time exclusion (Rust / Tauri)

```rust
// Before reading clipboard text content, check OS privacy flags
// On macOS: NSPasteboardItem conformsToType: NSPasteboardTypeConcealedType
// On Windows: check MSAA password field flags or clipboard sequence check
// On Linux: check XDG clipboard privacy extensions

fn should_exclude_clipboard_item(item: &ClipboardItem) -> bool {
    // 1. OS-flagged as private (password managers set this)
    if item.is_os_private {
        return true;
    }
    // 2. Sourced from known password manager bundle IDs
    let password_manager_bundle_ids = [
        "com.1password.1password",
        "com.agilebits.onepassword7",
        "com.bitwarden.desktop",
        "net.sourceforge.keepassx",
        "com.lastpass.LastPass",
    ];
    if let Some(source) = &item.source_bundle_id {
        if password_manager_bundle_ids.contains(&source.as_str()) {
            return true;
        }
    }
    false
}
```

### Layer 2: Pattern-based redaction

```rust
use regex::Regex;
use lazy_static::lazy_static;

lazy_static! {
    static ref REDACTION_PATTERNS: Vec<(&'static str, Regex)> = vec![
        // API keys by known prefixes
        ("api-key", Regex::new(
            r"(?i)(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36}|xoxp-[0-9]+-[a-zA-Z0-9]+|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z\-_]{35}|ya29\.[a-zA-Z0-9\-_]+)"
        ).unwrap()),
        
        // JWT tokens (3 base64url segments)
        ("jwt", Regex::new(
            r"eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"
        ).unwrap()),
        
        // Credit card numbers (13-19 digits, optional separators)
        ("credit-card", Regex::new(
            r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12})(?:[-\s]?[0-9]{4})?\b"
        ).unwrap()),
        
        // PEM private keys
        ("private-key", Regex::new(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
        ).unwrap()),
        
        // Environment variable secret assignments
        ("env-secret", Regex::new(
            r"(?i)(?:secret|api_?key|auth_?token|password|passwd|private_?key|access_?token)\s*[=:]\s*['\"]?([^\s'\"]{8,})['\"]?"
        ).unwrap()),
        
        // Generic high-entropy strings (40+ hex chars = likely a hash/key)
        ("hex-secret", Regex::new(
            r"\b[0-9a-f]{40,}\b"
        ).unwrap()),
    ];
}

pub fn redact_secrets(input: &str) -> String {
    let mut output = input.to_string();
    for (name, pattern) in REDACTION_PATTERNS.iter() {
        output = pattern.replace_all(&output, format!("[REDACTED:{}]", name).as_str())
            .to_string();
    }
    output
}

// Apply before storage
pub fn process_clipboard_for_storage(text: &str, custom_patterns: &[CustomPattern]) -> String {
    let mut result = redact_secrets(text);
    // Apply user-defined patterns
    for pattern in custom_patterns {
        if let Ok(re) = Regex::new(&pattern.regex) {
            result = re.replace_all(&result, "[REDACTED:custom]").to_string();
        }
    }
    result
}

// Apply before AI context assembly
pub fn redact_for_ai_context(messages: &[Message]) -> Vec<Message> {
    messages.iter().map(|msg| Message {
        role: msg.role.clone(),
        content: redact_secrets(&msg.content),
    }).collect()
}
```

### Layer 3: AES-256-GCM encryption at rest

```rust
use aes_gcm::{Aes256Gcm, Key, Nonce};
use aes_gcm::aead::{Aead, KeyInit};
use keyring::Entry;
use rand::RngCore;

const KEYRING_SERVICE: &str = "asyar";
const KEYRING_USER: &str = "db-encryption-key";

pub struct StorageEncryption {
    cipher: Aes256Gcm,
}

impl StorageEncryption {
    pub fn new() -> Result<Self, StorageError> {
        // Try to load key from OS keychain
        let entry = Entry::new(KEYRING_SERVICE, KEYRING_USER)?;
        
        let key_bytes = match entry.get_password() {
            Ok(stored_key) => {
                // Decode from hex string stored in keychain
                hex::decode(stored_key)?
            }
            Err(_) => {
                // First run: generate new key and store it
                let mut key_bytes = vec![0u8; 32]; // 256-bit key
                rand::thread_rng().fill_bytes(&mut key_bytes);
                entry.set_password(&hex::encode(&key_bytes))?;
                key_bytes
            }
        };
        
        let key = Key::<Aes256Gcm>::from_slice(&key_bytes);
        let cipher = Aes256Gcm::new(key);
        
        Ok(Self { cipher })
    }
    
    pub fn encrypt(&self, plaintext: &[u8]) -> Result<Vec<u8>, StorageError> {
        // Generate a fresh 96-bit nonce for each encryption operation
        let mut nonce_bytes = [0u8; 12];
        rand::thread_rng().fill_bytes(&mut nonce_bytes);
        let nonce = Nonce::from_slice(&nonce_bytes);
        
        let ciphertext = self.cipher.encrypt(nonce, plaintext)
            .map_err(|_| StorageError::EncryptionFailed)?;
        
        // Prepend nonce to ciphertext: [12 bytes nonce][ciphertext+tag]
        let mut result = nonce_bytes.to_vec();
        result.extend(ciphertext);
        Ok(result)
    }
    
    pub fn decrypt(&self, data: &[u8]) -> Result<Vec<u8>, StorageError> {
        if data.len() < 12 {
            return Err(StorageError::InvalidData);
        }
        let (nonce_bytes, ciphertext) = data.split_at(12);
        let nonce = Nonce::from_slice(nonce_bytes);
        
        self.cipher.decrypt(nonce, ciphertext)
            .map_err(|_| StorageError::DecryptionFailed)
    }
}
```

### SQLite integration (SQLCipher or manual blob encryption)

```rust
// Option A: Encrypt at column level (blobs in SQLite)
// Store clipboard items as encrypted blobs
pub fn store_clipboard_item(
    db: &Connection,
    item: &ClipboardItem,
    encryption: &StorageEncryption,
) -> Result<(), StorageError> {
    let text = process_clipboard_for_storage(&item.text, &item.custom_patterns);
    let text_bytes = text.as_bytes();
    let encrypted = encryption.encrypt(text_bytes)?;
    
    db.execute(
        "INSERT INTO clipboard_history (id, content_encrypted, timestamp, source) VALUES (?1, ?2, ?3, ?4)",
        rusqlite::params![item.id, encrypted, item.timestamp, item.source],
    )?;
    Ok(())
}

// Option B: Use SQLCipher (full database encryption)
// Connection string: "file:asyar.db?key=<hex_key>"
// Key retrieved from OS keychain at startup
```

### Custom pattern configuration

```typescript
// In TypeScript settings layer
interface CustomRedactionPattern {
  name: string;
  regex: string;          // Rust-compatible regex syntax
  description?: string;   // Shown to user in settings UI
  enabled: boolean;
}

// Stored in settings.json (not in the encrypted DB)
interface PrivacySettings {
  enableRedaction: boolean;
  builtinPatterns: {
    apiKeys: boolean;
    jwts: boolean;
    creditCards: boolean;
    privateKeys: boolean;
    envSecrets: boolean;
    hexSecrets: boolean;
  };
  customPatterns: CustomRedactionPattern[];
  cloudSync: {
    enabled: boolean;
    provider: 'none' | 'icloud' | 'custom';
  };
}
```

## Data contracts

### ClipboardItem shape
```rust
pub struct ClipboardItem {
    pub id: String,               // UUID v4
    pub text: String,             // Raw text (not yet redacted)
    pub is_os_private: bool,      // OS clipboard privacy flag
    pub source_bundle_id: Option<String>,  // macOS: NSRunningApplication bundleIdentifier
    pub timestamp: i64,           // Unix timestamp ms
    pub custom_patterns: Vec<CustomPattern>,
}
```

### Encrypted storage blob format
```
[0..12]   : nonce (96-bit random, per-write)
[12..N-16]: ciphertext
[N-16..N] : GCM authentication tag (16 bytes, appended by aes-gcm)
```

## Dependencies & assumptions

- **Rust**: `aes-gcm` crate (AEAD encryption), `regex` crate, `keyring` crate (OS keychain), `rand` crate
- **`lazy_static!`** for compiled-once regex patterns
- OS keychain available: macOS Keychain, Windows Credential Manager, libsecret/GNOME Keyring on Linux
- **SQLite** for local storage (rusqlite)
- Tauri v2 for OS integration

## To port this, you need:

- [ ] OS clipboard privacy flag detection at capture time (platform-specific)
- [ ] A set of compiled regex patterns for common secret formats (see patterns above)
- [ ] A `redact_secrets(text: &str) -> String` function called at two points: before storage, before AI context assembly
- [ ] AES-256-GCM encryption wrapper with OS keychain key management
- [ ] SQLite schema with encrypted blob columns (or SQLCipher full-DB encryption)
- [ ] Settings UI to manage custom patterns and toggle built-in patterns
- [ ] User-visible `[REDACTED:type]` markers in UI instead of silent deletion

## Gotchas

**Compiled-once regex patterns are essential.** Do not compile regexes on every call — `Regex::new()` in a hot path crashes performance. Use `lazy_static!` or `OnceLock<Regex>`.

**GCM nonce must be unique per encryption.** Reusing a nonce with the same key breaks GCM confidentiality completely. Always generate a fresh random nonce per write operation.

**Hex-secret pattern has high false positive rate.** SHA hashes, UUIDs (without dashes), and content hashes are 40+ hex chars. Tune the threshold or make this pattern opt-in.

**Keychain access prompts.** On macOS, the first time you access a keychain item, the OS may show a permission dialog. This must be handled gracefully (show user a prompt, not crash).

**Credit card regex is not sufficient for compliance.** A Luhn-valid number is not proof of a live PAN. If you're building a compliance product, use a dedicated library. The regex is a best-effort heuristic.

**JWT replacement breaks some workflows.** If the user is using the launcher to manage auth tokens for testing, redacting them defeats the purpose. Consider a per-item "don't redact" override flag.

## Origin (reference only)

- Repo: https://github.com/Xoshbin/asyar
- Key paths: `asyar-launcher/src-tauri/src/` (Rust backend), settings architecture in `asyar-launcher/src-svelte/src/`
- Stack: Tauri v2, Rust, SQLite, OS keychains
