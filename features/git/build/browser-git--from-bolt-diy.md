# Browser Git (build spec) — distilled from bolt.diy

## Summary

Use `isomorphic-git` to clone GitHub repos inside the browser, route git HTTP traffic through a server-side CORS proxy, filter out noise files, and load the result into your app as a file tree. The proxy is a thin pass-through Remix/Express route that adds CORS headers to git server responses.

## Core logic (inlined)

```typescript
// === CORS PROXY (server-side: Remix route api.git-proxy.$.ts) ===

export async function loader({ request, params }: LoaderArgs) {
  if (request.method === 'OPTIONS') {
    return new Response(null, { headers: corsHeaders() });
  }

  // URL shape: /api/git-proxy/github.com/owner/repo/...
  const proxyPath = params['*']; // "github.com/owner/repo/info/refs?service=..."
  const targetUrl = `https://${proxyPath}${new URL(request.url).search}`;

  const ALLOWED_REQUEST_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type',
    'git-protocol', 'user-agent', 'x-http-method-override',
  ];
  const EXPOSED_RESPONSE_HEADERS = [
    'cache-control', 'content-encoding', 'content-length',
    'content-type', 'etag', 'x-github-request-id',
  ];

  const headers = new Headers();
  for (const h of ALLOWED_REQUEST_HEADERS) {
    const v = request.headers.get(h);
    if (v) headers.set(h, v);
  }
  headers.set('user-agent', request.headers.get('user-agent') ?? 'git/@isomorphic-git/cors-proxy');

  const upstream = await fetch(targetUrl, {
    method: request.method,
    headers,
    body: request.method !== 'GET' && request.method !== 'HEAD' ? request.body : undefined,
  });

  const responseHeaders = corsHeaders();
  responseHeaders.set('Access-Control-Expose-Headers', EXPOSED_RESPONSE_HEADERS.join(', '));
  for (const h of EXPOSED_RESPONSE_HEADERS) {
    const v = upstream.headers.get(h);
    if (v) responseHeaders.set(h, v);
  }

  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}

function corsHeaders() {
  return new Headers({
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PUT, PATCH, DELETE, OPTIONS, HEAD',
    'Access-Control-Allow-Headers': 'authorization, content-type, git-protocol, x-http-method-override',
    'Access-Control-Max-Age': '86400',
  });
}

// === CLIENT-SIDE GIT CLONE ===

import * as git from 'isomorphic-git';
import http from 'isomorphic-git/http/web';

interface CloneResult {
  workdir: string;
  files: Record<string, string>;
}

async function gitClone(repoUrl: string): Promise<CloneResult> {
  const fs = new LightningFS('git'); // in-memory FS
  const dir = '/repo';

  await git.clone({
    fs,
    http,
    dir,
    url: repoUrl,
    corsProxy: '/api/git-proxy', // your server-side proxy
    singleBranch: true,
    depth: 1, // shallow clone — faster, only latest commit
  });

  // Read all files into a flat map
  const files: Record<string, string> = {};
  const IGNORE = ['node_modules', '.git', 'package-lock.json', 'pnpm-lock.yaml'];
  await walkDir(fs, dir, '', files, IGNORE);

  return { workdir: dir, files };
}

async function walkDir(fs: any, base: string, rel: string, out: Record<string, string>, ignore: string[]) {
  const entries = await fs.promises.readdir(`${base}/${rel || ''}`);
  for (const entry of entries) {
    if (ignore.some(pattern => entry === pattern || entry.startsWith(pattern))) continue;
    const fullPath = `${base}/${rel ? rel + '/' : ''}${entry}`;
    const stat = await fs.promises.stat(fullPath);
    if (stat.isDirectory()) {
      await walkDir(fs, base, rel ? `${rel}/${entry}` : entry, out, ignore);
    } else {
      try {
        const bytes = await fs.promises.readFile(fullPath);
        const content = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
        out[rel ? `${rel}/${entry}` : entry] = content;
      } catch {
        // skip binary files
      }
    }
  }
}

// === PROJECT COMMAND DETECTION ===

function detectProjectCommands(files: Record<string, string>): CommandDescriptor[] {
  const commands: CommandDescriptor[] = [];
  if (files['package.json']) {
    const pkg = JSON.parse(files['package.json']);
    const scripts = pkg.scripts ?? {};
    // Always install first
    const packageManager = files['pnpm-lock.yaml'] ? 'pnpm' : files['yarn.lock'] ? 'yarn' : 'npm';
    commands.push({ type: 'shell', content: `${packageManager} install` });
    // Start the dev server
    const startScript = scripts.dev ?? scripts.start ?? scripts.serve;
    if (startScript) commands.push({ type: 'start', content: `${packageManager} run ${startScript === scripts.dev ? 'dev' : 'start'}` });
  }
  return commands;
}
```

## Data contracts

```typescript
// Files map (flat, path relative to project root)
type FileMap = Record<string, string>; // { "src/App.tsx": "import React..." }

// Import result for injecting into bolt chat
interface ImportedProject {
  name: string;          // derived from repo URL
  files: FileMap;
  commands: CommandDescriptor[];
}

interface CommandDescriptor {
  type: 'shell' | 'start';
  content: string; // e.g. "npm install", "npm run dev"
}
```

## Dependencies & assumptions

- `isomorphic-git` — `npm install isomorphic-git`
- `@isomorphic-git/lightning-fs` — in-memory FS implementation for browsers
- `isomorphic-git/http/web` — the browser HTTP transport for git
- Server route at `/api/git-proxy/*` (the CORS proxy above)
- Runs client-side only (use `ClientOnly` wrapper in React/Remix)

## To port this, you need:
- [ ] Add server route `/api/git-proxy/[...path]` that proxies to `https://{path}` with CORS headers
- [ ] Client: `npm install isomorphic-git @isomorphic-git/lightning-fs`
- [ ] Client: `git.clone()` using `corsProxy: '/api/git-proxy'` and `depth: 1` for speed
- [ ] Walk the cloned FS, skip `node_modules`/`.git`/lockfiles, skip binary files via `TextDecoder` with `fatal: true`
- [ ] Detect project commands from `package.json` scripts
- [ ] Inject cloned files into your app's file state (WebContainer or equivalent)

## Gotchas

- **Shallow clones only for large repos**: `depth: 1` fetches only the latest commit. Without it, large repos (especially with history) take 10-30 seconds to clone.
- **GitHub rate limits**: the CORS proxy is making requests from your server's IP. With many concurrent users, you'll hit GitHub's unauthenticated API limit (60 req/hr per IP). Pass `Authorization: token {github_token}` through the proxy for authenticated users (5000 req/hr).
- **Binary files crash TextDecoder with `fatal: true`**: that's intentional — catch the error and skip the file. Without `fatal: true`, corrupted UTF-8 silently produces garbage.
- **LightningFS is in-memory**: data doesn't persist across page reloads. For persistence, use IndexedDB backend: `new LightningFS('myfs', { wipe: false })`.
- **Private repos**: add `onAuth` callback to `git.clone()` that returns `{ username: '', password: githubToken }`.

## Origin (reference only)

- Repo: https://github.com/stackblitz-labs/bolt.diy
- `app/routes/api.git-proxy.$.ts` — CORS proxy
- `app/components/git/GitUrlImport.client.tsx` — client-side clone + import flow
- `app/lib/webcontainer/index.ts` — WebContainer FS where files land after clone
