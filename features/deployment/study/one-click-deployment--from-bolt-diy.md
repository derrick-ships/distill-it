# One-Click Deployment — from [bolt.diy](https://github.com/stackblitz-labs/bolt.diy)

> Domain: [[_domain]] · Source: https://github.com/stackblitz-labs/bolt.diy · NotebookLM:

## What it does

Bolt.diy can deploy your in-browser project to Vercel or Netlify in one click. You paste your API token in settings, hit "Deploy," and a few seconds later you get a live URL — without any CLI, without leaving the browser, without a local `git push`. The deployment routes detect your framework, create a project on the platform if needed, upload your files, and poll for completion.

## Why it exists

The target user built something in the browser sandbox and wants to show it to someone. Without one-click deploy, they'd have to: export the files, open a terminal, `git init`, push to a repo, connect to Netlify/Vercel, wait for CI, and get a URL. That's 10 steps. Bolt collapses it to 1. The value is purely in removing friction between "it works in preview" and "it's live on the internet."

## How it actually works

Both providers follow the same general flow, with minor differences:

**Vercel**: The server-side route receives the project files and a Vercel API token. It first tries to detect the framework by looking at `package.json` dependencies (React → `create-react-app`, Next.js deps → `nextjs`, Vue → `vue`, etc.) and then checks for config files (`next.config.js`, `vite.config.ts`). A new project is created via the Vercel v9 API with a name like `bolt-diy-{chatId}-{timestamp}`. Then files are posted to the v13 deployments API. Status is polled every 2 seconds for up to 2 minutes until state is `READY` or `ERROR`.

**Netlify**: Files are SHA-1 hashed and the digests are sent first to Netlify's deploy creation endpoint (Netlify's content-addressable protocol — it only requests files it doesn't already have). A new site is created if needed (`bolt-diy-{chatId}-{timestamp}`). Once the deploy is "prepared," each file is individually PUT to `api.netlify.com/api/v1/deploys/{id}/files/{path}` as `application/octet-stream`. Each upload retries up to 3 times with 2-second delays. Status is polled every 1 second for up to 60 seconds.

Both flows return: deploy ID, state, URL, and project/site metadata. The UI stores the site/project ID in the chat metadata (in IndexedDB) so subsequent deploys update the existing project rather than creating a new one.

## The non-obvious parts

- **Content-addressable Netlify protocol**: Netlify's API doesn't want you to upload files blindly. You first send SHA-1 hashes of all files, and Netlify replies with which hashes it doesn't have. You only upload the diff. This makes re-deploys of nearly-identical sites very fast.
- **Framework detection drives build config**: for Vercel, the detected framework changes which build command and output directory are sent. A React app gets `npm run build` + `build/`; a Next.js app gets different settings. Getting this wrong produces a failed deployment.
- **Source vs. output files**: for static sites (detected by framework), Netlify receives the raw project files and Netlify builds them on their side. For projects that already have a `dist/` or `build/` folder in the WebContainer, it can upload build output directly instead.
- **ChatId in project names**: naming projects `bolt-diy-{chatId}-{timestamp}` creates a 1:1 mapping from bolt chat session to deploy project. Subsequent deploys from the same chat update the same Netlify/Vercel project.
- **Token storage**: tokens are stored in the browser (`localStorage` or settings store), not server-side. Each deploy request includes the token in the POST body.

## Related
- [[webcontainer-runtime--from-bolt-diy]] (produces the files and build output that this feature deploys)
- [[chat-persistence--from-bolt-diy]] (stores deploy metadata in chat records)
- [[browser-git--from-bolt-diy]] (alternative deployment mechanism via git push)
