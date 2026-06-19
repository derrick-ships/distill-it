# BYOK Settings — from [dyad](https://github.com/dyad-sh/dyad)

> Domain: [[_domain]] · Source: https://github.com/dyad-sh/dyad · NotebookLM: 

## What it does

Dyad's "Bring Your Own Keys" settings system lets users configure API keys for any of 7+ AI providers (OpenAI, Anthropic, Google, Amazon Bedrock, Azure, xAI, custom OpenAI-compatible endpoints), plus tokens for Vercel, GitHub, Supabase, and Neon. All secrets are encrypted on-disk using the OS keychain. The settings UI also controls model selection, theme, chat mode defaults, telemetry, and feature flags.

## Why it exists

The entire product premise is local + private. That means no Dyad-managed API keys, no cloud proxy for AI calls — the user's keys go straight from their machine to the AI provider. BYOK is how Dyad avoids becoming a vendor that marks up API costs, and how it can support any provider (new providers can be added as custom endpoints without a Dyad update).

## How it actually works

**Settings file:** All settings live in `user-settings.json` in the Electron app data directory. Writes use an atomic rename pattern (write to temp file, rename) to prevent corruption on crash.

**Encryption:** Before any secret is written to `user-settings.json`, it's encrypted via Electron's `safeStorage.encryptString()` — which uses the OS keychain on macOS (Keychain Access), Windows (DPAPI), and libsecret on Linux. The encrypted bytes are base64-encoded and stored alongside a metadata field indicating the encryption type. On read, `decryptStoredSecret()` reverses this. If `safeStorage` isn't available (test builds, some CI environments), secrets are stored as plaintext.

**Protected credentials include:**
- Per-provider API keys (one per provider entry)
- GitHub personal access token
- Vercel access token
- Supabase access + refresh tokens (per-organization)
- Neon database token
- Vertex AI service account JSON (entire JSON blob)

**IPC contract:** The renderer can only read/write settings through two IPC calls: `getUserSettings` and `setUserSettings`. These are deliberately unlogged — even the Electron IPC log layer is bypassed — to ensure raw key values never appear in log files.

**Custom providers:** Beyond the 7 built-in providers, users can create custom provider entries with a name, ID, and API base URL (any OpenAI-compatible endpoint). Custom models can be added under custom providers. All stored in SQLite, distinct from the settings file secrets.

**Effective settings merge:** `readEffectiveSettings()` merges the user's settings file with computed defaults. If a field is missing (older config format), the default value fills in. This makes settings forward-compatible — new feature flags appear with sensible defaults when users upgrade.

**Feature flags in settings:** Code Explorer enabled/disabled, pro mode, auto-update, local agent quota tracking — these are all settings fields, not environment variables. This means users can toggle experimental features without editing config files.

## The non-obvious parts

- **No cloud sync:** Settings are entirely local. If a user sets up Dyad on two machines, they must copy the settings file manually (and re-encrypt, since `safeStorage` is machine-specific). This is a deliberate privacy trade-off.
- **safeStorage is platform-dependent:** On Linux, `safeStorage` uses libsecret/gnome-keyring. If neither is running (e.g., headless server), encryption falls back to plaintext. Dyad warns about this.
- **Backup on corruption:** If the settings file is unreadable (corruption, encoding issues), Dyad notifies the user and links to recovery docs. A timestamped backup is kept alongside the main file.
- **API keys never leave the main process:** The renderer receives a settings object where all encrypted fields are present but with the *decrypted* value — but only in the main process RAM. The IPC serialization sends the decrypted value to the renderer only for display in the settings form. This is a known trade-off: Electron's IPC is same-machine, but the renderer could in theory be compromised.

## Related
- [[cloud-deploy--from-dyad]] (Vercel token stored here)
- [[mcp-integration--from-dyad]] (MCP OAuth credentials stored alongside)
- [[ai-chat-stream--from-dyad]] (provider/model selection consumed here)
