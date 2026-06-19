# Pattern-Based Secret Redaction — from [asyar](https://github.com/Xoshbin/asyar)

> Domain: [[_domain]] · Source: https://github.com/Xoshbin/asyar · NotebookLM:

## What it does

Every piece of text that flows through Asyar — clipboard items, typed input, AI conversation context, shell command output — passes through a multi-layer privacy pipeline before touching storage or leaving the device. The pipeline intercepts OS privacy signals at capture time, runs a pattern-matching redaction pass to strip well-known secret formats (API keys, JWTs, credit card numbers, environment variables, private keys), and then encrypts everything it does keep using AES-256-GCM with keys stored in the OS keychain.

## Why it exists

Command launchers are a natural aggregation point for secrets. You paste API keys into shell commands, copy JWTs from browser dev tools, type passwords into prompts. If that clipboard history is stored in plaintext, or if AI context includes raw secrets that get sent to an external LLM, the user's credentials are silently exfiltrated. Asyar solves this as a first-class architectural concern rather than an afterthought.

## How it actually works

**Capture-time exclusion** is the first layer. macOS, Windows, and Linux all provide mechanisms for marking clipboard content as private (password managers use these). Asyar reads these OS flags before even extracting the text content — if the flag is set, the clipboard item is never stored, not even temporarily.

**Pattern-based redaction** is the second layer. Before any text is written to SQLite or included in an AI prompt, it runs through a configurable regex pipeline. The pipeline includes built-in patterns for:

- **API keys**: detected by recognizable prefixes (`sk-`, `ghp_`, `xoxp-`, `AKIA`, etc.) plus length/character-class constraints
- **JWTs**: three base64url segments separated by dots (the `eyJ...` pattern is distinctive)
- **Credit card numbers**: Luhn-valid 13–19 digit strings with optional separators
- **Private keys**: PEM header/footer blocks (`-----BEGIN RSA PRIVATE KEY-----`)
- **Environment variables with secrets**: `SECRET=`, `API_KEY=`, `TOKEN=`, `PASSWORD=` patterns in shell-style assignment form

Matched content is replaced in-place with a placeholder like `[REDACTED]` rather than deleted, so the user can see that redaction occurred. Users can add custom patterns for company-specific secret formats.

**Encryption at rest** is the third layer. After redaction, clipboard history and conversation data are stored in a local SQLite database encrypted with AES-256-GCM. The encryption key is generated once per device and stored in the OS native keychain (Keychain Services on macOS, Windows Credential Manager, libsecret on Linux) rather than in a config file or environment variable. This means the data is safe even if someone copies the database file.

**AI context scrubbing** happens before any content is sent to an LLM provider. The same redaction pipeline runs over the assembled conversation context to catch anything that slipped through earlier (e.g., a previously stored but not-yet-redacted item that gets loaded from history).

## The non-obvious parts

**Capture-time is the only safe moment to exclude password manager content.** Once you've stored the text, you can try to redact it, but if a backup or sync already captured it, you've lost. Checking OS privacy flags at capture time is the correct architecture.

**Pattern matching has false positive vs. false negative tradeoffs.** A UUID looks like an API key; a 16-digit credit card could be a product serial number. The pipeline is deliberately conservative (some false positives) rather than permissive. Users can suppress false positives by adding exclusion patterns.

**AES-256-GCM gives authenticated encryption.** Not only is the data encrypted, but GCM mode adds an authentication tag that detects tampering. Corrupted or modified database files are detected at read time, not silently decrypted into garbage.

**OS keychain dependency.** If the OS keychain is locked (e.g., the user's login keychain is protected by a different password), Asyar can't read the encryption key and falls back to prompting the user rather than skipping decryption silently.

**Optional cloud sync inherits the same encryption.** If the user opts into cloud sync, the encrypted blobs travel as-is — the cloud provider sees only ciphertext. The sync key is different from the local key and is established via a key exchange during setup.

## Related

- [[ai-agent-tool-calling--from-asyar]] — AI context goes through this redaction pipeline before reaching any LLM
- [[sandboxed-extension-system--from-asyar]] — extensions run in isolated iframes and have no direct access to the clipboard history database
- [[credential-management/multi-tier-credentials--from-last30days-skill]] — related pattern for securing credentials used by tools
- [[realtime-collab/e2e-encrypted-collaboration--from-excalidraw]] — a similar AES-GCM + key-in-URL approach to E2E encryption
