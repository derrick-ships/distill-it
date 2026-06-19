# Image Generation (build spec) — distilled from dyad

## Summary

Build an in-app AI image generation feature: accept a user prompt + style theme, prepend a theme-specific style prefix, POST to an image generation API (OpenAI-compatible), handle both base64 and URL responses, save the result to the app's media directory under a file lock, support cancellation via an AbortController map, and return the relative file path for use in generated code.

## Core logic (inlined)

```typescript
// --- THEME PREFIXES ---
const THEME_PREFIXES: Record<string, string> = {
  plain: '',
  clay: 'Sculpted clay-like 3D forms, soft ambient occlusion, rounded edges, matte pastel surfaces, studio lighting. ',
  photo: 'Hyperrealistic photograph, cinematically lit, DSLR camera, shallow depth of field, 8K resolution. ',
  isometric: 'Clean vector isometric illustration, 30° projection, flat colors, crisp outlines, icon-style. ',
}

// --- ACTIVE REQUEST TRACKING ---
const activeControllers = new Map<string, AbortController>()

// --- MAIN HANDLER ---
async function generateImage(
  appId: number,
  requestId: string,    // UUID from renderer
  prompt: string,
  theme: keyof typeof THEME_PREFIXES,
  settings: UserSettings
): Promise<{ filePath: string }> {
  // 1. Validate prerequisites
  if (!settings.dyadApiKey) throw new Error('Dyad API key required for image generation')
  const app = await db.select().from(apps).where(eq(apps.id, appId)).get()
  if (!app) throw new Error(`App ${appId} not found`)
  
  // 2. Build prompt
  const fullPrompt = (THEME_PREFIXES[theme] ?? '') + prompt
  
  // 3. Set up abort controller with 120s timeout
  const controller = new AbortController()
  activeControllers.set(requestId, controller)
  const timeoutId = setTimeout(() => controller.abort(), 120_000)
  
  try {
    // 4. Call image API
    const apiBase = process.env.DYAD_ENGINE_URL ?? 'https://engine.dyad.sh/v1'
    const res = await fetch(`${apiBase}/images/generations`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${settings.dyadApiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'gpt-image-1.5',
        prompt: fullPrompt,
        response_format: 'b64_json',  // prefer base64; fall back to URL
        n: 1,
        size: '1024x1024',
      }),
      signal: controller.signal,
    })
    
    if (!res.ok) throw new Error(`Image API error: ${res.status} ${await res.text()}`)
    
    // 5. Validate response schema
    const body = await res.json()
    const imageData = body?.data?.[0]
    if (!imageData) throw new Error('No image data in response')
    
    // 6. Get image bytes
    let imageBuffer: Buffer
    if (imageData.b64_json) {
      imageBuffer = Buffer.from(imageData.b64_json, 'base64')
    } else if (imageData.url) {
      // Validate URL safety
      const url = new URL(imageData.url)
      if (url.protocol !== 'https:') throw new Error('Image URL must be HTTPS')
      
      const imgRes = await fetch(imageData.url, { signal: controller.signal })
      if (!imgRes.ok) throw new Error('Failed to download image')
      
      const contentLength = Number(imgRes.headers.get('content-length') ?? 0)
      if (contentLength > 50 * 1024 * 1024) throw new Error('Image too large (max 50MB)')
      
      imageBuffer = Buffer.from(await imgRes.arrayBuffer())
    } else {
      throw new Error('Response has neither b64_json nor url')
    }
    
    // 7. Save to app media directory (with file lock)
    const mediaDir = path.join(app.path, '.dyad', 'media')
    fs.mkdirSync(mediaDir, { recursive: true })
    
    const filename = `generated-${Date.now()}-${crypto.randomUUID().slice(0, 8)}.png`
    const filePath = path.join(mediaDir, filename)
    
    // File lock prevents concurrent write conflicts
    const lock = await acquireFileLock(mediaDir)
    try {
      fs.writeFileSync(filePath, imageBuffer)
    } finally {
      await lock.release()
    }
    
    // Return relative path (for use in code: <img src=".dyad/media/generated-xxx.png">)
    return { filePath: path.relative(app.path, filePath) }
    
  } finally {
    clearTimeout(timeoutId)
    activeControllers.delete(requestId)
  }
}

// --- CANCELLATION ---
function cancelImageGeneration(requestId: string): void {
  const controller = activeControllers.get(requestId)
  if (controller) {
    controller.abort()
    activeControllers.delete(requestId)
  }
}

// --- IPC REGISTRATION ---
function registerImageGenerationHandlers() {
  ipcMain.handle('image:generate', async (_, { appId, requestId, prompt, theme }) => {
    const settings = readEffectiveSettings()
    return generateImage(appId, requestId, prompt, theme, settings)
  })
  
  ipcMain.handle('image:cancel', (_, { requestId }) => {
    cancelImageGeneration(requestId)
  })
}
```

