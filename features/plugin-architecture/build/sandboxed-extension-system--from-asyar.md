# Sandboxed Extension System (build spec) — distilled from asyar

## Summary

Run third-party extensions inside sandboxed iframes. Extensions declare capabilities via `manifest.json`. Communication flows via typed `postMessage()` bridge with a UUID `requestId` for async resolution. Permissions are validated at two layers: TypeScript frontend (fast path) and Rust backend (authoritative). SDK handles project scaffolding, build, and packaging. Background scheduling via Tokio-driven timers. Live subtitles via periodic `getSubtitle()` callbacks.

## Core logic (inlined)

### manifest.json schema

```json
{
  "name": "My Extension",
  "id": "com.example.my-extension",
  "version": "1.0.0",
  "description": "Description shown in launcher",
  "icon": "icon.svg",
  "commands": [
    {
      "name": "search-items",
      "title": "Search Items",
      "subtitle": "Search through my data",
      "mode": "view",             // "view" | "no-view" | "menu-bar"
      "entry": "dist/index.html"
    }
  ],
  "permissions": [
    "clipboard:read",
    "clipboard:write",
    "network:fetch",
    "storage:read",
    "storage:write"
  ],
  "schedule": {
    "command": "sync-data",
    "interval": 3600             // seconds; range 60–86400
  }
}
```

### Iframe host setup (Svelte/TypeScript)

```typescript
// ExtensionHost.svelte - renders the sandboxed iframe
// and routes messages between extension and Tauri backend

const ALLOWED_PERMISSIONS_FOR_EXTENSION = loadManifestPermissions(extensionId)

function renderExtensionIframe(
  extensionPath: string,
  extensionId: string
): HTMLIFrameElement {
  const iframe = document.createElement('iframe')
  
  // Sandbox: allow scripts + same-origin (for localStorage), nothing else
  iframe.sandbox.add('allow-scripts')
  iframe.sandbox.add('allow-same-origin')
  // Note: do NOT add allow-top-navigation or allow-popups
  
  iframe.src = `asset://localhost/${extensionPath}/dist/index.html`
  iframe.style.cssText = 'width:100%;height:100%;border:none;background:transparent'
  
  return iframe
}

// Message bridge: extension → launcher
window.addEventListener('message', async (event) => {
  // Verify origin is our local asset server, not an external URL
  if (!isAllowedOrigin(event.origin)) return
  
  const { action, payload, requestId } = event.data as ExtensionMessage
  
  // Layer 1: frontend permission check (fast path)
  if (!ALLOWED_PERMISSIONS_FOR_EXTENSION.includes(getPermissionForAction(action))) {
    event.source?.postMessage({
      requestId,
      error: `Permission denied: ${getPermissionForAction(action)}`,
    }, event.origin)
    return
  }
  
  // Forward to Rust backend via Tauri invoke
  try {
    const result = await invoke('extension_action', {
      extensionId,
      action,
      payload,
    })
    event.source?.postMessage({ requestId, result }, event.origin)
  } catch (err) {
    event.source?.postMessage({ requestId, error: String(err) }, event.origin)
  }
})
```

### Rust backend permission enforcement

```rust
#[tauri::command]
async fn extension_action(
    state: tauri::State<'_, AppState>,
    extension_id: String,
    action: String,
    payload: serde_json::Value,
) -> Result<serde_json::Value, String> {
    // Layer 2: authoritative permission check in Rust
    let manifest = state.extension_registry
        .get_manifest(&extension_id)
        .ok_or("Extension not found")?;
    
    let required_permission = permission_for_action(&action);
    
    if !manifest.permissions.contains(&required_permission) {
        return Err(format!(
            "Permission denied: {} requires {:?}",
            action, required_permission
        ));
    }
    
    // Route to the appropriate handler
    match action.as_str() {
        "clipboard.read" => handle_clipboard_read(&state, &payload).await,
        "clipboard.write" => handle_clipboard_write(&state, &payload).await,
        "storage.get" => handle_storage_get(&state, &extension_id, &payload).await,
        "storage.set" => handle_storage_set(&state, &extension_id, &payload).await,
        "network.fetch" => handle_network_fetch(&state, &payload).await,
        "shell.execute" => handle_shell_execute(&state, &payload).await,
        _ => Err(format!("Unknown action: {}", action)),
    }
}

fn permission_for_action(action: &str) -> Permission {
    match action {
        a if a.starts_with("clipboard.read") => Permission::ClipboardRead,
        a if a.starts_with("clipboard.write") => Permission::ClipboardWrite,
        a if a.starts_with("network.") => Permission::Network,
        a if a.starts_with("storage.") => Permission::Storage,
        a if a.starts_with("shell.") => Permission::ShellExecute,
        _ => Permission::Unknown,
    }
}
```

### SDK client-side bridge (TypeScript, extension-side)

```typescript
// @asyar/sdk - extension-side client

interface AysarMessage {
  action: string
  payload: unknown
  requestId: string
}

interface AysarResponse {
  requestId: string
  result?: unknown
  error?: string
}

class AysarSDK {
  private pendingRequests = new Map<string, {
    resolve: (value: unknown) => void
    reject: (reason: string) => void
  }>()
  
  constructor() {
    window.addEventListener('message', (event) => {
      const { requestId, result, error } = event.data as AysarResponse
      const pending = this.pendingRequests.get(requestId)
      if (!pending) return
      this.pendingRequests.delete(requestId)
      if (error) pending.reject(error)
      else pending.resolve(result)
    })
  }
  
