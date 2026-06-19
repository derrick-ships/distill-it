# One-Click Deployment (build spec) — distilled from bolt.diy

## Summary

Build server-side API routes for deploying in-browser project files to Vercel and Netlify without CLI tools. Each route handles: auth validation, project creation (if first deploy), framework detection, file upload, status polling, and returning the live URL. Tokens come from the client POST body; project IDs are cached in the client for re-deploys.

## Core logic (inlined)

```typescript
// === VERCEL DEPLOYMENT ===

async function deployToVercel(request: Request): Promise<Response> {
  const { files, token, chatId, projectId } = await request.json();
  if (!token) return new Response('Not connected to Vercel', { status: 401 });

  const VERCEL_API = 'https://api.vercel.com';
  const headers = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };

  // 1. Framework detection
  const framework = detectFramework(files);

  // 2. Project management
  let activeProjectId = projectId;
  if (!activeProjectId) {
    const proj = await fetch(`${VERCEL_API}/v9/projects`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ name: `bolt-diy-${chatId}-${Date.now()}`, framework }),
    }).then(r => r.json());
    activeProjectId = proj.id;
  }

  // 3. Deploy
  const buildConfig = FRAMEWORK_BUILD_CONFIG[framework] ?? { buildCommand: 'npm run build', outputDirectory: 'dist' };
  const deploy = await fetch(`${VERCEL_API}/v13/deployments`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      name: `bolt-diy-${chatId}`,
      projectId: activeProjectId,
      files: Object.entries(files).map(([path, content]) => ({ file: path, data: content })),
      ...buildConfig,
    }),
  }).then(r => r.json());

  // 4. Poll
  const result = await pollVercelDeployment(deploy.id, token, 120, 2000); // 2min, 2s interval
  return Response.json({ deployId: result.id, url: result.url, projectId: activeProjectId });
}

async function pollVercelDeployment(deployId: string, token: string, maxSec: number, interval: number) {
  const deadline = Date.now() + maxSec * 1000;
  while (Date.now() < deadline) {
    const status = await fetch(`https://api.vercel.com/v13/deployments/${deployId}`, {
      headers: { Authorization: `Bearer ${token}` },
    }).then(r => r.json());
    if (status.readyState === 'READY') return status;
    if (status.readyState === 'ERROR') throw new Error(`Deploy failed: ${status.errorMessage}`);
    await sleep(interval);
  }
  throw new Error('Deployment timed out');
}

// === NETLIFY DEPLOYMENT ===

async function deployToNetlify(request: Request): Promise<Response> {
  const { files, token, chatId, siteId } = await request.json();
  if (!token) return new Response('Not connected to Netlify', { status: 401 });

  const BASE = 'https://api.netlify.com/api/v1';
  const headers = { Authorization: `Bearer ${token}` };

  // 1. Site management
  let activeSiteId = siteId;
  if (!activeSiteId) {
    const site = await fetch(`${BASE}/sites`, {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: `bolt-diy-${chatId}-${Date.now()}` }),
    }).then(r => r.json());
    activeSiteId = site.id;
  }

  // 2. Hash all files (SHA-1)
  const fileHashes: Record<string, string> = {};
  for (const [path, content] of Object.entries(files)) {
    const normalPath = path.startsWith('/') ? path : `/${path}`;
    fileHashes[normalPath] = await sha1(content);
  }

  // 3. Create deploy with hashes (content-addressable protocol)
  const deploy = await fetch(`${BASE}/sites/${activeSiteId}/deploys`, {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ files: fileHashes, async: true }),
  }).then(r => r.json());

  // 4. Poll until "prepared" (Netlify tells us which files it needs)
  const prepared = await pollNetlifyDeploy(deploy.id, token, BASE, ['prepared', 'uploaded']);

  // 5. Upload only the files Netlify requested
  const requiredFiles = prepared.required ?? Object.keys(fileHashes);
  for (const hash of requiredFiles) {
    const [path, content] = Object.entries(files).find(([p]) => fileHashes[`/${p}`] === hash || fileHashes[p] === hash)!;
    const normalPath = path.startsWith('/') ? path : `/${path}`;
    await uploadWithRetry(`${BASE}/deploys/${deploy.id}/files${normalPath}`, content, token, 3);
  }

  return Response.json({ deployId: deploy.id, url: prepared.deploy_ssl_url, siteId: activeSiteId });
}

