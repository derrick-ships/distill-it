# Multi-Studio Shell Architecture (build spec) — distilled from open-generative-ai

## Summary
A single thin "shell" component hosts ~12 interchangeable feature modules ("studios": Image, Video, LipSync, Cinema, Workflow, Audio, Clipping, VibeMotion, Marketing, Agent, DesignAgent, Apps, McpCli). All studios live in one shared library (`packages/studio`) that is re-exported from a single barrel `index.js` and consumed *unchanged* by both the web app (Next.js) and the desktop app (Electron). The shell owns the cross-cutting concerns once — API-key/auth state, the key modal, balance polling, drag-and-drop file handoff — and renders the active studio by a `TABS`-driven switch. Adding a feature = export a studio + add a tab. This is the "thin shell + interchangeable modules + shared lib across targets" pattern.

## Core logic (inlined)

**1) One barrel exports every studio and the whole API layer**, so both apps import from a single package:

```javascript
// packages/studio/src/index.js
"use client";
export { default as ImageStudio }       from './components/ImageStudio';
export { default as VideoStudio }       from './components/VideoStudio';
export { default as LipSyncStudio }     from './components/LipSyncStudio';
export { default as CinemaStudio }      from './components/CinemaStudio';
export { default as WorkflowStudio }    from './components/WorkflowStudio';
export { default as AudioStudio }       from './components/AudioStudio';
export { default as ClippingStudio }    from './components/ClippingStudio';
export { default as VibeMotionStudio }  from './components/VibeMotionStudio';
export { default as MarketingStudio }   from './components/MarketingStudio';
export { default as AgentStudio }       from './components/AgentStudio';
export { default as DesignAgentStudio } from './components/DesignAgentStudio';
export { default as AppsStudio }        from './components/AppsStudio';
export { default as McpCliStudio }      from './components/McpCliStudio';
export * from './muapi';   // the entire API layer rides along
```

**2) The shell** is a tab switcher that owns shared state and gates the whole app on having a key:

```javascript
"use client";
import { useState, useEffect, useCallback } from 'react';
import { ImageStudio, VideoStudio, /* ... */ getUserBalance } from 'studio';
import ApiKeyModal from './ApiKeyModal';

const STORAGE_KEY = 'muapi_key';
const TABS = [
  { id: 'image',    label: 'Image Studio'  },
  { id: 'video',    label: 'Video Studio'  },
  { id: 'lipsync',  label: 'Lip Sync'      },
  // ...one entry per studio
];

export default function StandaloneShell() {
  const [apiKey, setApiKey]   = useState(null);
  const [activeTab, setTab]   = useState('image');
  const [balance, setBalance] = useState(null);
  const [droppedFiles, setDroppedFiles] = useState(null);

  const fetchBalance = useCallback(async (key) => {
    try { setBalance(await getUserBalance(key)); } catch { /* ignore */ }
  }, []);

  // load key on mount; keep cookie in sync (the server proxy reads the cookie)
  useEffect(() => {
    const k = localStorage.getItem(STORAGE_KEY);
    if (k) { setApiKey(k); fetchBalance(k); document.cookie = `muapi_key=${k}; path=/; max-age=31536000; SameSite=Lax`; }
  }, [fetchBalance]);

  // auth bridge: any 401/403 anywhere drops the key → modal re-renders (see credential-management doc)
  useEffect(() => {
    const onAuth = () => setApiKey(null);
    window.addEventListener('muapi:auth-required', onAuth);
    return () => window.removeEventListener('muapi:auth-required', onAuth);
  }, []);

  // refresh balance periodically while authed
  useEffect(() => {
    if (!apiKey) return;
    const t = setInterval(() => fetchBalance(apiKey), 30000);
    return () => clearInterval(t);
  }, [apiKey, fetchBalance]);

  const handleKeySave = useCallback((key) => {
    localStorage.setItem(STORAGE_KEY, key);
    setApiKey(key);
    fetchBalance(key);
    document.cookie = `muapi_key=${key}; path=/; max-age=31536000; SameSite=Lax`;
  }, [fetchBalance]);

  if (!apiKey) return <ApiKeyModal onSave={handleKeySave} />;   // hard gate: no key, no app

  return (
    <div onDrop={e => setDroppedFiles(e.dataTransfer.files)} onDragOver={e => e.preventDefault()}>
      <nav>
        {TABS.map(t => (
          <button key={t.id} className={activeTab === t.id ? 'active' : ''} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>
      {activeTab === 'image'   && <ImageStudio   apiKey={apiKey} droppedFiles={droppedFiles} />}
      {activeTab === 'video'   && <VideoStudio   apiKey={apiKey} droppedFiles={droppedFiles} />}
      {activeTab === 'lipsync' && <LipSyncStudio apiKey={apiKey} droppedFiles={droppedFiles} />}
      {/* ...one line per studio, all receiving the same shared props */}
    </div>
  );
}
```

