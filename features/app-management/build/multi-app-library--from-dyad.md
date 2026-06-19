# Multi-App Library (build spec) — distilled from dyad

## Summary

Build a multi-project management layer for a local app builder: store app metadata in SQLite, scaffold directories from templates with git init, support collections (folder groupings), run each app as an independent child process, capture commit-keyed screenshots as thumbnails, and provide ripgrep-powered file search within any app. Designed for Electron but the data model is framework-agnostic.

## Core logic (inlined)

```typescript
// --- DB SCHEMA ---
// apps table
interface App {
  id: number
  name: string
  slug: string          // url-safe, unique
  path: string          // absolute filesystem path
  templateId: string | null
  collectionId: number | null
  // Cloud integrations
  githubRepoUrl: string | null
  supabaseProjectId: string | null
  vercelProjectId: string | null
  vercelProjectName: string | null
  vercelTeamId: string | null
  deploymentUrl: string | null
  neonProjectId: string | null
  // UI
  theme: string | null
  createdAt: number     // unix ms
}

// collections table
interface Collection {
  id: number
  name: string          // unique
  createdAt: number
  deletedAt: number | null   // soft delete
}

// --- CREATE APP ---
async function createApp(
  name: string,
  templateId: string,
  customAppPath?: string
): Promise<App> {
  const slug = slugify(name)
  const appPath = path.join(customAppPath ?? getDefaultAppsDir(), slug)
  
  // 1. Create DB record
  const [app] = await db.insert(apps)
    .values({ name, slug, path: appPath, templateId, createdAt: Date.now() })
    .returning()
  
  // 2. Scaffold from template
  const templatePath = getTemplatePath(templateId)
  await copyDirRecursive(templatePath, appPath, {
    exclude: ['node_modules', '.git']
  })
  
  // 3. Init git
  await git(appPath).init()
  await git(appPath).add('.')
  await git(appPath).commit('Initial commit')
  
  return app
}

// --- LIST APPS ---
async function listApps(): Promise<App[]> {
  return db.select().from(apps)
    .orderBy(desc(apps.createdAt))
}

// --- THUMBNAILS ---
// Screenshot is taken by renderer after successful build, sent as base64
async function saveScreenshot(
  appId: number,
  commitHash: string,
  base64Image: string
): Promise<void> {
  const app = await getApp(appId)
  const screenshotsDir = path.join(app.path, '.dyad', 'screenshots')
  fs.mkdirSync(screenshotsDir, { recursive: true })
  
  const filename = `${commitHash}.png`
  const filePath = path.join(screenshotsDir, filename)
  
  fs.writeFileSync(filePath, Buffer.from(base64Image, 'base64'))
  
  // Prune to MAX_SCREENSHOTS (e.g., 10) by modification time
  const existing = fs.readdirSync(screenshotsDir)
    .filter(f => /^[a-f0-9]{7,40}\.png$/.test(f))
    .map(f => ({ f, mtime: fs.statSync(path.join(screenshotsDir, f)).mtimeMs }))
    .sort((a, b) => b.mtime - a.mtime)
  
  for (const { f } of existing.slice(MAX_SCREENSHOTS)) {
    fs.unlinkSync(path.join(screenshotsDir, f))
  }
}

async function getLatestScreenshot(appId: number): Promise<string | null> {
  const app = await getApp(appId)
  const screenshotsDir = path.join(app.path, '.dyad', 'screenshots')
  if (!fs.existsSync(screenshotsDir)) return null
  
  const files = fs.readdirSync(screenshotsDir)
    .filter(f => f.endsWith('.png'))
    .sort((a, b) => {
      return fs.statSync(path.join(screenshotsDir, b)).mtimeMs
           - fs.statSync(path.join(screenshotsDir, a)).mtimeMs
    })
  
  if (files.length === 0) return null
  return fs.readFileSync(path.join(screenshotsDir, files[0])).toString('base64')
}

// --- APP LIFECYCLE ---
const runningProcesses = new Map<number, ChildProcess>()

async function runApp(appId: number): Promise<{ port: number }> {
  const app = await getApp(appId)
  
  // Detect start command from package.json
  const pkg = JSON.parse(fs.readFileSync(path.join(app.path, 'package.json'), 'utf-8'))
  const startCmd = pkg.scripts?.dev ?? pkg.scripts?.start ?? 'npm run dev'
  
  const port = await findFreePort(3000)
  const proc = spawn('sh', ['-c', startCmd], {
    cwd: app.path,
    env: { ...process.env, PORT: String(port) }
  })
  
  runningProcesses.set(appId, proc)
  return { port }
}

async function stopApp(appId: number): Promise<void> {
  const proc = runningProcesses.get(appId)
  if (proc) {
    proc.kill('SIGTERM')
    runningProcesses.delete(appId)
  }
}

// --- DELETE APP ---
async function deleteApp(appId: number): Promise<void> {
  // 1. Stop running process
  await stopApp(appId)
  
  // 2. Delete DB record (cascades to chats → messages)
  await db.delete(apps).where(eq(apps.id, appId))
  
  // 3. Delete filesystem (retry on Windows file locks)
  const app = await getApp(appId) // get before delete
  let attempts = 0
  while (attempts < 5) {
    try {
      fs.rmSync(app.path, { recursive: true, force: true })
      break
    } catch {
      await sleep(200 * (attempts + 1))
      attempts++
    }
  }
}

// --- COPY APP ---
async function copyApp(sourceId: number, newName: string, keepGitHistory: boolean): Promise<App> {
  const source = await getApp(sourceId)
  const newSlug = slugify(newName)
  const newPath = path.join(path.dirname(source.path), newSlug)
  
  await copyDirRecursive(source.path, newPath, {
    exclude: ['node_modules', ...(keepGitHistory ? [] : ['.git'])]
  })
  
  if (!keepGitHistory) {
    await git(newPath).init()
    await git(newPath).add('.')
    await git(newPath).commit('Copied from ' + source.name)
  }
  
  const [newApp] = await db.insert(apps)
    .values({ ...source, id: undefined, name: newName, slug: newSlug, path: newPath, createdAt: Date.now() })
    .returning()
  
  return newApp
}

// --- FILE SEARCH (ripgrep) ---
async function searchAppFiles(
  appId: number,
  query: string,
  excludeGlobs: string[] = ['node_modules', '.git', 'dist']
): Promise<SearchResult[]> {
  const app = await getApp(appId)
  
  const excludeArgs = excludeGlobs.flatMap(g => ['--glob', `!${g}`])
  const args = ['--json', '--smart-case', ...excludeArgs, query, app.path]
  
  const { stdout } = await execAsync(`rg ${args.map(a => `"${a}"`).join(' ')}`, {
    maxBuffer: 10 * 1024 * 1024 // 10MB
  })
  
  return stdout.split('\n')
    .filter(Boolean)
    .map(line => JSON.parse(line))
    .filter(item => item.type === 'match')
    .map(item => ({
      file: path.relative(app.path, item.data.path.text),
      line: item.data.line_number,
      text: item.data.lines.text.trim(),
      // Convert byte offset to char index for multi-byte chars
      charOffset: Buffer.from(item.data.lines.text).slice(0, item.data.submatches[0].start).toString().length
    }))
}

// --- COLLECTIONS ---
async function createCollection(name: string): Promise<Collection> {
  const [collection] = await db.insert(collections)
    .values({ name, createdAt: Date.now() })
    .returning()
  return collection
}

async function addAppToCollection(appId: number, collectionId: number): Promise<void> {
  await db.update(apps).set({ collectionId }).where(eq(apps.id, appId))
}

async function deleteCollection(collectionId: number, deleteApps: boolean): Promise<void> {
  if (deleteApps) {
    const memberApps = await db.select().from(apps).where(eq(apps.collectionId, collectionId))
    for (const app of memberApps) await deleteApp(app.id)
  } else {
    // Orphan apps (set collectionId to null)
    await db.update(apps).set({ collectionId: null }).where(eq(apps.collectionId, collectionId))
  }
  // Soft delete
  await db.update(collections).set({ deletedAt: Date.now() }).where(eq(collections.id, collectionId))
}
```

