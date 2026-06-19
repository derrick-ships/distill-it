# WebContainer Runtime — from [bolt.diy](https://github.com/stackblitz-labs/bolt.diy)

> Domain: [[_domain]] · Source: https://github.com/stackblitz-labs/bolt.diy · NotebookLM:

## What it does

Bolt.diy runs an entire Node.js server — including `npm install`, file writing, and live HTTP previews — inside your browser tab. No cloud VM, no remote shell. The app in the preview pane is genuinely running locally in the browser sandbox. You can open a terminal, type `npm run dev`, and see the Vite dev server start up, all within the browser window.

## Why it exists

The core value proposition of bolt.diy (and the original bolt.new) is zero-friction prototyping: you describe an app, and 30 seconds later you're looking at a running application you can interact with, without installing anything or waiting for a cloud container to spin up. WebContainer makes this possible by providing a full POSIX-compatible runtime inside a browser tab.

## How it actually works

WebContainer is a proprietary API by StackBlitz (`@webcontainer/api`). Bolt boots it once on the client side using `WebContainer.boot()` with specific configuration:
- `coep: 'credentialless'` — required by the browser's cross-origin isolation policy for SharedArrayBuffer (which WebContainer needs for its worker thread model)
- `workdirName` — the virtual filesystem root where all project files live
- `forwardPreviewErrors: true` — makes runtime JS errors in the preview appear in bolt's UI

After booting, the workbench can write files directly to the WebContainer's filesystem. When the AI generates file changes (wrapped in `<boltAction type="file">` tags), the workbench store executes these writes via WebContainer's `fs.writeFile()` API. Shell commands (`<boltAction type="shell">`) spawn processes using WebContainer's `spawn()` method, which behaves like a real terminal.

The preview panel points at a URL that WebContainer exposes: `localhost:PORT` within the container's network. Bolt maps this to a special internal URL served from the browser's service worker. The `webcontainer.preview.$id.tsx` route handles preview isolation.

Bolt also installs a custom inspector script into the preview to capture uncaught exceptions and unhandled rejections. When an error occurs, it's posted back to the main thread and displayed in the workbench as an actionable error card.

The integration persists across Vite HMR (hot reloads) by checking `import.meta.hot.data` for an existing WebContainer instance before calling `boot()` again. Only one instance can exist per browser tab.

## The non-obvious parts

- **Cross-origin isolation is mandatory**: the server must send `Cross-Origin-Embedder-Policy: credentialless` and `Cross-Origin-Opener-Policy: same-origin` headers. Without these, WebContainer simply won't boot.
- **One instance per tab**: calling `WebContainer.boot()` twice crashes with an error. The HMR persistence trick is load-bearing.
- **File sync to local disk**: bolt optionally uses the File System Access API (`window.showDirectoryPicker`) to sync the virtual FS to a real local directory. This is separate from WebContainer — it's browser-native.
- **The terminal is xterm.js**: the shell UI is an xterm.js terminal wired to WebContainer's spawn() output stream. It's not simulated — it's a real PTY inside the container.
- **Static site vs. server deploys**: when deploying, bolt checks which files to export. WebContainer produces real build artifacts (`dist/`, `out/`) that can be zipped and sent to Netlify or Vercel directly.

## Related
- [[artifact-code-generation--from-bolt-diy]] (generates the files this runtime executes)
- [[one-click-deployment--from-bolt-diy]] (takes the runtime's build output and pushes to hosting)
- [[chat-persistence--from-bolt-diy]] (snapshots save the runtime's file state to IndexedDB)