## Data contracts

```typescript
// IPC: image:generate(appId, requestId, prompt, theme) → { filePath: string }
interface GenerateImageRequest {
  appId: number
  requestId: string     // UUID, used for cancellation
  prompt: string        // user's description
  theme: 'plain' | 'clay' | 'photo' | 'isometric'
}

interface GenerateImageResponse {
  filePath: string      // relative to app root: ".dyad/media/generated-xxx.png"
}

// IPC: image:cancel(requestId) → void

// Image API request (OpenAI images/generations compatible):
interface ImageAPIRequest {
  model: string                    // "gpt-image-1.5" or "dall-e-3" etc.
  prompt: string                   // theme prefix + user prompt
  response_format: 'b64_json' | 'url'
  n: number                        // 1
  size: '1024x1024' | '1792x1024' | '1024x1792'
}

// Image API response:
interface ImageAPIResponse {
  data: Array<{
    b64_json?: string   // base64-encoded PNG
    url?: string        // HTTPS URL to download from
  }>
}

// Settings field needed:
// dyadApiKey: string  (encrypted, different from provider API keys)
```

## Dependencies & assumptions

- OpenAI-compatible image generation endpoint (`/images/generations`)
- **`proper-lockfile`** or similar for directory-level file locking
- Node `fs`, `crypto`, `path`, `fetch` (Node 18+)
- AbortController (native Node 18+)
- App must have a `.dyad/media/` directory convention (created on first use)

## To port this, you need:

- [ ] Theme prefix map (or load from config for user-extensible themes)
- [ ] `activeControllers` map keyed by `requestId` for cancellation
- [ ] 120-second AbortController timeout on the fetch
- [ ] Response handler supporting both `b64_json` and `url` formats
- [ ] HTTPS URL validation before fetching remote images
- [ ] 50MB size limit check on URL-based responses
- [ ] File lock on the media directory write
- [ ] UUID + timestamp filename for uniqueness
- [ ] Return relative path (not absolute) so the AI can reference it portably

## Gotchas

- **Dyad uses a hosted engine, not direct OpenAI:** The endpoint is `engine.dyad.sh/v1`, not `api.openai.com`. If you're building your own, wire directly to OpenAI DALL-E 3 or gpt-image-1 with the user's own OpenAI key.
- **Theme is client-side only:** The style is a prompt prefix, not a server-side parameter. Any theme can be added without changing the API. Keep themes as data (configurable), not hardcoded.
- **File lock prevents simultaneous writes:** Without it, two concurrent generation requests could corrupt each other's output. Directory-level lock (not per-file) is simpler.
- **Relative path return is critical:** The renderer or AI needs a path it can use in `<img>` tags relative to the app root. Absolute paths won't work in the served app. Always `path.relative(app.path, filePath)`.
- **requestId must come from the renderer:** The caller generates the UUID. This ensures the cancel IPC can match the right request even if multiple generations are in flight simultaneously.
- **AbortController aborts the fetch, not the server:** If you call `abort()`, the HTTP request is dropped on the client side, but the server may still complete the generation. This is expected behavior — just make sure you clean up `activeControllers`.

## Origin (reference only)
- Repo: https://github.com/dyad-sh/dyad
- Key files: `src/ipc/handlers/image_generation_handlers.ts`
