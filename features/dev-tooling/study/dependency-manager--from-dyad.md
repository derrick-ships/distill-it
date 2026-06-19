# Dependency Manager — from [dyad](https://github.com/dyad-sh/dyad)

> Domain: [[_domain]] · Source: https://github.com/dyad-sh/dyad · NotebookLM: 

## What it does

When the AI generates code that imports a package that isn't installed yet, Dyad automatically installs it. The AI emits a special XML tag `<dyad-add-dependency packages="react-query framer-motion">` and Dyad's dependency manager intercepts it, validates the package names, picks the right package manager (npm or pnpm), runs the install, and replaces the XML tag with a success/failure report back into the chat history.

## Why it exists

Without this, AI-generated code frequently fails to run because the AI confidently uses packages it doesn't know are installed. The developer would need to manually read the AI output, find the import, then switch to a terminal and run npm install. Dyad closes this loop automatically so the generated app is runnable immediately after the AI's turn.

## How it actually works

**XML tag protocol:** The system prompt instructs the LLM to emit `<dyad-add-dependency packages="pkg1 pkg2">` when it uses packages that might not be installed. During stream post-processing, `executeAddDependency()` scans the assistant's message for these tags.

**Validation:** Each package name is checked against the regex `^(@[a-z0-9-_.]+\/)?[a-z0-9-_.]+$` — this matches both scoped (`@org/pkg`) and unscoped (`react-query`) npm packages. Any name that fails this check is rejected and not installed, with an error written back to the tag's replacement.

**Package manager selection:** The handler checks if pnpm is available in the app's environment. If so, it runs `pnpm add`. Otherwise it falls back to `npm install`. This respects whatever the generated project was set up with.

**Socket Firewall:** If the `blockUnsafeNpmPackages` feature flag is enabled, Dyad routes the install through Socket.dev's firewall tool (if installed). Socket checks packages for known malware, supply-chain attacks, and suspicious patterns before the install proceeds. This is an optional safety layer for security-conscious users.

**Result injection:** After the install completes (with a configurable timeout), the `<dyad-add-dependency>` tag in the stored message is replaced with one of:
- `<dyad-add-dependency-result status="success">` with the list of installed packages
- `<dyad-add-dependency-result status="error">` with the error message

This replacement happens in both the in-memory response and the persisted DB record, so the chat history accurately reflects what was installed.

**Timeout handling:** npm/pnpm installs can hang if the registry is unreachable. The handler enforces a timeout and kills the process if it exceeds it, then writes an error result tag.

## The non-obvious parts

- **The AI doesn't know if packages are installed:** The LLM emits the `<dyad-add-dependency>` tag based on its training knowledge of what packages are typically needed — not based on inspecting `package.json`. Dyad checks `package.json` first and skips install if the package is already there.
- **Tag replacement is in the DB, not just in-flight:** The persisted `messages.content` column gets the `<dyad-add-dependency-result>` substituted in. This means the chat history always shows what happened, not the raw LLM output — useful for debugging.
- **Socket Firewall is optional:** Most users don't have it. When absent, the flag is a no-op. The install proceeds normally. Dyad chose not to block installs when Socket isn't present — convenience over security by default.
- **pnpm preferred over npm:** The detection logic prefers pnpm when available because pnpm's lockfile is more deterministic and its install is faster. But many generated apps use npm/npx in their scaffolding, so npm is the safe fallback.

## Related
- [[ai-chat-stream--from-dyad]] (XML tags parsed from the stream)
- [[code-explorer--from-dyad]] (TypeScript install enables semantic indexing)
