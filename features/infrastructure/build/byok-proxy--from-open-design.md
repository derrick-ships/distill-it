# BYOK Proxy (build spec) — distilled from open-design

## Summary

Provider-agnostic streaming HTTP proxy in the local daemon. 6 provider endpoints (Anthropic, OpenAI, Azure, Google, Ollama, SenseAudio). SSE response streaming with 4 event types. API key passed in request body (not stored as env var by default). SSRF protection blocks internal IPs, link-local, CGNAT.

## Core logic (inlined)

**Endpoint pattern:**
```
POST /api/proxy/{anthropic,openai,azure,google,ollama,senseaudio}/stream
```

**Request processing:**
```typescript
// 1. Parse ProxyStreamRequest from body
// 2. SSRF check: reject internal IPs / link-local / CGNAT
// 3. Build provider-specific request headers + body
// 4. Forward to baseUrl with apiKey auth
// 5. Stream response back as SSE
```

**SSRF protection (applied before forwarding):**
```
Blocked ranges:
  10.0.0.0/8          (RFC 1918 private)
  172.16.0.0/12       (RFC 1918 private)
  192.168.0.0/16      (RFC 1918 private)
  169.254.0.0/16      (link-local)
  100.64.0.0/10       (CGNAT)
  127.0.0.0/8         (loopback)
  ::1                 (IPv6 loopback)
  fc00::/7            (IPv6 ULA)
// Note: Ollama's localhost default is allowed via a documented exception
// or the user provides the resolved external IP
```

**SSE event stream:**
```typescript
type ProxySseEvent =
  | { type: 'start'; model?: string }            // ProxyStreamStartPayload
  | { type: 'delta'; text: string }              // ProxyStreamDeltaPayload
  | { type: 'error'; message: string; code?: string }  // SseErrorPayload
  | { type: 'end'; statusCode?: number }         // ProxyStreamEndPayload

// Wire format (SSE):
// data: {"type":"start","model":"claude-sonnet-4-5"}\n\n
// data: {"type":"delta","text":"Hello"}\n\n
// data: {"type":"end","statusCode":200}\n\n
```

## Data contracts

**ProxyStreamRequest:**
```typescript
{
  baseUrl: string,         // provider endpoint, e.g. "https://api.anthropic.com"
  apiKey: string,          // passed in body, not header
  model: string,           // model ID, e.g. "claude-sonnet-4-5"
  messages: Array<{
    role: 'system' | 'user' | 'assistant' | 'tool',
    content: string | Array<ContentBlock>
  }>,
  systemPrompt?: string,
  maxTokens?: number,       // default 8192
  apiVersion?: string       // Azure-specific API version string
}

// Multimodal content block:
ContentBlock = {
  type: 'text',  text: string
} | {
  type: 'image', data: string (base64), format: 'jpeg'|'png'|'gif'|'webp'
}
```

**Provider-specific notes:**
```
Anthropic: x-api-key header, anthropic-version header
OpenAI: Bearer token in Authorization header
Azure: api-key header + api-version query param (from apiVersion field)
Google: Bearer token or x-goog-api-key depending on endpoint
Ollama: no auth required (localhost); baseUrl = http://localhost:11434
SenseAudio: audio-specific endpoints, not LLM chat
```

## Dependencies & assumptions

- Hono HTTP framework (daemon uses it throughout)
- Node.js built-in `fetch` or equivalent for upstream HTTP calls
- SSE: `text/event-stream` content-type, `data:` prefixed lines, `\n\n` terminated
- No persistent key storage confirmed — keys travel in request body per call
- Ollama: user must have Ollama server running locally; default port 11434

## To port this, you need:

- [ ] Route handler for `POST /api/proxy/:provider/stream`
- [ ] SSRF blocker: reject requests to RFC 1918, link-local, CGNAT, loopback ranges
- [ ] ProxyStreamRequest parser with Zod validation
- [ ] Provider dispatch: build provider-specific auth headers from `apiKey` field
- [ ] Upstream streaming: fetch with streaming body, parse provider's SSE/chunk format
- [ ] Normalize to 4-event SSE format: start, delta, error, end
- [ ] Azure special case: append `api-version` query param from `apiVersion` field

## Gotchas

- **API key in body, not header.** Some provider clients default to Authorization header injection. Here it's explicit in the body — your proxy owns the auth header construction.
- **SSRF is a real threat.** Without the IP range check, a malicious prompt could instruct the AI to call `http://169.254.169.254/latest/meta-data/` (AWS IMDSv1) or internal services. Block the ranges before the upstream fetch.
- **Ollama and the SSRF blocker conflict by default.** Ollama's default localhost address is in the loopback range. You need an explicit allowlist entry or config flag for local development.
- **maxTokens defaults to 8192 — not all providers support this.** Some providers cap lower (e.g., older GPT-3.5 endpoints). Handle `400 invalid_request` on the maxTokens field gracefully.
- **Azure needs apiVersion.** Missing this field causes a 400. Make it required when provider is `azure`, optional otherwise.
- **Key persistence is unconfirmed.** The AppConfigPrefs schema doesn't show explicit key fields, but the Connectors system does have `providerConnectionId` and credential storage. Don't assume keys are ephemeral — plan for encrypted-at-rest storage.

## Origin (reference only)

Repo: https://github.com/nexu-io/open-design  
Key files: `apps/daemon/src/proxy-routes.ts`, `apps/daemon/src/types/proxy.ts`
