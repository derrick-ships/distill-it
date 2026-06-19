# Submit-and-Poll Generation Client (build spec) — distilled from open-generative-ai

## Summary
A single async primitive that drives *every* long-running AI generation (image, i2i, video, i2v, v2v, lip-sync, audio, ads). POST a job to `/{endpoint}` → receive a `request_id` → poll a result endpoint on a fixed interval until the job reports a terminal status, then normalize the output to a single `url`. One function (`submitAndPoll`) plus one poller (`pollForResult`) back the whole product; each public generation function is a thin payload-builder that calls it. This is the canonical way to wrap any async "fal/replicate/muapi-style" model gateway.

## Core logic (inlined)

The base URL flips between same-origin proxy (browser) and the real host (SSR/Electron). See the proxy build spec for why — but this is the line:

```javascript
const BASE_URL = (typeof window !== 'undefined' && window.location?.protocol?.startsWith('http'))
    ? '/api'                       // browser → goes through the host app's proxy route
    : 'https://api.muapi.ai';      // SSR / Electron → call the gateway directly
```

The submit+poll primitive:

```javascript
async function submitAndPoll(endpoint, payload, key, onRequestId, maxAttempts = 60) {
    const url = `${BASE_URL}/api/v1/${endpoint}`;
    const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-api-key': key },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        const errText = await response.text();
        notifyAuthRequired(response.status, errText);   // 401/403 → fire DOM event (see proxy/auth doc)
        throw new Error(`API Request Failed: ${response.status} ${response.statusText} - ${errText.slice(0, 100)}`);
    }
    const submitData = await response.json();
    const requestId = submitData.request_id || submitData.id;
    if (!requestId) return submitData;            // synchronous result — no polling needed
    if (onRequestId) onRequestId(requestId);       // surface id to UI (cancel / progress / history)
    const result = await pollForResult(requestId, key, maxAttempts);
    const outputUrl = result.outputs?.[0] || result.url || result.output?.url;  // normalize shape
    return { ...result, url: outputUrl };
}
```

The poller — fixed interval, retry-through-5xx, fail-fast-on-4xx, terminal-status detection:

```javascript
async function pollForResult(requestId, key, maxAttempts = 900, interval = 2000) {
    const pollUrl = `${BASE_URL}/api/v1/predictions/${requestId}/result`;
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        await new Promise(resolve => setTimeout(resolve, interval));   // wait FIRST, then poll
        try {
            const response = await fetch(pollUrl, {
                headers: { 'Content-Type': 'application/json', 'x-api-key': key }
            });
            if (!response.ok) {
                const errText = await response.text();
                if (response.status >= 500) continue;          // transient server error → keep polling
                notifyAuthRequired(response.status, errText);
                throw new Error(`Poll Failed: ${response.status} - ${errText.slice(0, 100)}`);
            }
            const data = await response.json();
            const status = data.status?.toLowerCase();
            if (status === 'completed' || status === 'succeeded' || status === 'success') return data;
            if (status === 'failed'    || status === 'error')                             throw new Error(`Generation failed: ${data.error || 'Unknown error'}`);
            // any other status (queued / processing / in_progress) → loop again
        } catch (error) {
            if (attempt === maxAttempts) throw error;   // swallow transient errors until the last attempt
        }
    }
    throw new Error('Generation timed out after polling.');
}
```

A public generation function is just a payload-builder + a per-task `maxAttempts` budget:

```javascript
export async function generateImage(apiKey, params) {
    const modelInfo = getModelById(params.model);        // registry lookup (see model-registry doc)
    const endpoint  = modelInfo?.endpoint || params.model;
    const payload = { prompt: params.prompt };
    if (params.aspect_ratio) payload.aspect_ratio = params.aspect_ratio;
    if (params.resolution)   payload.resolution   = params.resolution;
    if (params.quality)      payload.quality      = params.quality;
    if (params.image_url) {                               // i2i mode
        payload.image_url = params.image_url;
        payload.strength  = params.strength || 0.6;
    } else if (params.images_list) {                     // multi-image input (up to 14)
        payload.images_list = params.images_list;
    } else {
        payload.image_url = null;
    }
    if (params.seed && params.seed !== -1) payload.seed = params.seed;
    return submitAndPoll(endpoint, payload, apiKey, params.onRequestId, 60);   // images: ~2 min budget
}

export async function generateVideo(apiKey, params) {
    const modelInfo = getVideoModelById(params.model);
    const endpoint  = modelInfo?.endpoint || params.model;
    const payload = {};
    if (params.prompt)       payload.prompt       = params.prompt;
    if (params.aspect_ratio) payload.aspect_ratio = params.aspect_ratio;
    if (params.duration)     payload.duration     = params.duration;
    if (params.resolution)   payload.resolution   = params.resolution;
    if (params.quality)      payload.quality      = params.quality;
    if (params.mode)         payload.mode         = params.mode;
    if (params.image_url)    payload.image_url    = params.image_url;
    return submitAndPoll(endpoint, payload, apiKey, params.onRequestId, 900);  // video: ~30 min budget
}
```

