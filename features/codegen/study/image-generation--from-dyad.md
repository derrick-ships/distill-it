# Image Generation — from [dyad](https://github.com/dyad-sh/dyad)

> Domain: [[_domain]] · Source: https://github.com/dyad-sh/dyad · NotebookLM: 

## What it does

Inside Dyad, you can generate images to use in your app without leaving the builder. You describe what you want, pick a style theme (plain, 3D clay, photorealistic, or isometric), and the image is generated via Dyad's hosted engine and saved directly to the app's media directory. The AI can also reference these images when building the app's UI.

## Why it exists

App builders need images — hero images, icons, illustrations, product mockups. Traditionally you'd context-switch to Midjourney or DALL-E, download the image, and manually place it in your project. Dyad's in-builder image generation closes that loop: generate an image and it's immediately available as a file path the AI can reference in the generated code.

## How it actually works

**Endpoint:** Image generation calls go to `https://engine.dyad.sh/v1` (or a custom URL set via env variable). This is Dyad's own hosted service, not a direct call to OpenAI or another provider. The model name used is `"gpt-image-1.5"`. Authentication uses a Dyad API key from settings (separate from provider keys).

**Theme prompts:** The handler prepends a system-level style description to the user's prompt based on their selected theme:
- **Plain**: no prefix
- **3D clay morphism**: "sculpted clay-like forms, soft lighting, rounded edges, matte pastel surfaces"
- **Real photography**: "hyperrealistic photograph, cinematically lit, DSLR, shallow depth of field"
- **Isometric illustration**: "clean vector isometric illustration, 30° projection, flat colors"

The prefix is invisible to the user but shapes the output significantly.

**Request flow:**
1. Validates the API key exists in settings
2. Looks up the app in the DB (needs app path for file storage)
3. Generates a unique `requestId` (UUID) and stores it in an `activeControllers` map with an `AbortController`
4. POSTs to the engine with `{ model, prompt (theme + user text), response_format }` plus `Authorization: Bearer <key>` header
5. Sets a **120-second timeout** on the AbortController
6. Validates the response schema
7. If the response contains `b64_json`: decodes base64 → Buffer → writes to disk
8. If the response contains a URL: validates it's HTTPS, fetches it (max 50MB), writes to disk
9. Saves to `.dyad/media/<uniqueName>.png` using a file lock for consistency
10. Returns the relative file path to the renderer

**Cancellation:** The renderer can send a cancel IPC message with the `requestId`. The handler looks up the `AbortController` by ID and calls `abort()`, which cancels the HTTP request and removes the entry from the map.

**Safety limits:** HTTPS-only URL validation, 50MB response size cap, JSON schema validation of the response shape before processing — all guards against a compromised or misbehaving engine endpoint.

## The non-obvious parts

- **Dyad-hosted engine, not direct API:** Image generation doesn't use the user's own OpenAI key (even if configured). It goes through Dyad's engine. This means Dyad can rate-limit, monetize (Pro feature), or swap the underlying model without client changes. The `gpt-image-1.5` model name hints at a GPT-image backend, but the actual routing is opaque to the client.
- **File lock on write:** The media directory write uses a file lock (`proper-lockfile` or similar) so two concurrent image generation requests don't write to the same filename simultaneously. File names are UUID-based to avoid collisions anyway, but the lock protects the directory index.
- **Theme is a client-side concern, not server-side:** The engine doesn't know about Dyad's themes. The theme is implemented purely by prompt prefix concatenation in the handler. Any theme can be added without a server change.
- **Images saved to `.dyad/media/`:** This is a convention directory inside the app. The AI, when told an image exists at `.dyad/media/hero.png`, knows the correct relative path to reference in `<img>` tags or CSS. It's a shared namespace between generation and the AI's code awareness.

## Related
- [[ai-chat-stream--from-dyad]] (generated images referenced in build-mode conversations)
- [[multi-app-library--from-dyad]] (images live inside the app's directory)
- [[byok-settings--from-dyad]] (Dyad API key for engine access stored here)
