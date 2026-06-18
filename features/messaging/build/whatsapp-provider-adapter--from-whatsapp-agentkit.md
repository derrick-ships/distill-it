# WhatsApp Provider Adapter Layer (build spec) — distilled from whatsapp-agentkit

## Summary
A provider-agnostic messaging integration: one abstract interface + a config-driven factory + per-provider adapters that translate each provider's webhook/send API into a common normalized message. The rest of the app (webhook handler, memory, AI brain) is written once against the interface and never branches on provider. Selection is via an env var (`WHATSAPP_PROVIDER=meta|twilio`). Adapters absorb all provider-specific parsing, auth, endpoints, and success-code quirks. This is the adapter/strategy pattern for a messaging channel; the WhatsApp specifics (Meta + Twilio) are concrete examples you can swap for SMS, Telegram, etc.

## Core logic (inlined)

### The contract (`base.py`)
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from fastapi import Request

@dataclass
class MensajeEntrante:                 # normalized inbound message — same shape for every provider
    telefono: str                      # sender phone (provider-prefix stripped)
    texto: str                         # message body
    mensaje_id: str                    # provider's unique message id
    es_propio: bool                    # True if WE sent it (echo) → caller ignores it

class ProveedorWhatsApp(ABC):
    @abstractmethod
    async def parsear_webhook(self, request: Request) -> list[MensajeEntrante]:
        """Extract + normalize inbound messages from the provider's webhook payload."""
        ...
    @abstractmethod
    async def enviar_mensaje(self, telefono: str, mensaje: str) -> bool:
        """Send a text. Return True on success."""
        ...
    async def validar_webhook(self, request: Request) -> dict | int | None:
        """GET verification handshake. Only some providers (Meta) need it; default no-op."""
        return None
```

### The factory (`__init__.py`)
```python
import os
from .base import ProveedorWhatsApp

def obtener_proveedor() -> ProveedorWhatsApp:
    proveedor = os.getenv("WHATSAPP_PROVIDER", "").lower()
    if not proveedor:
        raise ValueError("WHATSAPP_PROVIDER no configurado. Usa: meta o twilio")
    if proveedor == "meta":
        from .meta import ProveedorMeta;     return ProveedorMeta()
    if proveedor == "twilio":
        from .twilio import ProveedorTwilio;  return ProveedorTwilio()
    raise ValueError(f"Proveedor no soportado: {proveedor}")
```
Lazy imports → only the chosen adapter is loaded (and, per the kit, may be the only one on disk).

### Meta adapter (`meta.py`) — nested JSON, Bearer auth, HTTP 200, GET handshake
```python
class ProveedorMeta(ProveedorWhatsApp):
    def __init__(self):
        self.access_token   = os.getenv("META_ACCESS_TOKEN")
        self.phone_number_id= os.getenv("META_PHONE_NUMBER_ID")
        self.verify_token   = os.getenv("META_VERIFY_TOKEN", "agentkit-verify")
        self.api_version    = "v21.0"

    async def validar_webhook(self, request):                 # GET /webhook handshake
        p = request.query_params
        if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == self.verify_token:
            return int(p.get("hub.challenge"))                # echo challenge as int
        return None

    async def parsear_webhook(self, request):                 # deeply nested payload
        body = await request.json(); out = []
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                for msg in change.get("value", {}).get("messages", []):
                    if msg.get("type") == "text":
                        out.append(MensajeEntrante(
                            telefono=msg.get("from",""),
                            texto=msg.get("text",{}).get("body",""),
                            mensaje_id=msg.get("id",""), es_propio=False))
        return out

    async def enviar_mensaje(self, telefono, mensaje):
        if not self.access_token or not self.phone_number_id: return False
        url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}/messages"
        headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type":"application/json"}
        payload = {"messaging_product":"whatsapp","to":telefono,"type":"text","text":{"body":mensaje}}
        async with httpx.AsyncClient() as c:
            r = await c.post(url, json=payload, headers=headers)
            return r.status_code == 200                       # Meta success = 200
