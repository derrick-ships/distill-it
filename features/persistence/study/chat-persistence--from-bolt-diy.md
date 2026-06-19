# Chat Persistence (IndexedDB) — from [bolt.diy](https://github.com/stackblitz-labs/bolt.diy)

> Domain: [[_domain]] · Source: https://github.com/stackblitz-labs/bolt.diy · NotebookLM:

## What it does

Every conversation in bolt.diy is saved to the browser's IndexedDB database. Your chat history, all the messages the AI generated, the project files that were created, the deployment URLs — all of it persists across browser sessions without any server storage. You can close the tab, come back tomorrow, and pick up exactly where you left off. You can also fork a conversation at any point (creating a branch from a specific message), duplicate entire sessions, and delete them individually.

## Why it exists

Bolt.diy is designed to be self-hostable with zero backend infrastructure. Storing everything in the browser means no database to manage, no auth to build, no privacy concerns about conversation data leaving the user's machine. The trade-off is that data lives in one browser — you can't sync across devices. But for the target user (developer using a personal machine), this is an acceptable trade-off that dramatically simplifies the product.

## How it actually works

The database is `boltHistory`, version 2, with two IndexedDB object stores:

**Chats store** (v1): Keyed by `id` (numeric auto-increment). Has two unique indexes: `id` and `urlId` (a human-readable URL slug like `abc123`). Each chat record contains:
- `id`: numeric key
- `urlId`: URL-safe identifier, used as the URL path (`/chat/abc123`)
- `messages`: the full array of message objects
- `description`: user-provided title, auto-generated from first messages
- `timestamp`: ISO date string
- `metadata`: optional object with deployment/git info (`gitUrl`, `gitBranch`, `netlifySiteId`, `vercelProjectId`)

**Snapshots store** (v2): Keyed by `chatId`. Stores the WebContainer's file state at a point in time — a complete file tree snapshot. This lets bolt restore a project to exactly the state it was in at any message in the conversation.

The persistence layer exposes clean async operations: `getDB()` returns the database handle (opening and migrating on first call), and everything else is wrapped in `idb-keyval`-style promise chains over the native IndexedDB API.

The sidebar shows all chats sorted by timestamp. Clicking a chat loads its messages and replays the file state from the snapshot, restoring the workbench to that exact point.

## The non-obvious parts

- **urlId vs id**: the `id` is numeric and used internally. The `urlId` is what appears in the browser URL bar. They're separate so you can have pretty URLs without exposing internal database keys.
- **Forking**: bolt can fork a conversation at message N by creating a new chat record with `messages.slice(0, N)` and a fresh urlId. The fork is a complete copy — changes in the fork don't affect the original.
- **Snapshot timing**: snapshots aren't taken after every message. They're taken at meaningful checkpoints (e.g., after a deploy succeeds, or when the user explicitly saves). Restoring from a snapshot before that checkpoint means replaying all the file-writing actions from that point.
- **Schema migration**: upgrading from v1 to v2 added the snapshots store. The `onupgradeneeded` handler creates the new store only if it doesn't exist, so existing chat data survives the upgrade.
- **No cloud sync**: chat data is purely local. There's no export/import UI in the open-source version. The metadata field (gitUrl, gitBranch) lets technically savvy users reconstruct the project from git, but there's no built-in restore path.

## Related
- [[context-optimization--from-bolt-diy]] (summaries are stored as special messages in the chats store)
- [[one-click-deployment--from-bolt-diy]] (deploy URLs stored in chat metadata)
- [[webcontainer-runtime--from-bolt-diy]] (snapshots capture runtime file state)