  private async call<T>(action: string, payload?: unknown): Promise<T> {
    const requestId = crypto.randomUUID()
    return new Promise<T>((resolve, reject) => {
      this.pendingRequests.set(requestId, {
        resolve: resolve as (value: unknown) => void,
        reject,
      })
      window.parent.postMessage({ action, payload, requestId }, '*')
      // Timeout after 30s to avoid leaked promises
      setTimeout(() => {
        if (this.pendingRequests.has(requestId)) {
          this.pendingRequests.delete(requestId)
          reject('Timeout')
        }
      }, 30_000)
    })
  }
  
  clipboard = {
    read: () => this.call<string[]>('clipboard.read'),
    write: (text: string) => this.call<void>('clipboard.write', { text }),
  }
  
  storage = {
    get: (key: string) => this.call<unknown>('storage.get', { key }),
    set: (key: string, value: unknown) => this.call<void>('storage.set', { key, value }),
  }
  
  search = {
    query: (q: string) => this.call<SearchResult[]>('search.query', { q }),
  }
}

// Injected as window.asyar in extension context
export const asyar = new AysarSDK()
```

### Background scheduling (Rust / Tokio)

```rust
use tokio::time::{interval, Duration};

pub async fn start_extension_scheduler(
    extension_id: String,
    command: String,
    interval_secs: u64,
    app_handle: tauri::AppHandle,
) {
    let mut ticker = interval(Duration::from_secs(interval_secs));
    
    loop {
        ticker.tick().await;
        
        // Run the extension's scheduled command
        if let Err(e) = run_extension_command(
            &app_handle,
            &extension_id,
            &command,
        ).await {
            eprintln!("Scheduled extension command failed: {}", e);
            // Don't break — keep scheduling even on failure
        }
    }
}
```

### Live subtitle callback

```typescript
// Extension registers a subtitle function
export const command: AysarCommand = {
  name: 'clipboard-history',
  title: 'Clipboard History',
  
  // Called periodically by launcher to update subtitle
  async getSubtitle(): Promise<string> {
    const items = await asyar.clipboard.read()
    return `${items.length} items`
  },
  
  // Called when user activates the command
  async run(context: CommandContext): Promise<void> {
    // Render the extension view
  }
}
```

## Data contracts

### ExtensionMessage (postMessage schema)
```typescript
interface ExtensionMessage {
  action: string          // e.g. "clipboard.read", "storage.set"
  payload: unknown        // action-specific data
  requestId: string       // UUID v4, for response correlation
}

interface ExtensionResponse {
  requestId: string
  result?: unknown        // on success
  error?: string          // on failure
}
```

### Permission enum
```rust
#[derive(Debug, PartialEq, serde::Deserialize)]
pub enum Permission {
    ClipboardRead,
    ClipboardWrite,
    FileSystemRead,
    FileSystemWrite,
    Network,
    ShellExecute,
    Notifications,
    WindowManagement,
    Storage,
    BackgroundSchedule,
    LauncherSearch,
    Unknown,
}
```

### Extension registry entry
```rust
pub struct ExtensionManifest {
    pub id: String,
    pub name: String,
    pub version: String,
    pub permissions: Vec<Permission>,
    pub commands: Vec<CommandManifest>,
    pub schedule: Option<ScheduleConfig>,
    pub install_path: PathBuf,
}
```

## Dependencies & assumptions

- **Tauri v2** — provides the `invoke()` bridge and WebView rendering
- **Rust async runtime** (Tokio) — background scheduler
- **TypeScript** — SDK and extension development
- Extensions are pre-built HTML/JS bundles (not source — the SDK CLI compiles them)
- Extensions loaded via `asset://localhost/` protocol (Tauri's file serving)
- Extension storage isolated per extension-id (no cross-extension data access)

## To port this, you need:

- [ ] An iframe container with `sandbox="allow-scripts allow-same-origin"` attribute
- [ ] A `postMessage` bridge with `requestId` for async correlation and 30s timeout
- [ ] Manifest schema with `permissions[]` and `commands[]` arrays
- [ ] Extension registry that stores the installed manifest (NOT derived from runtime messages)
- [ ] A `permission_for_action(action) → Permission` mapping enforced on BOTH sides
- [ ] Rust (or server-side) authoritative permission check before any system call
- [ ] Extension storage namespaced by extension ID (e.g., `sqlite: storage WHERE extension_id = ?`)
- [ ] Background scheduler using Tokio interval timers
- [ ] `getSubtitle()` polling mechanism in launcher search results

## Gotchas

**Never trust `event.origin` alone.** Check that the message source is one of your registered extension iframes, not just that the origin looks right. Cache the iframe reference at load time and compare `event.source`.

**Extension IDs must be globally unique.** Use reverse-domain notation (`com.author.name`) and validate on install. Two extensions with the same ID would share storage and permissions.

**The `allow-same-origin` sandbox flag has a subtle interaction.** If the iframe src is `null` origin (e.g., a data URI), `allow-same-origin` makes it same-origin as the top frame, giving it full access. Always serve extension HTML from a specific origin (`asset://localhost/...`), never inline.

**Background tasks must be idempotent.** The scheduler doesn't check if a previous run completed before starting the next. If the extension's network call takes longer than its interval, runs will pile up. Add a mutex/lock inside the scheduled handler.

**SDK postMessage timeout needs cleanup.** If the launcher is reloaded (during development), pending Promises in the extension iframe will leak because the response never comes. The 30s timeout is a safety valve, not a solution — add a `beforeunload` handler to reject all pending promises.

## Origin (reference only)

- Repo: https://github.com/Xoshbin/asyar
- Key paths: `asyar-sdk/` (TypeScript SDK), `asyar-launcher/src-tauri/src/` (Rust backend), `asyar-launcher/src-svelte/src/` (Svelte frontend)
- Stack: Tauri v2, Rust, TypeScript, Svelte 5, SQLite
