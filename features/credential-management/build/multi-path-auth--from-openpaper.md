# Multi-Path Authentication (build spec) — distilled from openpaper

## Summary

Three auth paths over **opaque server-side session tokens** (NOT JWT): Google OAuth2 (login), email
6-digit-code (login), and Zotero OAuth 1.0a (library link, requires existing login). 64-char hex token
in a `sessions` table, 30-day expiry, httpOnly `session_token` cookie; routes resolve user from cookie
OR `Authorization: Bearer`. Cross-provider accounts are **refused, not merged**. Includes several
documented security gaps to fix on port.

## Core logic (inlined)

### Sessions & route protection — `auth/utils.py`, `auth/dependencies.py`

```python
token = secrets.token_hex(32)          # 64-char hex, opaque
# sessions table: {id, user_id(FK CASCADE), token(unique idx), expires_at(tz), user_agent, ip_address}
# expiry: 30 days; no refresh/sliding window found
response.set_cookie("session_token", token, max_age=<secs>, expires=<rfc>,
    domain=SESSION_COOKIE_DOMAIN, path="/", secure=SECURE_COOKIES, httponly=True, samesite="lax")

# dependencies:
get_current_user  -> Optional[CurrentUser]   # Bearer header first, else session_token cookie; None if invalid/expired
get_required_user -> 401 if None
get_admin_user    -> 403 if not is_admin
# CurrentUser{id,email,name,is_admin,picture,is_email_verified,is_active(<-subscription_crud.is_user_active),is_blocked}
```

### (a) Google OAuth2 — `auth/google.py`, `api/auth_api.py`

```python
GET /api/auth/google/login:
    state = secrets.token_urlsafe(32)           # GOTCHA: returned but NEVER verified on callback
    url = google.get_auth_url(state)            # accounts.google.com/o/oauth2/v2/auth
        # scope="openid email profile", access_type=offline, prompt=consent, response_type=code
    return {"auth_url": url}

GET /api/auth/google/callback?code=...:
    tok  = google.get_token(code)               # POST oauth2.googleapis.com/token (code,client_id,secret,redirect_uri)
    info = google.get_user_info(tok.access_token)  # GET googleapis.com/oauth2/v2/userinfo
    if get_by_email(email) under different provider: redirect ?error=different_provider   # refuse-merge
    user = upsert_with_provider(auth_provider="google", provider_user_id=google_id, ...)
    sess = create_session(db, user_id, user_agent, ip_address)
    resp = RedirectResponse(f"{CLIENT_DOMAIN}/auth/callback?success=true[&welcome=true]")
    set_session_cookie(resp, sess.token); return resp
```

### (b) Email verification code — `auth/email.py`, `api/auth_api.py`

```python
POST /api/auth/email/signin {email}:
    email = email.lower().strip()
    if exists under non-email provider: return {success:false, message:...}    # refuse-merge
    user = get or create_email_user(email)   # auth_provider="email", is_email_verified=False
    code = "".join(random.choices(string.digits, k=6))   # GOTCHA: random not secrets; plaintext stored
    expires = now_utc + 10 min
    update_verification_code(user, code, expires)         # writes users.email_verification_token/_expires_at
    email.send_verification_code(email, code)             # HTML+txt templates, {{verification_code}}
    return AuthResponse{success, newly_created, needs_name}

POST /api/auth/email/fullname {email,name}:   # only if email user with null name; no auth
POST /api/auth/email/verify {email, code}:
    ok = is_verification_code_valid(expires_at, code, stored):
         return bool(expires_at) and code==stored and now_utc < expires_at   # plain equality
    if ok: verify_email(user)   # is_email_verified=True, clear token/expiry
           sess = create_session(...)
           return Response(json.dumps({success:true, redirectUrl:...}))  # raw Response so cookie sticks
           set_session_cookie(resp, sess.token)
```

### (c) Zotero OAuth 1.0a (library link, not login) — `auth/zotero.py`