## Data contracts
- **Submit request**: `POST {BASE_URL}/api/v1/{endpoint}`, headers `{ 'Content-Type':'application/json', 'x-api-key': key }`, body = task-specific JSON payload. `endpoint` is resolved from the model registry, not hardcoded.
- **Submit response**: `{ request_id?: string, id?: string, ...maybeSyncResult }`. If neither id field is present, the whole body IS the result (synchronous path).
- **Poll request**: `GET {BASE_URL}/api/v1/predictions/{requestId}/result`, same headers.
- **Poll response**: `{ status: string, outputs?: string[], url?: string, output?: { url }, error?: string }`. `status` is matched case-insensitively against terminal sets:
  - success: `completed | succeeded | success`
  - failure: `failed | error`
  - anything else = still running → keep polling.
- **Normalized return**: `{ ...result, url: <first of outputs[0] | url | output.url> }`. Callers always read `.url`.
- **Timing**: `interval = 2000ms`, sleep-then-poll order. Budgets: images `maxAttempts=60` (~2 min), video/i2v/lipsync `maxAttempts=900` (~30 min). Default poller budget if unspecified is `900`.

## Dependencies & assumptions
- Browser `fetch` + `setTimeout` only — no SDK, no websockets, no SSE. Portable to any runtime with `fetch`.
- Assumes the gateway is **submit→poll** (HTTP 202-style async jobs keyed by an id), not streaming. If your provider streams or uses webhooks, this pattern doesn't apply unchanged.
- Assumes a stable `predictions/{id}/result` shape and string status fields.
- `notifyAuthRequired` (see proxy/auth-bridge doc) is the only coupling out of this module; it just dispatches a DOM event on 401/403.

## To port this, you need:
- [ ] A gateway whose generation endpoints return a job id and expose a pollable result endpoint.
- [ ] An auth scheme injectable as a request header (here `x-api-key`).
- [ ] A place to set per-task polling budgets (cheap/fast tasks get small `maxAttempts`; long renders get large).
- [ ] A normalizer that collapses the provider's varied output shapes into one field your UI reads (`.url`).
- [ ] An `onRequestId` hook if you want cancel/progress/history keyed by the job id.
- [ ] Optional: a hook (event/callback) to escalate 401/403 to a re-auth UI.

## Gotchas
- **Sleep-before-poll** is deliberate: never hammer the result endpoint at t=0 when the job certainly isn't done. Costs one interval of latency on instant jobs; worth it.
- **5xx are retried, 4xx are fatal.** A 500 during polling is treated as transient (`continue`); a 4xx throws (after firing auth event for 401/403). Get this backwards and you either spin forever on a real error or give up on a blip.
- **The try/catch swallows errors until the final attempt.** Transient network failures mid-poll don't kill the job; only an error on the *last* attempt propagates. This is robust but can hide a persistent error for the whole budget — log inside the catch if you need visibility.
- **No client-side cancel of the server job.** `onRequestId` lets the UI *stop listening*, but the gateway job keeps running (and billing). If you need true cancel you must add a cancel endpoint call.
- **Fixed 2s interval, no backoff.** A 30-min video = ~900 requests. Fine for a single user; if you fan out many concurrent generations consider exponential backoff or a longer interval for long tasks.
- **Output normalization is best-effort.** If a new model returns yet another shape (e.g. `result.video.url`), `.url` will be `undefined`. Keep the fallback chain in sync with the gateway's response variants.
- **`maxAttempts` is the only timeout.** There's no wall-clock deadline; if the gateway hangs in a non-terminal status, you wait the full `interval * maxAttempts`.

## Origin (reference only)
`Anil-matcha/Open-Generative-AI` — `packages/studio/src/muapi.js` (`submitAndPoll`, `pollForResult`, `generateImage`, `generateVideo`, and every other `generate*/process*` wrapper). Endpoints resolved via `models.js` (`getModelById`, `getVideoModelById`).
