# Multi-App Library — from [dyad](https://github.com/dyad-sh/dyad)

> Domain: [[_domain]] · Source: https://github.com/dyad-sh/dyad · NotebookLM: 

## What it does

Dyad lets you build and manage many separate apps from a single interface. The Apps page shows all your projects as cards in a responsive grid, with thumbnails (auto-captured screenshots tied to git commits), search, and bulk actions. Apps can be organized into collections (like folders), copied, moved to custom directories, renamed, and deleted. Each app runs as an independent local process with its own git history.

## Why it exists

The vision is that you'd use Dyad to spin up many small apps — tools, experiments, dashboards — not one monolithic project. The library is the home base for that collection. Collections exist because users naturally want to group related experiments (e.g., "marketing tools," "client X projects") without having to memorize app names.

## How it actually works

**Data model:**
```
apps table:
  id, name, slug, path (filesystem path), templateId, collectionId,
  githubRepoUrl, supabaseProjectId, vercelProjectId, vercelProjectName, 
  vercelTeamId, deploymentUrl, neonProjectId, theme, createdAt
  
collections table:
  id, name (unique), createdAt, deletedAt (soft delete cascade)
```

**App creation:** `createApp` handler: creates a DB record, scaffolds the directory from a template (copies template files into the app path), initializes a git repo with `git init`, makes an initial commit ("Initial commit"), and returns the new app record to the renderer. The app path is either the user's configured custom apps folder or a default location.

**App listing:** `listApps` returns all apps sorted by `createdAt` descending. The frontend additionally fetches thumbnails for all app IDs in one call (shared cache with the home page). `sortAppsForShowcase()` applies a secondary sort (pinned apps first, then recent).

**Search:** Two search surfaces:
1. Client-side filter on the apps page — fuzzy matches app name as user types
2. Server-side `search-app` IPC handler — SQL `LIKE` pattern matching across app names, chat message content, and chat titles. Returns a deduplicated ranked list (exact name matches ranked higher).

**Thumbnails:** Screenshots are taken by the renderer at certain lifecycle points (after a build completes), base64-encoded, sent to the main process via IPC, and saved to a screenshots subdirectory. Each screenshot is keyed to a git commit hash, ensuring the thumbnail matches a specific code state. Maximum screenshots per app are pruned by modification time. The AppsPage fetches all thumbnails up front using `useAppThumbnails(allAppIds)` to populate cards.

**Collections:**
- Collections are SQLite rows with a name and optional cascade-delete behavior
- Apps are assigned to a collection via `collectionId` FK
- The Apps page has two view tabs: "apps" (grid of app cards) and "collections" (grid of folder-like collection cards)
- Renaming/deleting collections updates all member apps

**Bulk actions:** When `isSelectionMode` is true, checkboxes appear on cards. Users can select individual apps or "select all visible" (filtered list). Bulk operations: add to collection, delete with confirmation dialog listing affected app names.

**App lifecycle:**
- `runApp`: starts the app's dev server as a child process, monitors port
- `stopApp`: kills the process, cleans up the port
- `restartApp`: stop + run
- `copyApp`: deep-copies the directory (excluding node_modules), creates a new DB record, optionally preserves git history
- `changeAppLocation`: moves the directory to a new parent, updates the DB path
- `deleteApp`: stops the process, deletes DB record, recursively deletes the directory (with retry logic for file locks on Windows)

## The non-obvious parts

- **Thumbnails are commit-keyed, not time-keyed:** The screenshot stored for a card represents a specific git state. If you build the same commit twice, the same screenshot is used. This prevents stale thumbnails after a revert.
- **ripgrep for file search:** The `searchAppFiles` handler uses ripgrep (bundled with the app) for content search inside a specific app's files — not SQLite FTS. This handles large codebases much faster than Node's fs module. UTF-8 byte offsets are converted to character positions to handle emoji/multibyte correctly.
- **Custom apps folder:** Users can configure a non-default directory for where app directories are created. Dyad validates it's an absolute path and that it exists. Apps created before the path change stay in their original locations.
- **Collections use soft deletes:** A `deletedAt` timestamp marks collections as deleted rather than hard-deleting them immediately. This allows recovery (though no recovery UI is exposed). The `collectionId` on orphaned apps goes to null on cascade.

## Related
- [[cloud-deploy--from-dyad]] (deployment URL surfaces in app cards)
- [[ai-chat-stream--from-dyad]] (chat sessions are per-app)
