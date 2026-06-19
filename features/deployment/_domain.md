# Domain: deployment

Patterns for deploying locally-built, in-browser, or AI-generated apps to cloud hosting providers — including token validation, framework auto-detection, file upload, environment variable pre-configuration, and deployment status polling.

## What this domain is about

When a builder tool (AI-powered or otherwise) creates apps locally or in-browser, deployment is the last mile: getting the working code to a URL someone else can visit. This domain covers the integration between the local/browser build environment and cloud platforms (Vercel, Netlify, Fly.io, Railway, etc.) — with emphasis on the automation that makes deployment feel like a button rather than a workflow.

## Core patterns

- **Token validation on save:** Validate API/access tokens against the provider's user endpoint immediately on entry — don't let users discover bad tokens at deploy time.
- **Framework detection before project create:** Inspect config files and `package.json` deps to determine the framework before calling the hosting API. Config files take precedence over deps.
- **Env vars before first build:** Set database URLs, API keys, and other env vars *before* triggering the initial deployment — builds that need a DB at startup will fail if vars arrive after.
- **Polling, not webhooks:** Tools that can't receive webhooks (no public ingress) use polling against the deployment status/list endpoint to detect when a build completes.
- **Store deployment URL in local DB:** Once a production deployment succeeds, store the live URL locally so the builder UI can surface it without hitting the hosting API every time.
- **Content-addressable uploads:** Platforms like Netlify use SHA-1 hashing to avoid re-uploading unchanged files — send hashes first, only upload the diff.
- **Encrypted local token storage:** Hosting tokens are secrets. Use OS keychain (Electron safeStorage, libsecret, DPAPI) for desktop apps, or encrypted cookies for browser apps — never plaintext.

## Features in this domain

- [[cloud-deploy--from-dyad]] — Vercel deployment from a local Electron app builder: token validation, framework detection, project creation, env var sync, deployment polling
- [[one-click-deployment--from-bolt-diy]] — Vercel + Netlify deployment from an in-browser IDE: SHA-1 content-addressable Netlify protocol, framework detection, status polling, project ID caching

## Repos studied
- dyad — Electron-based local AI app builder
- bolt.diy — In-browser AI IDE, Vercel + Netlify one-click deploy

## Related domains
- [[runtime]] — the runtime produces build artifacts that deployment pushes
- [[git]] — some deploy flows use git push as the deploy mechanism
