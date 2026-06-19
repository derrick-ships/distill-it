# BYOK Settings (build spec) — distilled from dyad

## Summary

Build a "Bring Your Own Keys" settings system for a desktop AI app: persist settings to a local JSON file with atomic writes, encrypt all secrets using the OS keychain (Electron safeStorage), merge user settings with defaults on read, expose settings only through unlogged IPC handlers, and support custom AI provider endpoints alongside built-in ones.

## Core logic (inlined)

```typescript
// --- SCHEMA ---
interface UserSettings {
  // Model selection
  selectedProvider: string                    // e.g. "openai", "anthropic", "custom_my-provider"
  selectedModel: string                       // e.g. "gpt-4o", "claude-sonnet-4-6"
  
  // Provider API keys (one per provider, encrypted on disk)
  providerApiKeys: Record<string, string>     // { openai: "sk-...", anthropic: "sk-ant-..." }
  
  // Service tokens (encrypted on disk)
  githubToken: string
  vercelToken: string
  supabaseTokens: Record<string, { access: string; refresh: string }>  // per org ID
  neonToken: string
  vertexServiceAccountJson: string            // entire JSON blob for GCP auth
  
  // UI preferences
  theme: 'light' | 'dark' | 'system'
  defaultChatMode: 'build' | 'ask' | 'plan' | 'local-agent'
  defaultTemplate: string
  
  // Feature flags
  codeExplorerEnabled: boolean
  proMode: boolean
  autoUpdate: boolean
  telemetryEnabled: boolean
  telemetryUserId: string                     // random UUID, never PII
  blockUnsafeNpmPackages: boolean
}

const DEFAULT_SETTINGS: UserSettings = {
  selectedProvider: 'anthropic',
  selectedModel: 'claude-sonnet-4-6',
  providerApiKeys: {},
  githubToken: '',
  vercelToken: '',
  supabaseTokens: {},
  neonToken: '',
  vertexServiceAccountJson: '',
  theme: 'system',
  defaultChatMode: 'build',
  defaultTemplate: 'react-vite',
  codeExplorerEnabled: false,
  proMode: false,
  autoUpdate: true,
  telemetryEnabled: true,
  telemetryUserId: crypto.randomUUID(),
  blockUnsafeNpmPackages: false,
}

// --- ENCRYPTION ---
const ENCRYPTED_FIELDS: (keyof UserSettings)[] = [
  'providerApiKeys',
  'githubToken', 'vercelToken',
  'supabaseTokens', 'neonToken',
  'vertexServiceAccountJson',
]

interface EncryptedValue {
  encrypted: string    // base64-encoded encrypted bytes
  type: 'safeStorage' | 'plaintext'
}

function encrypt(value: string): EncryptedValue {
  if (safeStorage.isEncryptionAvailable() && !IS_TEST_BUILD) {
    return {
      encrypted: safeStorage.encryptString(value).toString('base64'),
      type: 'safeStorage',
    }
  }
  // Fallback: plaintext (test builds, headless Linux without keyring)
  return { encrypted: value, type: 'plaintext' }
}

function decrypt(stored: EncryptedValue): string {
  if (stored.type === 'safeStorage') {
    return safeStorage.decryptString(Buffer.from(stored.encrypted, 'base64'))
  }
  return stored.encrypted
}

// --- WRITE (atomic) ---
function writeSettings(settings: Partial<UserSettings>): void {
  const current = readExistingSettingsFile() ?? { ...DEFAULT_SETTINGS }
  const merged = { ...current, ...settings }
  
  // Encrypt sensitive fields before serialization
  const toWrite = { ...merged }
  for (const field of ENCRYPTED_FIELDS) {
    if (toWrite[field] !== undefined) {
      toWrite[field] = encryptField(toWrite[field]) as any
    }
  }
  
  const settingsPath = getSettingsPath()
  const tmpPath = settingsPath + '.tmp'
  
  // Atomic write: temp file → rename
  fs.writeFileSync(tmpPath, JSON.stringify(toWrite, null, 2), 'utf-8')
  fs.renameSync(tmpPath, settingsPath)
  
  // Keep backup
  fs.copyFileSync(settingsPath, settingsPath + '.backup')
}

// --- READ ---
function readExistingSettingsFile(): UserSettings | null {
  const settingsPath = getSettingsPath()
  if (!fs.existsSync(settingsPath)) return null
  
  try {
    const raw = JSON.parse(fs.readFileSync(settingsPath, 'utf-8'))
    
    // Decrypt sensitive fields
    for (const field of ENCRYPTED_FIELDS) {
      if (raw[field] !== undefined) {
        raw[field] = decryptField(raw[field])
      }
    }
    
    return raw
  } catch (err) {
    // Corrupt settings — notify user, return null to use defaults
    notifyCorruptSettings(settingsPath)
    return null
  }
}

function readEffectiveSettings(): UserSettings {
  const stored = readExistingSettingsFile()
  // Deep merge with defaults — missing fields get default values
  return deepMerge(DEFAULT_SETTINGS, stored ?? {})
}

// --- IPC HANDLERS (unlogged) ---
function registerSettingsHandlers() {
  // CRITICAL: No logging — these handlers process raw API keys
  createTypedHandler(settingsContracts.getUserSettings, async () => {
    return readEffectiveSettings()
  }, { skipLogging: true })

  createTypedHandler(settingsContracts.setUserSettings, async (_, settings) => {
    writeSettings(settings)
    return readEffectiveSettings()
  }, { skipLogging: true })
}

// --- CUSTOM PROVIDERS (DB, not settings file) ---
// Custom providers and models stored in SQLite (no encryption needed — no secrets here)
// DB tables: custom_providers (id, name, apiBaseUrl), custom_models (id, providerId, apiName, displayName)
async function createCustomProvider(id: string, name: string, apiBaseUrl: string) {
  // Validate
  if (!/^custom_[a-z0-9-]+$/.test(id)) throw new Error('Invalid provider ID')
  if (!apiBaseUrl.startsWith('https://')) throw new Error('API base URL must be HTTPS')
  
  await db.insert(customProviders).values({ id, name, apiBaseUrl })
}
```

