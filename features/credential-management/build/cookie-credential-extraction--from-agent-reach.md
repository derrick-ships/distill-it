# Cookie Credential Extraction + Secure Local Store (build spec) — distilled from Agent-Reach

## Summary

Harvest a logged-in browser's cookies and persist them as credentials, securely. Three transplantable parts: (1) a **declarative per-platform spec** (domains + either named cookies or whole-header capture) driving a **multi-browser extractor** with a `rookiepy → browser_cookie3` fallback; (2) **validation-before-save** (reject anonymous/incomplete cookie sets by checking for a logged-in marker, not just presence); (3) an **atomic owner-only write** (`open(O_CREAT, mode=0o600)`, no write-then-chmod race) reused for the canonical store and for best-effort, shell-safe mirrors into each upstream tool's native credential file.

## Core logic (inlined)

### 1. Declarative platform specs + extractor (verbatim core)

```python
# (platform spec) — cookies: list = pull these by name; None = grab WHOLE cookie header
PLATFORM_SPECS = [
    {"name": "Twitter/X",   "domains": [".x.com", ".twitter.com"], "cookies": ["auth_token", "ct0"],   "config_key": "twitter"},
    {"name": "XiaoHongShu", "domains": [".xiaohongshu.com"],       "cookies": None,                     "config_key": "xhs"},
    {"name": "Bilibili",    "domains": [".bilibili.com"],          "cookies": ["SESSDATA", "bili_jct"], "config_key": "bilibili"},
    {"name": "Xueqiu",      "domains": [".xueqiu.com", "xueqiu.com"], "cookies": None,                  "config_key": "xueqiu"},
]


def extract_all(browser: str = "chrome") -> dict[str, dict]:
    """Extract cookies for all specs from one browser.
    Prefer rookiepy (Rust, stabler); fall back to browser_cookie3. Normalize
    both to objects with .name/.value/.domain."""
    use_rookiepy = False
    try:
        import rookiepy; use_rookiepy = True
    except ImportError:
        try:
            import browser_cookie3
        except ImportError:
            raise RuntimeError("Need rookiepy (recommended) or browser_cookie3.")

    browser = browser.lower()
    if browser not in ("chrome", "firefox", "edge", "brave", "opera"):
        raise ValueError(f"Unsupported browser: {browser}")

    if use_rookiepy:
        funcs = {"chrome": rookiepy.chrome, "firefox": rookiepy.firefox, "edge": rookiepy.edge,
                 "brave": rookiepy.brave, "opera": rookiepy.opera}
        raw = funcs[browser]()                        # list[dict] name/value/domain
        class _C:
            def __init__(s, d): s.name, s.value, s.domain = d.get("name",""), d.get("value",""), d.get("domain","")
        jar = [_C(c) for c in raw]
    else:
        funcs = {"chrome": browser_cookie3.chrome, "firefox": browser_cookie3.firefox,
                 "edge": browser_cookie3.edge, "brave": browser_cookie3.brave, "opera": browser_cookie3.opera}
        jar = funcs[browser]()                         # browser may need to be CLOSED

    results = {}
    for spec in PLATFORM_SPECS:
        named, all_for_domain = {}, []
        for c in jar:
            if not any(c.domain.endswith(d) or c.domain == d.lstrip(".") for d in spec["domains"]):
                continue
            all_for_domain.append(c)
            if spec["cookies"] is not None and c.name in spec["cookies"]:
                named[c.name] = c.value
        if spec["cookies"] is None:                    # whole-header mode
            if all_for_domain:
                results[spec["config_key"]] = {"cookie_string":
                    "; ".join(f"{c.name}={c.value}" for c in all_for_domain)}
        elif named:                                    # named-cookie mode
            results[spec["config_key"]] = named
    return results
```

### 2. The atomic owner-only write (the security primitive — reuse everywhere a secret is saved)

