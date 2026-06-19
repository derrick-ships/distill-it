# Command-Palette Launcher (build spec) — distilled from asyar

## Summary

A floating, always-running command-palette window built on Tauri v2 + Svelte 5. On global hotkey, the window reveals (hide/show, never destroy). The user types to fuzzy-search a merged pool of: indexed OS applications, registered built-in feature commands (each with a manifest), extension commands, and user aliases. Enter launches the selection; Escape hides.

## Core logic (inlined)

### Window lifecycle
```rust
// Tauri Rust side
// Window is created at app startup, never destroyed
fn show_launcher(window: tauri::Window) {
    window.show().unwrap();
    window.set_focus().unwrap();
    // Flash-free reveal: position is already correct from last hide
}

fn hide_launcher(window: tauri::Window) {
    window.hide().unwrap();
    // Do NOT destroy — keeps WebView warm
}
```

### Global hotkey
- Registered via `tauri-plugin-global-shortcut` at app init
- Default: ⌘+Space (macOS), Ctrl+Space (Win/Linux), user-configurable
- On fire: calls `show_launcher()` + focuses the search input

### Built-in feature registration (manifest.json per feature)
```json
{
  "id": "clipboard-history",
  "name": "Clipboard History",
  "description": "Browse and reuse copied content",
  "keywords": ["clipboard", "paste", "history"],
  "icon": "clipboard.svg",
  "defaultCommand": "open"
}
```
- Each `built-in-features/<name>/manifest.json` is scanned at startup
- Merged into a `BuiltInCommand[]` list alongside indexed apps

### Application indexing (Rust, platform-specific)
```rust
// macOS: scan /Applications + ~/Applications
// Windows: enumerate HKLM/HKCU registry + Start menu .lnk files
// Linux: parse ~/.local/share/applications/*.desktop + /usr/share/applications/

pub async fn list_applications() -> Vec<AppEntry> {
    // Returns: { name, icon_path, exec_command, keywords[] }
}
```

### Fuzzy search (TypeScript/Svelte frontend)
```typescript
// On every keystroke:
const results = allCommands.filter(cmd =>
  fuzzyMatch(query, cmd.name) || cmd.keywords.some(k => k.includes(query))
).sort((a, b) => score(b, query) - score(a, query));

// score() = fuzzy match quality * 0.7 + launchCount * 0.3
// launchCount persisted to SQLite, incremented on each launch
```

### Navigation stack
```svelte
<!-- Single Tauri window, view stack in Svelte state -->
let viewStack = $state(['search']); // root is always search

function pushView(feature: string) { viewStack.push(feature); }
function popView() {
  viewStack.pop();
  if (viewStack.length === 0) hide_launcher();
}
```

## Data contracts

**AppEntry** (from Rust → TypeScript):
```typescript
{
  id: string;          // "app:com.apple.safari"
  name: string;        // "Safari"
  icon: string;        // base64 PNG or file:// URI
  execCommand: string; // platform open command
  keywords: string[];
  launchCount: number; // from local SQLite
}
```

**BuiltInCommand** (from manifest.json):
```typescript
{
  id: string;          // "clipboard-history"
  name: string;
  description: string;
  keywords: string[];
  icon: string;        // path relative to feature dir
  defaultCommand: string;
  viewComponent: string; // Svelte component name to mount
}
```

## Dependencies & assumptions

- **Tauri v2** with `tauri-plugin-global-shortcut` for hotkey registration
- **Svelte 5** with `$state()` runes for reactivity
- **SQLite** (rusqlite) for launch frequency tracking
- **Platform-specific icon extraction**: macOS `NSImage`/`NSWorkspace`, Windows `ExtractIconEx`, Linux `.desktop` Icon= field
- The window must be created at app init (not lazily) — lazy creation causes visible flash

## To port this, you need:

- [ ] A desktop framework with show/hide window control (Tauri, Electron, etc.)
- [ ] Global hotkey registration (platform API or library)
- [ ] Platform-specific application enumeration for each target OS
- [ ] A manifest schema and file scan for registering built-in commands
- [ ] Fuzzy search implementation (fzf-style scoring)
- [ ] SQLite or equivalent for launch frequency persistence
- [ ] A single-window view stack navigation pattern

## Gotchas

- **Destroy vs hide**: destroying and recreating the window on each invocation causes 200-500ms cold-start visible to users. Always hide.
- **Window positioning**: On macOS, the window must appear centered on the active display, not the primary. Use `window.current_monitor()` and center relative to it.
- **Global hotkey conflicts**: ⌘+Space conflicts with Spotlight on macOS. Default to ⌃+Space or make it configurable; register with `tauri-plugin-global-shortcut`'s conflict-reporting.
- **Application index staleness**: Re-index on `FSEventStream` / `ReadDirectoryChangesW` / `inotify` changes, not just at startup. Otherwise newly installed apps don't appear.
- **Icon extraction on Windows**: `ExtractIconEx` returns HICON handles that must be converted to PNG in memory; this requires `winapi` crate + manual GDI cleanup.

## Origin (reference only)

Repo: https://github.com/Xoshbin/asyar  
Key files: `asyar-launcher/src/built-in-features/` (all manifests), `asyar-launcher/src-tauri/src/commands/applications.rs`, `asyar-launcher/src-tauri/src/commands/app.rs`, `asyar-launcher/src/routes/` (view stack)