## Data contracts

```typescript
// Settings file on disk (~/.config/dyad/user-settings.json or Electron userData path)
// All ENCRYPTED_FIELDS stored as: { encrypted: string, type: "safeStorage" | "plaintext" }
// All other fields stored as-is

// IPC: settings:get → UserSettings (decrypted, in-memory only)
// IPC: settings:set(Partial<UserSettings>) → UserSettings

// DB: custom_providers table
interface CustomProvider {
  id: string          // "custom_my-endpoint"
  name: string        // "My OpenAI Proxy"
  apiBaseUrl: string  // "https://api.myproxy.com/v1"
  createdAt: number
}

// DB: custom_models table
interface CustomModel {
  id: number
  providerId: string
  apiName: string     // actual model identifier sent to API
  displayName: string // shown in UI
  createdAt: number
}
```

## Dependencies & assumptions

- **Electron safeStorage**: OS keychain bridge. macOS: Keychain Access. Windows: DPAPI. Linux: libsecret/gnome-keyring.
- Node `fs` for atomic write (temp + rename)
- Drizzle ORM + better-sqlite3 for custom providers/models (no encryption needed)
- `IS_TEST_BUILD` env/build flag to disable encryption in CI

## To port this, you need:

- [ ] Settings schema with explicit `ENCRYPTED_FIELDS` list
- [ ] `encrypt()` / `decrypt()` wrappers around safeStorage (or equivalent)
- [ ] Atomic write: write to `.tmp` file, then `fs.renameSync` to final path
- [ ] `readEffectiveSettings()` that merges stored → defaults (handles missing fields on upgrade)
- [ ] IPC handlers with logging explicitly disabled for settings endpoints
- [ ] Backup file copy after each successful write
- [ ] Corruption handler: catch JSON parse errors, notify user, fall back to defaults
- [ ] Custom provider CRUD in SQLite (separate from settings file — no secrets)
- [ ] `deepMerge(defaults, stored)` that's null-safe for nested objects like `providerApiKeys`

## Gotchas

- **safeStorage is machine-specific:** Encrypted values can't be decrypted on a different machine. Never sync the settings file to cloud storage.
- **safeStorage unavailable on headless Linux:** If no keyring daemon is running (e.g., Docker, SSH-only servers), `safeStorage.isEncryptionAvailable()` returns false. Fall back to plaintext but warn the user.
- **Atomic rename is critical:** A plain `writeFileSync` that's interrupted mid-write corrupts the only settings file. Temp + rename makes the write atomic.
- **Never log settings handler input/output:** Raw API keys flow through these IPC calls. Any log line that includes args will expose them to log files. Wrap handlers in a no-log variant.
- **Custom providers use DB, not settings file:** API keys for custom providers go in the settings file (encrypted). The provider name/URL go in SQLite (not secret). Don't conflate them.
- **`providerApiKeys` is a Record<providerId, key>:** When a new built-in provider is added, the key can be null/undefined — `readEffectiveSettings()` must handle sparse objects.

## Origin (reference only)
- Repo: https://github.com/dyad-sh/dyad
- Key files: `src/main/settings.ts`, `src/ipc/handlers/settings_handlers.ts`, `src/ipc/handlers/language_model_handlers.ts`
