# Browser Git (isomorphic-git + CORS proxy) — from [bolt.diy](https://github.com/stackblitz-labs/bolt.diy)

> Domain: [[_domain]] · Source: https://github.com/stackblitz-labs/bolt.diy · NotebookLM:

## What it does

Bolt.diy lets you paste a GitHub URL and import the entire repository — files cloned directly into the browser's in-memory filesystem, no local git needed. You can then edit the code with AI assistance, run it, and deploy. The project also supports pushing changes back to a git remote, all from within the browser tab.

## Why it exists

Developers often want to start an AI conversation about an existing codebase. Without git-in-browser, they'd have to: find the repo locally, export specific files, paste them into the chat. Bolt sidesteps this entirely by cloning the repo into the browser sandbox, giving the AI full access to the codebase as if it had been built there. This is the "load existing project" feature.

## How it actually works

**isomorphic-git**: All git operations (clone, fetch, push) use the `isomorphic-git` library, which is a pure JavaScript implementation of git that runs in both Node.js and browsers. In bolt.diy, it runs client-side inside the browser.

**CORS proxy**: GitHub's git endpoints don't send CORS headers, so direct `fetch()` calls to `github.com` from a browser are blocked. Bolt solves this with a server-side CORS proxy (the `api.git-proxy.$.ts` Remix route). This proxy:
- Accepts a request like `GET /api/git-proxy/github.com/stackblitz-labs/bolt.diy/info/refs?service=git-upload-pack`
- Extracts the target domain from the URL path
- Forwards the request to `github.com` with appropriate git headers
- Returns the response with `Access-Control-Allow-Origin: *` added
- Supports all HTTP methods including OPTIONS (preflight), POST (push), and GET (clone/fetch)

**Import flow**: When a user pastes a GitHub URL, `gitClone()` calls isomorphic-git's `clone()` with the proxy URL as the git HTTP endpoint. After cloning, bolt:
1. Reads all files from the cloned directory
2. Filters out `node_modules/`, `.git/`, lockfiles
3. Decodes binary files and excludes them (only text files)
4. Calls `detectProjectCommands()` on `package.json` to find setup scripts
5. Creates two messages: an assistant message with all files as a `boltArtifact` structure, and a user message saying "set up and run this project"
6. Imports them as the chat history — the project appears as if the AI had just created it

## The non-obvious parts

- **isomorphic-git writes to a virtual FS**: in bolt, the cloned files land in an in-memory object, not the WebContainer filesystem. They're read, filtered, and then re-written to WebContainer separately.
- **Binary file exclusion**: `TextDecoder` is used to attempt to decode file contents. If decoding fails or produces non-text output, the file is excluded. This prevents binary files (images, fonts) from being pasted as garbled text into the AI context.
- **The CORS proxy user-agent**: the proxy sends `User-Agent: git/@isomorphic-git/cors-proxy` to look like a legitimate git client to GitHub's servers. GitHub's rate limits apply to this user-agent.
- **ClientOnly rendering**: the `GitUrlImport` component is wrapped in a `ClientOnly` wrapper — it never renders server-side because isomorphic-git uses browser APIs.
- **`detectProjectCommands()`**: this helper reads `package.json` scripts and figures out which commands to run (install dependencies, start the dev server). It returns structured command descriptors that become the initial message to the AI.

## Related
- [[webcontainer-runtime--from-bolt-diy]] (cloned files end up in WebContainer's filesystem)
- [[artifact-code-generation--from-bolt-diy]] (imported git repos are presented as bolt artifacts for the AI to work on)
- [[one-click-deployment--from-bolt-diy]] (deployment can push back to git remotes)
