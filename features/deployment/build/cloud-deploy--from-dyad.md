# Cloud Deploy (build spec) — distilled from dyad

## Summary

Build a one-click Vercel deployment integration into a local app builder: validate and store a Vercel token (encrypted), auto-detect the project's framework from config files and package.json, create a Vercel project via REST API, push environment variables for connected databases, trigger an initial deployment, and poll for deployment status to surface a live URL.

## Core logic (inlined)

```typescript
// --- TOKEN SAVE & VALIDATE ---
async function saveVercelToken(token: string): Promise<void> {
  // Validate before saving
  const res = await fetch('https://api.vercel.com/v2/user', {
    headers: { Authorization: `Bearer ${token}` }
  })
  if (!res.ok) throw new Error('Invalid Vercel token')
  
  // Encrypt and store (Electron safeStorage or equivalent KMS)
  writeEncryptedSetting('vercelToken', token)
}

// --- FRAMEWORK DETECTION ---
const FRAMEWORK_CONFIG_FILES: Record<string, string> = {
  'next.config.js': 'nextjs',
  'next.config.ts': 'nextjs',
  'next.config.mjs': 'nextjs',
  'vite.config.ts': 'vite',
  'vite.config.js': 'vite',
  'astro.config.mjs': 'astro',
  'nuxt.config.ts': 'nuxtjs',
  'svelte.config.js': 'svelte',
  'remix.config.js': 'remix',
  'angular.json': 'angular',
  'gatsby-config.js': 'gatsby',
}

const FRAMEWORK_DEPS: [string, string][] = [
  ['next', 'nextjs'],
  ['vite', 'vite'],
  ['nuxt', 'nuxtjs'],
  ['@angular/core', 'angular'],
  ['react', 'create-react-app'],
  ['vue', 'vue'],
  ['gatsby', 'gatsby'],
  ['@remix-run/react', 'remix'],
]

async function detectFramework(appPath: string): Promise<string | null> {
  // Priority 1: config files
  for (const [file, framework] of Object.entries(FRAMEWORK_CONFIG_FILES)) {
    if (fs.existsSync(path.join(appPath, file))) return framework
  }
  
  // Priority 2: package.json dependencies
  try {
    const pkg = JSON.parse(fs.readFileSync(path.join(appPath, 'package.json'), 'utf-8'))
    const allDeps = { ...pkg.dependencies, ...pkg.devDependencies }
    for (const [dep, framework] of FRAMEWORK_DEPS) {
      if (dep in allDeps) return framework
    }
  } catch {}
  
  return null
}

// --- PROJECT CREATION ---
async function createVercelProject(
  appId: number,
  appPath: string,
  projectName: string,
  teamId: string | null
): Promise<{ projectId: string; deploymentUrl: string }> {
  const token = readDecryptedSetting('vercelToken')
  const framework = await detectFramework(appPath)
  
  const headers = {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  }
  
  const teamQuery = teamId ? `?teamId=${teamId}` : ''
  
  // Create project
  const createRes = await fetch(`https://api.vercel.com/v9/projects${teamQuery}`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      name: projectName,
      framework: framework ?? undefined,
    })
  })
  
  if (!createRes.ok) throw new Error(await createRes.text())
  const project = await createRes.json()
  
  // Store in DB
  await db.update(apps)
    .set({
      vercelProjectId: project.id,
      vercelProjectName: project.name,
      vercelTeamId: teamId,
    })
    .where(eq(apps.id, appId))
  
  // Push DB env vars before first deploy
  await syncDatabaseEnvVars(project.id, teamId, appId, token)
  
  // Trigger initial deployment (via Vercel's deploy hook or CLI push)
  const deploymentUrl = await triggerDeployment(project.id, teamId, token)
  
  return { projectId: project.id, deploymentUrl }
}

// --- ENV VAR SYNC ---
async function syncDatabaseEnvVars(
  projectId: string,
  teamId: string | null,
  appId: number,
  token: string
): Promise<void> {
  const app = await db.select().from(apps).where(eq(apps.id, appId)).get()
  
  // Neon database
  if (app?.neonProjectId) {
    const dbUrl = await getNeonConnectionString(app.neonProjectId)
    await setVercelEnvVar(projectId, teamId, 'DATABASE_URL', dbUrl, token)
  }
  
  // Supabase
  if (app?.supabaseProjectId) {
    const { url, anonKey } = await getSupabaseCredentials(app.supabaseProjectId)
    await setVercelEnvVar(projectId, teamId, 'NEXT_PUBLIC_SUPABASE_URL', url, token)
    await setVercelEnvVar(projectId, teamId, 'NEXT_PUBLIC_SUPABASE_ANON_KEY', anonKey, token)
  }
}

