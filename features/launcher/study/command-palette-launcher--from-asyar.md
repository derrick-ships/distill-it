# Command-Palette Launcher — from [asyar](https://github.com/Xoshbin/asyar)

> Domain: [[_domain]] · Source: https://github.com/Xoshbin/asyar · NotebookLM:

## What it does

Asyar's core is a floating command palette that appears on demand (global hotkey, usually ⌘+Space or custom). You type, and the launcher instantly shows a ranked list of: installed applications, built-in commands (calculator, clipboard history, AI agents, scripts, etc.), extension commands, and user-defined aliases. Press Enter to launch anything. The window hides when you dismiss or launch.

## Why it exists

Every power user workflow bottleneck is "find the right thing fast." A keyboard-first launcher removes the mouse from the equation — it is the muscle memory layer for the entire OS. Asyar exists as a privacy-first, open-source, cross-platform alternative to Raycast (Mac-only, cloud-synced) and Alfred (paid, Mac-only).

## How it actually works

**Architecture**: The launcher is a Tauri v2 desktop app. The Rust backend handles OS-level concerns (application indexing, global hotkey, window management), while the Svelte 5 frontend renders the palette UI.

**Window lifecycle**: The window is always running in the background (spawned at startup). When the global hotkey fires, the Rust backend calls `show_window()` — which reveals the already-rendered Svelte UI without a cold-start delay. On dismiss, it hides rather than destroys.

**Built-in feature registry**: Every feature (calculator, snippets, clipboard, agents, scripts, extensions) registers itself as a "built-in" with a `manifest.json` that declares its name, keyword triggers, icon, and a Svelte view component. At startup the launcher indexes all manifests and merges them with indexed applications into a single searchable pool.

**Application indexing**: The Rust backend scans platform-appropriate locations (macOS `/Applications`, Windows registry/Start menu, Linux `.desktop` files) and builds an in-memory app list. The TypeScript frontend receives this list via a Tauri `invoke` call.

**Search**: Fuzzy search runs in the frontend against the merged pool. The query is scored against name, description, and keywords; results are sorted by score then recency (frequently launched items rise over time).

**Result rendering**: Each result in the list is rendered by its owning feature. Applications show icon + name. Built-in commands show a keyword chip. Selecting a result calls the command's action handler, which either opens an app via `open()` or navigates to the feature's dedicated view within the same window.

**Navigation model**: The launcher is a single window with a stack of views. The search list is the root. Selecting a feature (e.g. AI Agents) pushes that feature's view onto the stack. Escape pops back to the list or hides the window at the root level.

## The non-obvious parts

**No cold start**: Hiding vs destroying the window is critical for perceived performance. The Rust side calls `hide()`, keeping the WebView alive. `show()` just sets visibility — sub-millisecond.

**Built-in priority over extensions**: The manifest-based registry enforces a clear hierarchy so native built-ins always appear before extension commands with overlapping keywords. Users can override with aliases.

**Privacy by default**: The launcher never logs what the user types. The search query never leaves the device. Application index data is stored locally; no telemetry endpoint.

**Cross-platform challenges**: Application indexing is entirely platform-specific Rust code — three separate discovery paths — abstracted behind a single `list_applications()` command. The frontend never knows which platform it's on.

## Related

- [[alias-system--from-asyar]] (aliases surface here as synthetic commands)
- [[sandboxed-extension-system--from-asyar]] (extensions appear as commands in this list)
- [[snippets-text-expansion--from-asyar]] (snippets show up as searchable commands)
- [[deep-link-command-triggers--from-asyar]] (deep links trigger commands in this same registry)
