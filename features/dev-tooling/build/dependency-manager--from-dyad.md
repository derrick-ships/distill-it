# Dependency Manager (build spec) — distilled from dyad

## Summary

Build an automatic npm dependency installer triggered by AI-emitted XML tags in a chat stream. The LLM signals which packages it used with `<dyad-add-dependency packages="...">` tags; the handler validates package names, selects npm or pnpm, optionally runs a security firewall, executes the install, and replaces the tag in the stored message with a result tag showing success or failure.

## Core logic (inlined)

```typescript
// --- VALIDATION ---
const VALID_NPM_PACKAGE = /^(@[a-z0-9-_.]+\/)?[a-z0-9-_.]+(@[\w.*-]+)?$/

function validatePackageName(name: string): boolean {
  return VALID_NPM_PACKAGE.test(name)
}

// --- PACKAGE MANAGER DETECTION ---
async function detectPackageManager(appPath: string): Promise<'pnpm' | 'npm'> {
  // Prefer pnpm if lockfile exists
  if (fs.existsSync(path.join(appPath, 'pnpm-lock.yaml'))) return 'pnpm'
  // Or if pnpm binary is available
  try {
    await execAsync('pnpm --version', { timeout: 3000 })
    return 'pnpm'
  } catch {
    return 'npm'
  }
}

// --- INSTALL ---
async function installPackages(
  packages: string[],
  appPath: string,
  options: { useSocketFirewall?: boolean; timeout?: number } = {}
): Promise<{ installed: string[]; failed: { name: string; error: string }[] }> {
  const valid = packages.filter(validatePackageName)
  const invalid = packages.filter(p => !validatePackageName(p))
  
  if (valid.length === 0) {
    return { installed: [], failed: invalid.map(p => ({ name: p, error: 'invalid package name' })) }
  }

  const pm = await detectPackageManager(appPath)
  const cmd = pm === 'pnpm' ? 'pnpm add' : 'npm install'
  
  // Optionally prefix with Socket Firewall
  const fullCmd = options.useSocketFirewall && await isSocketAvailable()
    ? `npx socket ${cmd} ${valid.join(' ')}`
    : `${cmd} ${valid.join(' ')}`
  
  try {
    await execAsync(fullCmd, {
      cwd: appPath,
      timeout: options.timeout ?? 120_000 // 2 min default
    })
    return { installed: valid, failed: invalid.map(p => ({ name: p, error: 'invalid package name' })) }
  } catch (err) {
    return {
      installed: [],
      failed: valid.map(p => ({ name: p, error: String(err) }))
    }
  }
}

// --- TAG REPLACEMENT ---
async function executeAddDependency(
  messageContent: string,
  appPath: string,
  messageId: number,
  db: Database
): Promise<string> {
  let result = messageContent
  
  const tagPattern = /<dyad-add-dependency packages="([^"]+)">/g
  let match: RegExpExecArray | null
  
  while ((match = tagPattern.exec(messageContent)) !== null) {
    const [fullTag, packagesStr] = match
    const packages = packagesStr.split(/\s+/).filter(Boolean)
    
    // Check if already installed
    const alreadyInstalled = packages.filter(p => isInPackageJson(p, appPath))
    const toInstall = packages.filter(p => !isInPackageJson(p, appPath))
    
    let resultTag: string
    if (toInstall.length === 0) {
      resultTag = `<dyad-add-dependency-result status="already-installed" packages="${alreadyInstalled.join(' ')}">`
    } else {
      const { installed, failed } = await installPackages(toInstall, appPath)
      if (failed.length === 0) {
        resultTag = `<dyad-add-dependency-result status="success" packages="${installed.join(' ')}">`
      } else {
        resultTag = `<dyad-add-dependency-result status="error" packages="${toInstall.join(' ')}" error="${failed[0].error}">`
      }
    }
    
    result = result.replace(fullTag, resultTag)
  }
  
  // Persist updated content to DB
  await db.update(messages)
    .set({ content: result })
    .where(eq(messages.id, messageId))
  
  return result
}

function isInPackageJson(packageName: string, appPath: string): boolean {
  try {
    const pkg = JSON.parse(fs.readFileSync(path.join(appPath, 'package.json'), 'utf-8'))
    const allDeps = { ...pkg.dependencies, ...pkg.devDependencies }
    // Strip version from package name for comparison
    const name = packageName.split('@')[0] || packageName
    return name in allDeps
  } catch {
    return false
  }
}
```

**System prompt instruction to LLM:**
```
When you use an npm package that may not be installed, emit:
<dyad-add-dependency packages="package-name another-package">

Rules:
- Only emit for packages that are imported in generated code
- Use the exact npm package name (scoped packages: @scope/name)  
- Space-separate multiple packages in one tag
- Do not emit for built-in Node modules or browser APIs
```

## Data contracts

```typescript
// LLM emits in response text:
// <dyad-add-dependency packages="react-query framer-motion @tanstack/react-table">

// After processing, stored in DB as:
// <dyad-add-dependency-result status="success" packages="react-query framer-motion">
// OR
// <dyad-add-dependency-result status="error" packages="react-query" error="npm ERR! ...">
// OR  
// <dyad-add-dependency-result status="already-installed" packages="react">

// DB: messages.content column gets the substitution applied in-place
```

## Dependencies & assumptions

- Node `child_process.exec` (or `execa`) for running install commands
- npm and/or pnpm must be available in the app's process environment
- `package.json` exists in the app root
- Optional: `socket` CLI from Socket.dev for firewall (`npx socket`)
- DB: Drizzle ORM or any SQLite wrapper for persisting the tag replacement

## To port this, you need:

- [ ] System prompt instruction telling the LLM to emit `<dyad-add-dependency>` tags
- [ ] Package name validation regex (prevent command injection)
- [ ] Package manager detector (pnpm-lock.yaml → pnpm, otherwise npm)
- [ ] `execAsync` wrapper with timeout and cwd
- [ ] `isInPackageJson()` pre-check to skip already-installed packages
- [ ] Tag-replacement logic in the message string (regex replace, in-place)
- [ ] DB update to persist the replaced content after install

## Gotchas

- **Command injection risk:** Never interpolate unvalidated package names into shell commands. The regex validation is a security boundary — enforce it before passing to exec.
- **The LLM doesn't check package.json:** It will emit tags for packages it "knows" an app would need, even if they're already there. The `isInPackageJson()` check prevents redundant installs and "already installed" confusion.
- **npm install can take 60-120 seconds:** On slow networks or for large packages. Use a generous timeout (≥2 minutes). User should see a loading state during install.
- **Result tag must be persisted:** Don't just update in-memory. If the app restarts, the chat history must show what was installed. Write the replacement to the DB immediately.
- **pnpm workspace interference:** If the app's parent directory has a pnpm workspace, running `pnpm add` from the app subdirectory may update the wrong `package.json`. Verify with `--filter` if in a monorepo.

## Origin (reference only)
- Repo: https://github.com/dyad-sh/dyad
- Key files: `src/ipc/processors/executeAddDependency.ts`