async function setVercelEnvVar(
  projectId: string,
  teamId: string | null,
  key: string,
  value: string,
  token: string
): Promise<void> {
  const teamQuery = teamId ? `?teamId=${teamId}` : ''
  await fetch(`https://api.vercel.com/v9/projects/${projectId}/env${teamQuery}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ key, value, type: 'encrypted', target: ['production', 'preview'] })
  })
}

// --- DEPLOYMENT STATUS ---
async function getDeployments(appId: number): Promise<Deployment[]> {
  const app = await db.select().from(apps).where(eq(apps.id, appId)).get()
  if (!app?.vercelProjectId) return []
  
  const token = readDecryptedSetting('vercelToken')
  const teamQuery = app.vercelTeamId ? `&teamId=${app.vercelTeamId}` : ''
  
  const res = await fetch(
    `https://api.vercel.com/v6/deployments?projectId=${app.vercelProjectId}&limit=5${teamQuery}`,
    { headers: { Authorization: `Bearer ${token}` } }
  )
  
  const { deployments } = await res.json()
  
  // Update stored deployment URL when production build succeeds
  const latestProd = deployments.find((d: any) => d.target === 'production' && d.state === 'READY')
  if (latestProd?.url) {
    await db.update(apps)
      .set({ deploymentUrl: `https://${latestProd.url}` })
      .where(eq(apps.id, appId))
  }
  
  return deployments.map((d: any) => ({
    id: d.uid,
    url: `https://${d.url}`,
    state: d.state,
    createdAt: d.createdAt,
    target: d.target,
  }))
}
```

## Data contracts

```typescript
// DB: apps table (Vercel-relevant columns)
interface AppVercelFields {
  vercelProjectId: string | null
  vercelProjectName: string | null
  vercelTeamId: string | null
  deploymentUrl: string | null
}

// IPC: vercel:list-projects → VercelProject[]
interface VercelProject {
  id: string
  name: string
  teamId: string | null
}

// IPC: vercel:create-project(appId, projectName, teamId?) → { projectId, deploymentUrl }
// IPC: vercel:get-deployments(appId) → Deployment[]
interface Deployment {
  id: string
  url: string
  state: 'BUILDING' | 'READY' | 'ERROR' | 'CANCELED'
  createdAt: number
  target: 'production' | 'preview' | null
}

// Settings (encrypted)
// vercelToken: string
```

## Dependencies & assumptions

- Vercel REST API v9 (projects), v6 (deployments), v2 (user)
- Encrypted settings for token storage (Electron safeStorage or equivalent)
- App must have a `package.json` for framework detection
- Neon/Supabase integrations are optional but must be resolved before first deploy

## To port this, you need:

- [ ] Encrypted token storage + validation on save
- [ ] `detectFramework()` checking both config files and package.json deps
- [ ] Vercel project creation via REST API (`POST /v9/projects`)
- [ ] DB columns for `vercelProjectId`, `vercelProjectName`, `vercelTeamId`, `deploymentUrl`
- [ ] Env var sync before first deploy (DATABASE_URL, Supabase keys, etc.)
- [ ] Deployment list endpoint polling last 5 deployments
- [ ] Production deployment URL extraction and persistence
- [ ] List projects endpoint for "connect to existing project" flow

## Gotchas

- **Token must be validated immediately:** Don't save a bad token and let the user discover it fails later during create. Validate against `/v2/user` on entry.
- **Framework auto-detection ordering matters:** Check config files before package.json deps — a project can have `vite` in deps but actually be a Next.js project with the next config file. Config files are more authoritative.
- **teamId can be null:** Personal Vercel accounts have no team. Always handle `null` teamId — don't include the `?teamId=` query param when null (Vercel API rejects empty string).
- **Deployment URL timing:** The URL returned at project create time is a placeholder. The real production URL is only available after the first `READY` deployment. Poll `/v6/deployments` to get it.
- **Env vars must go before the build:** Set `DATABASE_URL` before triggering the initial deployment, not after. The build will fail if it can't connect to the database at startup.
- **Token is machine-specific:** Encrypted via safeStorage. If you support team sharing or cloud sync, you need a different token distribution mechanism.

## Origin (reference only)
- Repo: https://github.com/dyad-sh/dyad
- Key files: `src/ipc/handlers/vercel_handlers.ts`, `src/ipc/handlers/neon_handlers.ts`