```python
def _open_owner_only(path: str):
    """Open for writing, atomically creating with mode 0o600.
    O_CREAT + explicit mode means the file is NEVER briefly world-readable
    (unlike write-then-chmod). Falls back to plain open() on Windows."""
    import os, stat
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                     stat.S_IRUSR | stat.S_IWUSR)       # 0o600
        return os.fdopen(fd, "w", encoding="utf-8")
    except OSError:
        return open(path, "w", encoding="utf-8")
```

The canonical YAML store uses the same pattern inline:

```python
def save(self):
    import os, stat, yaml
    try:
        fd = os.open(str(self.config_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                     stat.S_IRUSR | stat.S_IWUSR)       # 0o600 from the first byte
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.dump(self.data, f, default_flow_style=False, allow_unicode=True)
    except OSError:                                      # Windows / unsupported flags
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.dump(self.data, f, default_flow_style=False, allow_unicode=True)
```

### 3. Validate-before-save + report (reject anonymous/incomplete sets)

```python
def configure_from_browser(browser: str, config) -> list[tuple[str, bool, str]]:
    """Extract + save; return (platform, success, message) per platform."""
    try:
        extracted = extract_all(browser)
    except Exception as e:
        return [("Browser", False, str(e))]
    if not extracted:
        return [("All", False, f"No platform cookies in {browser}. Log into the sites first.")]

    out = []
    if "twitter" in extracted:
        tc = extracted["twitter"]
        if "auth_token" in tc and "ct0" in tc:          # BOTH required
            config.set("twitter_auth_token", tc["auth_token"])
            config.set("twitter_ct0", tc["ct0"])
            _sync_xfetch_session(tc["auth_token"], tc["ct0"])   # best-effort mirror
            _sync_bird_env(tc["auth_token"], tc["ct0"])         # best-effort mirror
            out.append(("Twitter/X", True, "auth_token + ct0"))
        else:
            missing = [k for k in ("auth_token", "ct0") if k not in tc]
            out.append(("Twitter/X", False, f"missing: {', '.join(missing)} — log into x.com"))

    if "xueqiu" in extracted:
        s = extracted["xueqiu"].get("cookie_string", "")
        if s and "xq_a_token" in s:                     # logged-in MARKER, not mere presence
            config.set("xueqiu_cookie", s)
            out.append(("Xueqiu", True, f"{len(s.split(';'))} cookies (incl. xq_a_token)"))
        elif s:
            out.append(("Xueqiu", False, "found cookies but no xq_a_token — log into xueqiu.com first"))
    # ... xhs (whole-header) and bilibili (SESSDATA required) follow the same shape
    return out
```

### 4. Shell-safe mirror into an upstream tool's `.env`

```python
def _sync_bird_env(auth_token: str, ct0: str) -> None:
    """Write a shell-sourceable credentials.env. shlex.quote so a token with a
    quote/$/backtick can't break out into shell when the file is `source`d."""
    import os, shlex
    try:
        d = os.path.join(os.path.expanduser("~"), ".config", "bird"); os.makedirs(d, exist_ok=True)
        with _open_owner_only(os.path.join(d, "credentials.env")) as f:
            f.write(f"AUTH_TOKEN={shlex.quote(auth_token)}\n")
            f.write(f"CT0={shlex.quote(ct0)}\n")
    except Exception:
        pass        # best-effort: agent-reach config is the source of truth
```

### 5. Config reads: file over env, masked dumps

```python
def get(self, key, default=None):
    if key in self.data:
        return self.data[key]
    env_val = os.environ.get(key.upper())               # CONFIG file first, then UPPERCASE env
    return env_val if env_val else default

def to_dict(self):                                       # masked view (logging-safe)
    return {k: (f"{str(v)[:8]}..." if v else None)
               if any(s in k.lower() for s in ("key","token","password","proxy")) else v
            for k, v in self.data.items()}
```

## Data contracts