```python
GET /api/auth/zotero/connect  (Depends get_required_user):
    rt = zotero.get_request_token()                 # requests-oauthlib
    zotero_crud.delete_pending_for_user(user_id)
    zotero_crud.create_pending(user_id, rt.oauth_token, rt.oauth_token_secret)   # ZoteroPending, has expires_at
    return {"auth_url": "https://www.zotero.org/oauth/authorize?oauth_token=..."}

GET /api/auth/zotero/callback?oauth_token=&oauth_verifier=   (NO auth dependency):
    pending = zotero_crud.get_by_token(oauth_token)          # identity comes from pending.user_id
    assert pending and now_utc < pending.expires_at
    at = zotero.get_access_token(pending.token, pending.secret, verifier)  # permanent zotero user_id + api_key
    zotero_crud.upsert_connection(pending.user_id, at.userID, at.api_key)
    zotero_crud.delete_pending(...); redirect {CLIENT_DOMAIN}/settings?zotero=connected

GET /api/auth/zotero/status  -> {connected, connected_at, last_synced_at}
DELETE /api/auth/zotero/disconnect
```

## Data contracts

```python
# users (auth-relevant)
{id:UUID, email:str unique, name:str|None, picture:str|None, is_active:bool=True,
 is_admin:bool=False, is_blocked:bool=False, auth_provider:str /*"google"|"email"*/,
 provider_user_id:str /*google sub OR email*/, is_email_verified:bool=False,
 email_verification_token:str|None /*plaintext 6-digit*/, email_verification_expires_at:datetime|None, locale:str|None}
# sessions: {id, user_id, token(unique), expires_at, user_agent, ip_address}
# ZoteroPending: {user_id, oauth_token, oauth_token_secret, expires_at}   (schema inferred)
# ZoteroConnection: {user_id, zotero_user_id, api_key, connected_at, last_synced_at}  (inferred)
```
API shapes: `POST /email/signin {email}` → `{success,message,user,newly_created,needs_name}`;
`POST /email/verify {email,code}` → `{success,message,redirectUrl}` + Set-Cookie;
`GET /google/login` → `{auth_url}`; callbacks → 302 + Set-Cookie / redirect.

## Dependencies & assumptions

- `requests` (Google token/userinfo — no authlib/google-auth), `requests-oauthlib` (Zotero 1.0a),
  `secrets`, `random`+`string`, `fastapi`, `sqlalchemy`, `python-dotenv`. **No JWT lib.**
- **Env:** `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `ZOTERO_CLIENT_KEY`,
  `ZOTERO_CLIENT_SECRET`, `ZOTERO_REDIRECT_URI`, `SESSION_COOKIE_DOMAIN`(opt), `SECURE_COOKIES`(prod=true),
  `CLIENT_DOMAIN`, `API_DOMAIN`. No JWT secret.
- An email sender (`app/helpers/email.py` — transport not traced) + HTML/txt code templates.
- Swappable: providers are independent — drop any one; session store could move to Redis.

## To port this, you need:

- [ ] `users` + `sessions` tables (opaque token, 30-day expiry) and the cookie/Bearer dual resolver.
- [ ] Google OAuth2 login (with a **verified** state param — fix the gap below).
- [ ] Email-code: generate (**use `secrets`**), **hash + store**, rate-limit, verify, mint session.
- [ ] Zotero OAuth 1.0a connect/callback over a pending-tokens table keyed to the logged-in user.
- [ ] A refuse-or-merge decision for cross-provider emails (openpaper refuses).

## Gotchas (several are security bugs to FIX on port)

- **OAuth `state` is never validated** on the Google callback → no CSRF protection. Store state and verify it.
- **Email codes use `random.choices`** (not CSPRNG) and are **stored plaintext** with **no rate limiting** → brute-forceable. Use `secrets`, hash the code, throttle per email/IP.
- **Zotero callback has no auth dependency** — identity rides on the pending record; a stale/wrong pending could link the wrong account (mitigated only by the expiry check).
- **No cross-provider account merge** — same email under two providers = locked out. Decide deliberately.
- **`samesite="lax"`** — cross-origin POST won't send the cookie; use the Bearer path for cross-origin APIs.
- **Single-device logout bug** — reads token from an unset `Set-Cookie` header; only "all devices" works.
- **`is_active` on CurrentUser = subscription status**, not the `users.is_active` column — don't conflate.

## Origin (reference only)

khoj-ai/openpaper @ `master`:
`server/app/auth/README.md`, `auth/google.py`, `auth/email.py`, `auth/zotero.py`, `auth/utils.py`,
`auth/dependencies.py`, `server/app/api/auth_api.py`, `server/app/database/crud/user_crud.py`,
`server/app/database/models.py` (User/Session).

**Gaps to verify:** exact `user_crud` session code (token length/expiry from summary); `ZoteroPending`/
`ZoteroConnection` schemas + pending expiry duration; email transport (SES/SMTP/Resend?);
`upsert_with_provider` edge cases; whether any sliding-expiry/refresh exists.