async function uploadWithRetry(url: string, content: string, token: string, retries: number) {
  for (let i = 0; i < retries; i++) {
    const res = await fetch(url, {
      method: 'PUT',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/octet-stream' },
      body: content,
    });
    if (res.ok) return;
    if (i < retries - 1) await sleep(2000);
  }
  throw new Error(`Upload failed for ${url}`);
}

// === FRAMEWORK DETECTION ===

function detectFramework(files: Record<string, string>): string {
  const pkgJson = files['package.json'];
  if (pkgJson) {
    const pkg = JSON.parse(pkgJson);
    const deps = { ...pkg.dependencies, ...pkg.devDependencies };
    if (deps['next']) return 'nextjs';
    if (deps['@angular/core']) return 'angular';
    if (deps['vue']) return 'vue';
    if (deps['nuxt']) return 'nuxt';
    if (deps['react'] || deps['react-dom']) return 'create-react-app';
  }
  if (files['next.config.js'] || files['next.config.ts']) return 'nextjs';
  if (files['vite.config.ts'] || files['vite.config.js']) return 'vite';
  return 'other';
}

const FRAMEWORK_BUILD_CONFIG: Record<string, { buildCommand: string; outputDirectory: string }> = {
  nextjs: { buildCommand: 'npm run build', outputDirectory: '.next' },
  'create-react-app': { buildCommand: 'npm run build', outputDirectory: 'build' },
  vue: { buildCommand: 'npm run build', outputDirectory: 'dist' },
  vite: { buildCommand: 'npm run build', outputDirectory: 'dist' },
  other: { buildCommand: 'npm run build', outputDirectory: 'dist' },
};
```

## Data contracts

```typescript
// Vercel deploy request
interface VercelDeployRequest {
  files: Record<string, string>; // {filePath: fileContent}
  token: string;
  chatId: string;
  projectId?: string;            // undefined on first deploy
}

// Netlify deploy request
interface NetlifyDeployRequest {
  files: Record<string, string>;
  token: string;
  chatId: string;
  siteId?: string;               // undefined on first deploy
}

// Both return
interface DeployResult {
  deployId: string;
  url: string;
  projectId?: string;   // Vercel
  siteId?: string;      // Netlify
  state: string;
}
```

## Dependencies & assumptions

- Server-side Remix/Express action (don't expose tokens from client directly to provider APIs)
- `crypto.subtle.digest('SHA-1', ...)` for Netlify file hashing (Web Crypto API, available in Cloudflare Workers)
- No external SDK needed — plain `fetch` to provider REST APIs

## To port this, you need:
- [ ] Server route that accepts `{ files, token, chatId, projectId? }` POST body
- [ ] Implement `detectFramework()` against `package.json` deps + config files
- [ ] Implement Vercel flow: project creation → v13 deploy → status poll
- [ ] Implement Netlify flow: site creation → hash files → deploy with hashes → poll prepared → upload required files
- [ ] Store returned `projectId`/`siteId` in client state so re-deploys update, not recreate
- [ ] Show deploy URL in UI as a clickable link when done

## Gotchas

- **Vercel `readyState` vs Netlify `state`**: different field names and values. Vercel uses `READY`/`ERROR`; Netlify uses `prepared`/`uploaded`/`error`.
- **Netlify required files**: not all hashes are "required" — Netlify already has files it's seen before. Only upload what `deploy.required` lists. Uploading everything every time works but is slow.
- **Vercel project name collisions**: `bolt-diy-{chatId}-{timestamp}` avoids collisions but creates a new project every session. Cache the `projectId` client-side.
- **Rate limits**: Netlify's file upload endpoint rate-limits on free plans. The 3-retry + 2s backoff handles transient limits; sustained limits need exponential backoff.
- **SHA-1 for Netlify**: yes, SHA-1 is broken for security but Netlify uses it for content addressing. Don't substitute SHA-256.

## Origin (reference only)

- Repo: https://github.com/stackblitz-labs/bolt.diy
- `app/routes/api.vercel-deploy.ts`
- `app/routes/api.netlify-deploy.ts`
