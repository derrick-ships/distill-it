# Cloud Deploy — from [dyad](https://github.com/dyad-sh/dyad)

> Domain: [[_domain]] · Source: https://github.com/dyad-sh/dyad · NotebookLM: 

## What it does

Dyad lets you deploy your locally-built app to Vercel with one click from within the builder. You authenticate with a Vercel token, Dyad detects your app's framework (Next.js, Vite, Nuxt, etc.), creates the Vercel project, pushes an initial deployment, and then tracks deployment status. Supabase and Neon database connections are also pre-configured as environment variables before the build runs.

## Why it exists

The local-first pitch is "build privately on your machine." But most apps need to be shared or run in production. Cloud deploy closes the loop: build locally, share via Vercel URL. Without this, users would need to manually set up Vercel, configure environment variables, and figure out the framework settings — a 20-minute process that Dyad collapses to a token paste and a button click.

## How it actually works

**Token save & validation:** `handleSaveVercelToken` saves the token to settings (encrypted via safeStorage) then immediately validates it by hitting Vercel's `/v2/user` API endpoint. If the call fails, the token is rejected before it's persisted.

**Framework detection:** `detectFramework()` inspects the app's root directory in order:
1. Looks for config files: `next.config.js/ts/mjs`, `vite.config.ts/js`, `astro.config.mjs`, `nuxt.config.ts`, `svelte.config.js`, `remix.config.js`, `angular.json`, `gatsby-config.js`
2. If no config file found, reads `package.json` dependencies and checks for Next.js, Vite, Nuxt, Angular, React, Vue, Gatsby, Remix — in that priority order
3. Returns a Vercel framework identifier string (e.g. `"nextjs"`, `"vite"`)

**Project creation:** `handleCreateProject` calls Vercel's project creation API with the detected framework, then:
1. Stores the returned `vercelProjectId`, `vercelProjectName`, and `vercelTeamId` in the local SQLite apps table
2. If Neon database is connected, pushes the `DATABASE_URL` environment variable to Vercel before the first deploy
3. Triggers the initial deployment

**Deployment tracking:** `handleGetVercelDeployments` fetches the last 5 deployments from Vercel's API. When a production deployment succeeds, Dyad updates the stored `deploymentUrl` in the app record so the builder UI can show a direct "Open live app" link.

**Connect to existing:** `handleConnectToExistingProject` lets users link a Dyad app to an already-existing Vercel project (e.g. if they set it up externally). Same DB update, no new project created.

**Neon sync:** Before initial deployment, Dyad calls the Neon handlers to retrieve the database connection string and sets it as a Vercel environment variable. This ensures the deployed app can connect to Neon without manual configuration.

## The non-obvious parts

- **Framework detection runs locally, not on Vercel:** Dyad determines the framework before making any Vercel API call. This lets it set the right build settings upfront. Vercel's own auto-detection would also run, but Dyad's pre-detection ensures the correct framework ID is sent and avoids Vercel guessing wrong.
- **Encrypted token storage:** The Vercel token is stored via Electron's `safeStorage` API (OS-level keychain on macOS/Windows). It's never logged or shown after initial save.
- **Last 5 deployments only:** The polling doesn't watch deployments in real time. Users need to manually refresh (or the UI auto-polls). This is a simplification — Vercel webhooks would be better but require a public endpoint, which a local-first desktop app doesn't have.
- **Team vs. personal accounts:** `vercelTeamId` is stored and sent with all API calls. If null, the project is under the user's personal account. Dyad handles both but doesn't let users switch teams post-creation.

## Related
- [[byok-settings--from-dyad]] (Vercel token stored alongside other API keys)
- [[multi-app-library--from-dyad]] (deployment URL surfaces in the app library card)
