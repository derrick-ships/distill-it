# Chat Persistence (build spec) — distilled from bolt.diy

## Summary

Implement a two-store IndexedDB database (`boltHistory` v2) for storing chat sessions and project snapshots. Expose typed async CRUD operations for chats and snapshots. Key design: numeric `id` for internal use, string `urlId` for URLs, and a `metadata` field for deployment/git references.

## Core logic (inlined)

```typescript
import { openDB, type IDBPDatabase } from 'idb';

const DB_NAME = 'boltHistory';
const DB_VERSION = 2;

let _db: IDBPDatabase | null = null;

async function getDB(): Promise<IDBPDatabase> {
  if (_db) return _db;
  _db = await openDB(DB_NAME, DB_VERSION, {
    upgrade(db, oldVersion) {
      if (oldVersion < 1) {
        const chatsStore = db.createObjectStore('chats', { keyPath: 'id', autoIncrement: true });
        chatsStore.createIndex('id', 'id', { unique: true });
        chatsStore.createIndex('urlId', 'urlId', { unique: true });
      }
      if (oldVersion < 2) {
        db.createObjectStore('snapshots', { keyPath: 'chatId' });
      }
    },
  });
  return _db;
}

// === Chat CRUD ===

interface ChatRecord {
  id?: number;
  urlId: string;
  messages: Message[];
  description: string;
  timestamp: string;
  metadata?: ChatMetadata;
}

interface ChatMetadata {
  gitUrl?: string;
  gitBranch?: string;
  netlifySiteId?: string;
  vercelProjectId?: string;
}

async function createChat(data: Omit<ChatRecord, 'id'>): Promise<ChatRecord> {
  const db = await getDB();
  const id = await db.add('chats', { ...data, timestamp: new Date().toISOString() });
  return { ...data, id: id as number };
}

async function getChatByUrlId(urlId: string): Promise<ChatRecord | undefined> {
  const db = await getDB();
  return db.getFromIndex('chats', 'urlId', urlId);
}

async function getAllChats(): Promise<ChatRecord[]> {
  const db = await getDB();
  const all = await db.getAll('chats');
  return all.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
}

async function updateChatMessages(urlId: string, messages: Message[]): Promise<void> {
  const db = await getDB();
  const chat = await getChatByUrlId(urlId);
  if (!chat) throw new Error('Chat not found');
  await db.put('chats', { ...chat, messages });
}

async function updateChatMetadata(urlId: string, metadata: Partial<ChatMetadata>): Promise<void> {
  const db = await getDB();
  const chat = await getChatByUrlId(urlId);
  if (!chat) throw new Error('Chat not found');
  await db.put('chats', { ...chat, metadata: { ...chat.metadata, ...metadata } });
}

async function forkChat(urlId: string, messageIndex: number): Promise<ChatRecord> {
  const db = await getDB();
  const original = await getChatByUrlId(urlId);
  if (!original) throw new Error('Chat not found');
  const fork: Omit<ChatRecord, 'id'> = {
    urlId: generateUrlId(),
    messages: original.messages.slice(0, messageIndex + 1),
    description: `Fork of: ${original.description}`,
    timestamp: new Date().toISOString(),
    metadata: undefined,
  };
  return createChat(fork);
}

async function deleteChat(id: number): Promise<void> {
  const db = await getDB();
  await db.delete('chats', id);
  await db.delete('snapshots', id); // cascade
}

// === Snapshot CRUD ===

interface SnapshotRecord {
  chatId: number;
  files: Record<string, string>;
  timestamp: string;
}

async function saveSnapshot(chatId: number, files: Record<string, string>): Promise<void> {
  const db = await getDB();
  await db.put('snapshots', { chatId, files, timestamp: new Date().toISOString() });
}

async function getSnapshot(chatId: number): Promise<SnapshotRecord | undefined> {
  const db = await getDB();
  return db.get('snapshots', chatId);
}

// === URL ID generation ===

function generateUrlId(): string {
  return Math.random().toString(36).slice(2, 9); // 7-char alphanumeric
}
```

## Data contracts

```typescript
interface ChatRecord {
  id?: number;          // IndexedDB auto-increment key
  urlId: string;        // shown in URL: /chat/{urlId}
  messages: Message[];  // full conversation history
  description: string;  // human-readable title
  timestamp: string;    // ISO 8601
  metadata?: {
    gitUrl?: string;          // source repo URL if imported from git
    gitBranch?: string;
    netlifySiteId?: string;   // for re-deploys
    vercelProjectId?: string;
  };
}

interface SnapshotRecord {
  chatId: number;
  files: Record<string, string>; // {path: content} at snapshot time
  timestamp: string;
}

// Message shape (extends Vercel AI SDK CoreMessage)
type Message = CoreMessage & {
  id: string;
  type?: 'chatSummary'; // special type for context optimization summaries
};
```

## Dependencies & assumptions

- `idb` npm package — typed IndexedDB wrapper (`npm install idb`)
- Runs client-side only (IndexedDB is a browser API)
- `urlId` uniqueness is enforced by the IndexedDB unique index — retry with a new ID if `add()` throws `ConstraintError`

## To port this, you need:
- [ ] `npm install idb`
- [ ] Create `getDB()` with `openDB(DB_NAME, VERSION, { upgrade })` handling v1→v2 migration
- [ ] Implement `createChat`, `getChatByUrlId`, `getAllChats`, `updateChatMessages`, `deleteChat`
- [ ] Implement `saveSnapshot` and `getSnapshot` on the snapshots store
- [ ] Wire `getAllChats()` to your sidebar/history UI (sorted newest-first)
- [ ] Wire `getChatByUrlId(params.id)` in your chat route loader
- [ ] Store `netlifySiteId`/`vercelProjectId` in metadata after first deploy

## Gotchas

- **IndexedDB is async throughout**: every operation is a Promise. Never call these from synchronous code.
- **Schema version bumping**: incrementing `DB_VERSION` triggers `onupgradeneeded`. Always write migrations with `if (oldVersion < N)` guards — NOT `if (oldVersion === N-1)`, or you'll break multi-version upgrades.
- **ConstraintError on urlId**: if you generate a duplicate `urlId`, `db.add()` throws. Retry with a new ID rather than catching and ignoring.
- **Snapshot size**: storing full file trees in IndexedDB can get large (50MB+ for complex projects). Browser IndexedDB quotas vary by browser but are typically 50-60% of available disk space. For production, add a cleanup job to purge old snapshots.
- **Forked chats don't inherit snapshots**: after a fork, the new chat has no snapshot. The files must be re-derived by replaying the messages, or you must snapshot immediately after forking.

## Origin (reference only)

- Repo: https://github.com/stackblitz-labs/bolt.diy
- `app/lib/persistence/db.ts` — full IndexedDB implementation
- `app/lib/persistence/` — related helpers (useChatHistory hook, etc.)