## Data contracts

```typescript
// IPC: apps:list → App[]
// IPC: apps:create(name, templateId, customPath?) → App
// IPC: apps:delete(appId) → void
// IPC: apps:copy(appId, newName, keepGitHistory) → App
// IPC: apps:run(appId) → { port: number }
// IPC: apps:stop(appId) → void
// IPC: apps:save-screenshot(appId, commitHash, base64) → void
// IPC: apps:get-screenshot(appId) → string (base64) | null
// IPC: apps:search-files(appId, query, excludeGlobs?) → SearchResult[]
// IPC: collections:create(name) → Collection
// IPC: collections:list → Collection[]
// IPC: collections:add-app(appId, collectionId) → void
// IPC: collections:delete(collectionId, deleteApps) → void

interface SearchResult {
  file: string     // relative path
  line: number
  text: string     // matched line content
  charOffset: number
}
```

## Dependencies & assumptions

- **dugite** or **simple-git**: Git operations (init, add, commit)
- **ripgrep** (`rg`): Must be bundled with the app or available on PATH for file search
- **Node `child_process`**: For running dev servers
- **Drizzle ORM** + **better-sqlite3**: DB
- Templates must exist as directories on the app's install path

## To port this, you need:

- [ ] DB schema: `apps` table with all integration columns, `collections` with soft-delete
- [ ] Template directory structure on disk (scaffold source)
- [ ] `createApp`: DB insert → directory copy → git init → initial commit
- [ ] `deleteApp`: stop process → DB delete → `fs.rmSync` with retry loop (Windows file locks)
- [ ] `copyApp`: directory copy excluding node_modules, optional git history
- [ ] Process map (`Map<appId, ChildProcess>`) for lifecycle management
- [ ] Screenshot save: commit-keyed filename, LRU pruning by mtime
- [ ] ripgrep integration for file search with byte-to-char offset conversion
- [ ] Collections CRUD with soft delete and orphan/cascade options

## Gotchas

- **Windows file lock on delete:** `node_modules` and `.git` directories can be locked on Windows even after killing the process. Retry `fs.rmSync` with exponential backoff (up to 5 attempts, 200ms base).
- **ripgrep byte offsets vs character offsets:** rg returns byte offsets. For files with emoji or multibyte Unicode, byte offset ≠ character position. Convert: `Buffer.from(line).slice(0, byteOffset).toString().length`.
- **Thumbnail keyed to commit hash, not time:** If a user reverts to an earlier commit, the thumbnail from that commit hash reappears. This is a feature (thumbnails stay accurate to code state), but means you need git to be initialized before screenshots can be taken.
- **Custom app path must be absolute:** Relative paths break when the app changes working directory. Validate and reject relative paths in the IPC handler.
- **Template exclusion of node_modules:** Don't copy `node_modules` from templates — this would be massive and the wrong version. Always exclude it and require `npm install` after scaffold.

## Origin (reference only)
- Repo: https://github.com/dyad-sh/dyad
- Key files: `src/ipc/handlers/app_handlers.ts`, `src/pages/apps.tsx`
