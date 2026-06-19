# WebContainer Runtime (build spec) — distilled from bolt.diy

## Summary

Integrate StackBlitz WebContainer into a browser app to execute real Node.js projects in-browser: write files, run npm/node processes, and serve live HTTP previews — all without a backend VM.

## Core logic (inlined)

```typescript
import { WebContainer } from '@webcontainer/api';

// Boot once per tab (survive HMR)
let webcontainerInstance: WebContainer | null = null;

async function getWebContainer(): Promise<WebContainer> {
  if (webcontainerInstance) return webcontainerInstance;
  // Check if HMR preserved a previous instance
  if (import.meta.hot?.data.webcontainer) {
    webcontainerInstance = import.meta.hot.data.webcontainer;
    return webcontainerInstance!;
  }
  webcontainerInstance = await WebContainer.boot({
    coep: 'credentialless',
    workdirName: 'project',
    forwardPreviewErrors: true,
  });
  if (import.meta.hot) {
    import.meta.hot.data.webcontainer = webcontainerInstance;
  }
  return webcontainerInstance;
}

// Write files from AI output
async function writeFiles(files: Record<string, string>) {
  const wc = await getWebContainer();
  for (const [path, content] of Object.entries(files)) {
    await wc.fs.writeFile(path, content, 'utf-8');
  }
}

// Run a shell command (npm install, npm run dev, etc.)
async function runCommand(command: string, args: string[]): Promise<number> {
  const wc = await getWebContainer();
  const process = await wc.spawn(command, args);
  // Wire to xterm.js terminal
  process.output.pipeTo(new WritableStream({ write(data) { terminal.write(data); } }));
  return process.exit;
}

// Get the preview URL for a given port
async function getPreviewUrl(port: number): Promise<string> {
  const wc = await getWebContainer();
  return wc.on('server-ready', (p, url) => {
    if (p === port) return url;
  });
}
```

## Required server headers

```
Cross-Origin-Embedder-Policy: credentialless
Cross-Origin-Opener-Policy: same-origin
```

Without these, `WebContainer.boot()` throws immediately. Configure in Vite devServer or Cloudflare Headers.

## Data contracts

```typescript
// WebContainer.boot() options
interface BootOptions {
  coep: 'credentialless' | 'require-corp';
  workdirName?: string;
  forwardPreviewErrors?: boolean;
}

// File system tree for bulk write (initial project setup)
type FileSystemTree = {
  [name: string]: FileNode | DirectoryNode;
};
interface FileNode { file: { contents: string | Uint8Array } }
interface DirectoryNode { directory: FileSystemTree }

// Mount all at once (faster than writeFile loop for initial setup)
await wc.mount(fileSystemTree);
```

## Dependencies & assumptions

- `@webcontainer/api` — StackBlitz proprietary package, free for public projects
- Requires a browser with `SharedArrayBuffer` support (Chrome 92+, Firefox 79+, Safari 15.2+)
- Must serve the page with the two COEP/COOP headers above
- `xterm` and `@xterm/addon-fit` for the terminal UI
- The preview renders in an `<iframe>` pointing at the WebContainer-provided URL

## To port this, you need:
- [ ] Install `@webcontainer/api` (`npm i @webcontainer/api`)
- [ ] Add COEP + COOP headers to your dev and production server configs
- [ ] Create a singleton boot function that checks `import.meta.hot?.data` before calling `boot()`
- [ ] Wire `wc.fs.writeFile()` to wherever your app generates file content
- [ ] Wire `wc.spawn()` output to an xterm.js terminal component
- [ ] Mount an `<iframe>` that loads the URL from the `server-ready` event
- [ ] Install an inspector script (`wc.on('preview-message', ...)`) to catch runtime errors

## Gotchas

- **Only one instance per tab**: calling `boot()` twice throws. The HMR singleton pattern is mandatory in Vite/Remix apps.
- **Binary files**: write as `Uint8Array`, not strings. Text files as strings are fine.
- **npm install is slow on first run**: the container downloads npm packages from a CDN on first use. Cache the lockfile and use `--frozen-lockfile` to speed subsequent installs.
- **WebContainer is not available in Node.js**: it's purely browser-side. Your server code cannot touch it.
- **Preview URL changes**: the container assigns a fresh origin each boot. Don't hardcode preview URLs.
- **Cloudflare Pages**: you must set COEP/COOP in `_headers` file or the Pages config — not in `wrangler.toml`.

## Origin (reference only)

- Repo: https://github.com/stackblitz-labs/bolt.diy
- `app/lib/webcontainer/index.ts` — boot + HMR singleton
- `app/components/workbench/Workbench.client.tsx` — file sync, terminal toggle, preview panels
- `app/routes/webcontainer.preview.$id.tsx` — preview URL routing
