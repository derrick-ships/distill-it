# Deep Link Command Triggers (build spec) — distilled from asyar

## Summary

Register a custom `asyar://` URL scheme to allow any app or script to trigger extension commands. Tauri registers the scheme at install time; `deeplink.rs` parses and validates the URL with character allowlists; a Tauri event delivers the payload to the TypeScript frontend which routes to the target extension worker.

## Core logic (inlined)

### Tauri config (scheme registration)
```json
// tauri.conf.json
{
  "tauri": {
    "bundle": {
      "macOS": {
        "urlSchemes": ["asyar"]
      }
    },
    "allowlist": {
      "protocol": {
        "asset": true,
        "assetScope": ["**"]
      }
    }
  }
}
```

### URL format
```
asyar://extensions/{extensionId}/{commandId}[?key=value&key2=value2]
```

### Rust: parse and validate
```rust
// deeplink.rs
#[derive(Debug)]
pub struct ExtensionDeeplinkPayload {
    pub extension_id: String,
    pub command_id: String,
    pub args: HashMap<String, String>,
}

pub fn parse_extension_deeplink(url: &str) -> Option<ExtensionDeeplinkPayload> {
    let parsed = Url::parse(url).ok()?;

    // Validate scheme
    if parsed.scheme() != "asyar" { return None; }
    // Validate host
    if parsed.host_str() != Some("extensions") { return None; }

    let segments: Vec<&str> = parsed.path_segments()?.collect();
    if segments.len() < 2 { return None; }

    let extension_id = segments[0];
    let command_id = segments[1];

    // Character allowlists (prevent injection)
    let valid_ext_id = extension_id.chars()
        .all(|c| c.is_alphanumeric() || c == '.' || c == '-' || c == '_');
    let valid_cmd_id = command_id.chars()
        .all(|c| c.is_alphanumeric() || c == '-' || c == '_');

    if !valid_ext_id || !valid_cmd_id {
        warn!("Deep link rejected: unsafe characters in id segments");
        return None;
    }
    if extension_id.is_empty() || command_id.is_empty() {
        return None;
    }

    // Decode query args
    let args: HashMap<String, String> = parsed.query_pairs()
        .map(|(k, v)| (k.into_owned(), v.into_owned()))
        .collect();

    Some(ExtensionDeeplinkPayload {
        extension_id: extension_id.to_string(),
        command_id: command_id.to_string(),
        args,
    })
}
```

### Rust: handle incoming URL and emit event
```rust
// In app setup / deep link listener
fn handle_deeplink(app: &AppHandle, url: String) {
    if let Some(payload) = parse_extension_deeplink(&url) {
        app.emit_all("asyar:deeplink:extension", &payload)
           .unwrap_or_else(|e| warn!("Failed to emit deeplink event: {e}"));
    } else {
        warn!("Received unrecognized deep link: {url}");
    }
}
```

### TypeScript: listen and dispatch
```typescript
// In app initialization
import { listen } from '@tauri-apps/api/event';

listen<ExtensionDeeplinkPayload>('asyar:deeplink:extension', async ({ payload }) => {
  const { extensionId, commandId, args } = payload;
  // Route to extension worker iframe
  await extensionRuntime.invokeCommand(extensionId, commandId, args);
});
```

## Data contracts

**ExtensionDeeplinkPayload** (Rust → TypeScript via Tauri event):
```typescript
{
  extensionId: string;  // e.g. "com.example.weather"
  commandId: string;    // e.g. "check"
  args: Record<string, string>; // URL-decoded query params
}
```

## Dependencies & assumptions

- **Tauri v2** with deep link support (configured in `tauri.conf.json` per platform)
- `tauri-plugin-single-instance` or equivalent so the running app receives the URL rather than a second instance launching
- The extension runtime must expose `invokeCommand(extensionId, commandId, args)` that the listener can call

## To port this, you need:

- [ ] Register your custom URL scheme in `tauri.conf.json` (macOS: `urlSchemes`, Windows: registry via installer, Linux: `.desktop` file `MimeType=x-scheme-handler/yourapp`)
- [ ] A `deep_link_received` Tauri callback or event that fires when the OS delivers a URL
- [ ] `parse_*_deeplink()` function with scheme/host validation + character allowlists on path segments
- [ ] Tauri `emit_all()` → TypeScript `listen()` to deliver the payload to the frontend
- [ ] Frontend routing layer that maps `(extensionId, commandId)` to the correct handler

## Gotchas

- **App not running**: On macOS, if the app is not running when a deep link fires, the OS launches it and delivers the URL. Tauri single-instance plugin handles this, but you must buffer the URL and replay it after the frontend is ready.
- **Windows registry cleanup**: On Windows, the URL scheme is registered in the registry by the installer. If the app is uninstalled without a proper uninstaller run, stale registry entries may direct URLs to a missing binary.
- **No auth on deep links**: Any process on the machine can fire them. Don't use deep links to trigger privileged operations (deleting data, sending network requests) without user confirmation.
- **Fragment encoding**: URL fragments (`#`) are not transmitted to the server and many OS URL handlers strip them. Don't put arguments in the fragment; use query parameters.
- **URL encoding**: Callers must URL-encode special chars in arg values (`&` → `%26`, `=` → `%3D`). Document this explicitly in your extension SDK.

## Origin (reference only)

Repo: https://github.com/Xoshbin/asyar  
Key file: `asyar-launcher/src-tauri/src/deeplink.rs`
