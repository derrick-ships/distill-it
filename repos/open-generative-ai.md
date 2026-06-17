# open-generative-ai

- **Source:** https://github.com/Anil-matcha/Open-Generative-AI
- **Product:** Self-hosted, open-source studio for AI image & video generation — a free alternative to commercial AI video platforms. A thin multi-model front-end over the Muapi.ai gateway (200+ models: Flux, Kling, Sora, Veo, etc.), with ~12 "studios," plus local-inference fallbacks (sd.cpp / Wan2GP). Ships as both a web app and an Electron desktop app.
- **Stack:** JavaScript · Next.js 15 (App Router) · React 19 · Tailwind CSS 3 · axios · Electron 33 · Vite · npm workspaces (monorepo)
- **Gateway:** Muapi.ai (`api.muapi.ai`), auth via `x-api-key` (bring-your-own-key)
- **Date distilled:** 2026-06-17

## Architecture in one breath
Almost all the real engineering is in two files inside one shared package, `packages/studio`. `muapi.js` is a universal submit→poll client: every generation (image/video/i2v/lipsync/audio) posts a job, gets a `request_id`, and polls `/predictions/{id}/result` every 2s until done. `models.js` is a declarative registry of 200+ models (id, endpoint, parameter schema) that drives both the API routing and the auto-built UI. A thin `StandaloneShell` hosts ~12 interchangeable studios behind tabs, owns the API-key/auth/balance state, and is reused unchanged by both the web and Electron builds. A same-origin Next.js catch-all proxy forwards browser calls to the gateway (injecting the key, handling CORS), while Electron/SSR calls the gateway directly via a base-URL switch.

## Features distilled

| Feature | Domain | Study | Build |
|---|---|---|---|
| Submit-and-Poll Generation Client | ai-integration | [study](../features/ai-integration/study/submit-and-poll-generation-client--from-open-generative-ai.md) | [build](../features/ai-integration/build/submit-and-poll-generation-client--from-open-generative-ai.md) |
| Centralized Model Registry | ai-integration | [study](../features/ai-integration/study/centralized-model-registry--from-open-generative-ai.md) | [build](../features/ai-integration/build/centralized-model-registry--from-open-generative-ai.md) |
| Browser→Host API Proxy + Auth Bridge | credential-management | [study](../features/credential-management/study/browser-host-api-proxy--from-open-generative-ai.md) | [build](../features/credential-management/build/browser-host-api-proxy--from-open-generative-ai.md) |
| Multi-Studio Shell Architecture | ui-architecture | [study](../features/ui-architecture/study/multi-studio-shell-architecture--from-open-generative-ai.md) | [build](../features/ui-architecture/build/multi-studio-shell-architecture--from-open-generative-ai.md) |

## Source files (reference only — repo may be gone later)
- `packages/studio/src/muapi.js` — submit/poll primitive (`submitAndPoll`, `pollForResult`), all `generate*/process*` wrappers, `uploadFile`, the `BASE_URL` env switch, the proxy (`handleProxyRequest`, `handleServerSideProxy`), `notifyAuthRequired`, balance/cost helpers.
- `packages/studio/src/models.js` — the 200+ model registry (`t2iModels`, `i2iModels`, `t2vModels`, …), `getModelById`, `getVideoModelById`.
- `packages/studio/src/index.js` — barrel re-exporting all studios + `export * from './muapi'`.
- `components/StandaloneShell.js` — the shell: `TABS`, tab switch, key/auth/balance state, `handleKeySave`, auth-event listener.
- `components/ApiKeyModal.js` — API-key entry UI.
- `app/api/**/[[...path]]/route.js` — catch-all proxy routes (read `muapi_key` cookie, delegate to `handleServerSideProxy`).
- `app/studio/[[...slug]]/page.js`, `app/layout.js` — trivial route + bare layout (state lives in the shell).