**3) Routing is trivial** because the shell does the work — the Next.js route is a one-liner, and the same shell is what the Electron renderer mounts:

```javascript
// app/studio/[[...slug]]/page.js  (web)
import StandaloneShell from '@/components/StandaloneShell';
export const metadata = { title: 'Studio — Open Generative AI' };
export default function StudioPage() { return <StandaloneShell />; }
```

```javascript
// app/layout.js — deliberately bare: just fonts + <body>{children}</body>, no providers.
// All app state lives in the shell, not in a global provider tree.
```

**4) Each studio is self-similar**: it receives `{ apiKey, droppedFiles }`, reads the model registry to build its form (see model-registry doc), and calls a `generate*` function (see submit-and-poll doc) to do work. The studios share UX by sharing the registry + API layer, not by inheritance.

## Data contracts
- **Studio component props (uniform)**: `{ apiKey: string, droppedFiles?: FileList }`. Every studio takes the same handful, so the shell can mount any of them identically.
- **`TABS`**: `Array<{ id: string, label: string }>` — id maps 1:1 to a studio in the switch; label is the nav text.
- **Shared shell state**: `apiKey` (gates everything), `activeTab`, `balance` (polled every 30s), `droppedFiles` (drag-drop handoff to the active studio).
- **Auth coupling**: listens for `window` `'muapi:auth-required'` → `setApiKey(null)` → `ApiKeyModal` renders.
- **Key persistence**: `localStorage['muapi_key']` + cookie `muapi_key` (server proxy reads the cookie).

## Dependencies & assumptions
- React (hooks). The barrel uses Next's `"use client"` but the pattern is framework-agnostic.
- A monorepo/workspace so one library (`packages/studio`) is a dependency of multiple apps (web + Electron). Here: npm workspaces, package name `studio`.
- Assumes studios are independent and uniform enough to share one prop shape and one mounting switch.

## To port this, you need:
- [ ] A shared component library with a single barrel that re-exports every feature module + the API layer.
- [ ] A thin shell that: holds cross-cutting state (auth/key/balance), gates the app on auth, drives a tab/route switch, and passes a uniform prop set to whichever module is active.
- [ ] A uniform feature-module contract (same props in, registry + API layer used the same way) so the shell stays generic.
- [ ] A trivial route/entry that just renders the shell — keep the framework layout bare and put state in the shell (or a provider) so multiple targets can reuse it.
- [ ] A workspace setup if you want the same library consumed by more than one app.

## Gotchas
- **Conditional mounting (`activeTab === x && <X/>`) unmounts inactive studios.** Switching tabs loses a studio's in-progress local state unless it's lifted up or persisted. If a long generation must survive tab switches, hoist that state to the shell (or keep studios mounted and toggle visibility with CSS).
- **All state in the shell, no provider tree.** Simple and explicit, but every cross-cutting concern that grows (history, theme, multiple keys) lands in one component. Watch for the shell becoming a god-component; introduce context/providers before it sprawls.
- **Uniform props are a contract, not a coincidence.** The shell only stays a clean switch if every studio really does accept `{ apiKey, droppedFiles }`. A studio that needs something special tempts you to special-case the switch — resist; pass it via the registry or a context instead.
- **The auth gate is binary.** `if (!apiKey) return <ApiKeyModal/>` replaces the *entire* app with the modal. Good for BYOK onboarding; if you later need a public/anonymous mode, this gate must change.
- **One barrel = one bundle pressure point.** Re-exporting 12 studios from `index.js` can defeat tree-shaking and bloat the initial load. Use dynamic `import()` per studio (lazy-mount on tab activation) if startup size matters.
- **`"use client"` on the barrel** forces everything it exports to the client. Intentional here (it's an SPA-in-Next), but it means none of these studios can be server components.

## Origin (reference only)
`Anil-matcha/Open-Generative-AI` — `packages/studio/src/index.js` (barrel re-exporting all studios + `export * from './muapi'`); `components/StandaloneShell.js` (`TABS`, tab switch, `apiKey`/`balance`/`droppedFiles` state, `handleKeySave`, auth-event listener, balance polling); `app/studio/[[...slug]]/page.js` (renders the shell); `app/layout.js` (bare layout). Studios consume `models.js` (forms) and `muapi.js` (`generate*`).
