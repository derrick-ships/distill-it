# WhatsApp Provider Adapter Layer — from [whatsapp-agentkit](https://github.com/Hainrixz/whatsapp-agentkit)

> Domain: [[_domain]] · Source: https://github.com/Hainrixz/whatsapp-agentkit · NotebookLM: <add link>

## What it does
It lets one chatbot talk to WhatsApp through *either* Twilio *or* Meta's official Cloud API without the rest of the app knowing which one is in use. Twilio and Meta send wildly different webhook payloads (Twilio is flat form-encoded; Meta is deeply nested JSON) and have different sending APIs and auth schemes. This layer hides all of that behind a tiny common interface: every inbound message, whatever its origin, becomes the same little object, and "send a reply" is one method call. Switching providers is a one-line change in an env file.

## Why it exists
WhatsApp has two realistic on-ramps and they suit different users: Twilio's sandbox is free and needs no business verification (great for trying things out), while Meta's Cloud API is free per-conversation but demands a verified Facebook Business account (better for real production volume). A non-technical owner shouldn't have to commit to one forever, and the app's core logic — memory, the AI brain, the webhook handler — shouldn't be rewritten when they switch. The job-to-be-done is "support both, pick at config time, keep the core provider-blind." It's the textbook adapter/strategy pattern applied to a messaging channel.

## How it actually works
Three pieces:

1. **A common contract** — an abstract `ProveedorWhatsApp` class with three methods: `parsear_webhook(request)` returns a list of normalized `MensajeEntrante` objects, `enviar_mensaje(telefono, mensaje)` sends a text and returns success/failure, and an optional `validar_webhook(request)` for the GET handshake (only Meta needs it; the base returns `None`). The normalized message is a tiny dataclass: phone number, text, message id, and an `es_propio` flag for "this was sent by us, ignore it."

2. **A factory** — `obtener_proveedor()` reads `WHATSAPP_PROVIDER` from the environment, and returns either a `ProveedorMeta` or a `ProveedorTwilio`. It imports the chosen adapter lazily (so you don't need both providers' assumptions loaded) and raises a clear error if the variable is missing or unrecognized.

3. **Two adapters, each translating one provider's reality into the contract:**
   - **Meta** digs through the nested `entry[].changes[].value.messages[]` structure, keeps only `type == "text"` messages, and maps each to a `MensajeEntrante`. Its `validar_webhook` answers Meta's subscription handshake by echoing back `hub.challenge` as an integer when `hub.verify_token` matches. Sending is a `POST` to `graph.facebook.com/v21.0/{phone_number_id}/messages` with a Bearer token, success = HTTP 200.
   - **Twilio** reads a flat form body (`Body`, `From`, `MessageSid`), strips the `whatsapp:` prefix off the phone number, and produces one `MensajeEntrante`. Sending is a `POST` to Twilio's Messages endpoint with HTTP Basic auth (base64 of `SID:token`), success = HTTP 201.

The FastAPI server just calls `proveedor.parsear_webhook(...)` and `proveedor.enviar_mensaje(...)` — it never branches on provider.

## The non-obvious parts
- **The normalized `MensajeEntrante` is the whole trick.** By forcing both providers to emit the *same* four-field object, every downstream component (memory, brain, the webhook loop) is written once. The adapters absorb 100% of the provider-specific ugliness.
- **`validar_webhook` lives on the base with a no-op default.** Meta requires a GET verification handshake; Twilio doesn't. Rather than special-case Meta in the server, the base class returns `None` and only Meta overrides it — the server calls it unconditionally and just ignores a `None`.
- **Different success codes per provider (200 vs 201)** — a small reminder that "send succeeded" isn't universal. Each adapter knows its own provider's contract; the caller only sees a boolean.
- **Meta returns the challenge as an `int`, deliberately.** Meta expects the raw challenge value echoed in the GET response body; casting to int and returning it (the server wraps it in a `PlainTextResponse`) satisfies that quirk.
- **Lazy imports in the factory** mean a Twilio-only deployment never imports Meta's module (and vice-versa) — which also matches the kit's "generate only the chosen adapter" rule, so the un-chosen module may not even exist on disk.
- **No inbound authenticity check.** Twilio signs its requests and Meta supports payload signatures, but neither is verified here. The layer trusts whatever hits `/webhook`. Fine for a sandbox demo, a real gap for production.

## Related
- [[interview-driven-scaffolding--from-whatsapp-agentkit]] — the kit that generates this layer (and only the chosen adapter).
- [[conversation-memory--from-whatsapp-agentkit]] — keys its history off the `telefono` field this layer normalizes.
- See also: [[ordered-backend-routing--from-agent-reach]] — a richer take on the same idea (interchangeable backends behind one interface, with health-gated automatic fallback rather than a static env pick).