```

### Twilio adapter (`twilio.py`) — flat form body, Basic auth, HTTP 201
```python
class ProveedorTwilio(ProveedorWhatsApp):
    def __init__(self):
        self.account_sid  = os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token   = os.getenv("TWILIO_AUTH_TOKEN")
        self.phone_number = os.getenv("TWILIO_PHONE_NUMBER")

    async def parsear_webhook(self, request):                 # form-encoded, single message
        form = await request.form()
        texto = form.get("Body","")
        if not texto: return []
        return [MensajeEntrante(
            telefono=form.get("From","").replace("whatsapp:",""),   # strip channel prefix
            texto=texto, mensaje_id=form.get("MessageSid",""), es_propio=False)]

    async def enviar_mensaje(self, telefono, mensaje):
        if not all([self.account_sid, self.auth_token, self.phone_number]): return False
        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
        auth = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()
        data = {"From": f"whatsapp:{self.phone_number}", "To": f"whatsapp:{telefono}", "Body": mensaje}
        async with httpx.AsyncClient() as c:
            r = await c.post(url, data=data, headers={"Authorization": f"Basic {auth}"})
            return r.status_code == 201                        # Twilio success = 201
```

### How the server uses it (provider-blind)
```python
proveedor = obtener_proveedor()                      # once, at startup
# GET /webhook:
res = await proveedor.validar_webhook(request)
return PlainTextResponse(str(res)) if res is not None else {"status":"ok"}
# POST /webhook:
for msg in await proveedor.parsear_webhook(request):
    if msg.es_propio or not msg.texto: continue
    ... # brain + memory
    await proveedor.enviar_mensaje(msg.telefono, respuesta)
```

## Data contracts
- **Normalized inbound:** `MensajeEntrante{telefono:str, texto:str, mensaje_id:str, es_propio:bool}`.
- **Meta webhook (inbound):** `{entry:[{changes:[{value:{messages:[{from, id, type, text:{body}}]}}]}]}`. GET verify: query params `hub.mode`, `hub.verify_token`, `hub.challenge`.
- **Meta send (outbound):** POST `graph.facebook.com/v21.0/{phone_number_id}/messages`, Bearer auth, body `{messaging_product:"whatsapp", to, type:"text", text:{body}}`, success 200.
- **Twilio webhook (inbound):** form fields `Body`, `From` (`whatsapp:+E164`), `MessageSid`.
- **Twilio send (outbound):** POST `api.twilio.com/2010-04-01/Accounts/{SID}/Messages.json`, Basic auth (`base64(SID:token)`), form `{From:"whatsapp:<num>", To:"whatsapp:<num>", Body}`, success 201.
- **Env vars:** `WHATSAPP_PROVIDER`; Meta → `META_ACCESS_TOKEN`, `META_PHONE_NUMBER_ID`, `META_VERIFY_TOKEN`; Twilio → `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`.

## Dependencies & assumptions
- `httpx` (async HTTP), `fastapi` (the `Request` type; swappable for any framework exposing `.json()`/`.form()`/`.query_params`).
- Text messages only — media/audio/location are dropped (Meta) or unhandled.
- Each adapter reads its own credentials from env in `__init__`; missing creds → `enviar_mensaje` returns False (logged), doesn't crash.

## To port this, you need:
- [ ] A normalized inbound-message type for your domain (sender id, body, message id, is-echo flag).
- [ ] An abstract interface with `parse_webhook`, `send_message`, and an optional `verify_webhook` default-no-op.
- [ ] A factory keyed off one config/env value, with lazy per-provider imports.
- [ ] One adapter per provider, each owning its parsing, auth scheme, endpoint, and success-code check.
- [ ] A web framework request object (or a thin shim) the adapters can read body/form/query from.

## Gotchas
- **Success codes differ (Meta 200, Twilio 201).** Don't hardcode one check across adapters — each owns its own.
- **Meta's GET challenge must be returned as the raw value** (cast to int here) in the response body, not JSON-wrapped — else verification fails.
- **Strip the `whatsapp:` prefix** off Twilio's `From`/`To` consistently, or memory keys and replies break.
- **No signature/authenticity verification** — add Twilio request-signature validation and Meta payload-signature checks before production; right now anything POSTing to `/webhook` is trusted.
- **Echo loops:** the `es_propio` flag exists to drop messages the bot itself sent; if a provider echoes outbound messages and you don't set/honor this, the bot replies to itself.
- **Media types** are silently ignored (Meta filters `type=="text"`; Twilio assumes `Body`). Decide explicitly if you need them.

## Origin (reference only)
Repo: https://github.com/Hainrixz/whatsapp-agentkit · The adapter code lives inline inside `CLAUDE.md` (§3.3), generated into `agent/providers/{base,__init__,meta|twilio}.py` at build time — only the chosen provider's module is emitted.