```
PLATFORM_SPEC = { name:str, domains:list[str], cookies:list[str]|None, config_key:str }
  cookies=list  → named-cookie mode: extract those names → {name: value}
  cookies=None  → whole-header mode: join ALL domain cookies → {"cookie_string": "k=v; k=v; ..."}

extract_all(browser) -> { config_key: {cookie names→values}  |  {"cookie_string": "..."} }
configure_from_browser(browser, config) -> list[ (platform:str, success:bool, message:str) ]

Saved config keys (examples): twitter_auth_token, twitter_ct0, xhs_cookie,
  bilibili_sessdata, bilibili_csrf, xueqiu_cookie
File: ~/.agent-reach/config.yaml  (mode 0o600, created atomically)
Validation markers (presence ≠ valid): twitter needs auth_token AND ct0; xueqiu needs xq_a_token in string
Mirrors (best-effort): ~/.config/xfetch/session.json (JSON), ~/.config/bird/credentials.env (shell, shlex-quoted)
```

## Dependencies & assumptions

- `rookiepy` (preferred) or `browser_cookie3` for reading the browser cookie DB; `pyyaml` for the store. Both cookie libs read on-disk cookie stores — **the browser usually must be closed**, and the OS keychain/Keyring may prompt.
- POSIX for the atomic `0o600` create; a plain-`open` fallback covers Windows (where the file is *not* protected this way — accept that or use Windows ACLs).
- `shlex` (stdlib) for the `.env` mirror; `os`/`stat` (stdlib) for the secure write.
- Assumes the user is genuinely logged into the target sites in the chosen browser; otherwise you get anonymous cookies (which validation should reject).

## To port this, you need:

- [ ] A declarative spec list (domains + named-cookies-or-whole-header + a storage key) so adding a platform is data, not code.
- [ ] The extractor with `rookiepy → browser_cookie3` fallback, normalized to `.name/.value/.domain`.
- [ ] `_open_owner_only` (atomic `O_CREAT|mode=0o600`) and route EVERY secret write through it — never write-then-chmod.
- [ ] Validate-before-save: require the platform's logged-in marker (e.g. `auth_token`+`ct0`, `xq_a_token`) before persisting; return a precise per-platform `(name, ok, message)`.
- [ ] `get()` that layers config-file over uppercase env vars; a masked `to_dict()` for safe logging.
- [ ] (If other tools read the creds) best-effort mirrors into their native formats, each wrapped in `try/except: pass`, with `shlex.quote` on anything written to a shell-sourced file.

## Gotchas

- **Write-then-chmod has a race; don't.** Between `open()` and `chmod()` the secret file is world-readable. `os.open(..., O_CREAT, 0o600)` creates it protected from byte zero. This is the single most important line here.
- **Presence is not validity.** Anonymous cookies exist for logged-out sessions; saving them produces a credential that fails later in a confusing way. Gate on a logged-in marker token.
- **Named vs whole-header is not a style choice** — it's dictated by what the consuming tool expects. Getting it wrong yields creds the tool silently can't use.
- **`shlex.quote` the `.env`.** A `source`d file is executable shell; an unquoted `$`/backtick/quote in a token is an injection. (Twitter `ct0` values can contain unusual characters.)
- **Mirrors must never break the main save.** Wrap each in `try/except: pass`; the canonical store is the system of record.
- **Browser must usually be closed**, and OS keychain access can prompt — surface a clear error ("make sure {browser} is closed and you're logged in") rather than a raw traceback.
- **Recommend a secondary/throwaway account** for cookie auth: cookies = full account access, and platforms may ban detected automation. Limits blast radius on leak.

## Origin (reference only)

Repo: https://github.com/Panniantong/Agent-Reach
Key files: `agent_reach/cookie_extract.py` (`PLATFORM_SPECS`, `extract_all`, `configure_from_browser`, `_open_owner_only`, `_sync_xfetch_session`, `_sync_bird_env` with `shlex.quote`); `agent_reach/config.py` (`Config.save` atomic 0o600 write, `get` env-fallback, `to_dict` masking, `FEATURE_REQUIREMENTS`/`is_configured`). Entry: `agent-reach configure --from-browser chrome` and `agent-reach configure twitter-cookies "..."`. Security guidance (secondary account, Cookie-Editor import) lives in `docs/install.md`.
