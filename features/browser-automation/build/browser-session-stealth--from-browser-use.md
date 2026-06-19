# Browser Session & Stealth (build spec) — distilled from browser-use

## Summary

A CDP-first browser control layer for an agent: one `BrowserProfile` config compiles Chrome launch args; a `BrowserSession` + event-bus `watchdog` architecture launches/connects/cloud-provisions Chromium, tracks tabs via a `SessionManager`, captures screenshot+DOM in parallel, evades bot detection through launch flags only, waits on externally-signalled CAPTCHAs, routes through proxies (flag + CDP auth), persists cookies/localStorage, and auto-reconnects. Talks CDP over a WebSocket (`cdp_use`), NOT Playwright's API.

## Core logic (inlined)

### Config — `BrowserProfile` (Pydantic; multi-inherits connect/launch/context arg groups)
```
# Connection
cdp_url: str|None            # attach to a running browser instead of launching
use_cloud: bool              # provision via browser-use cloud -> sets cdp_url from response.cdpUrl
cloud_browser_params: { profile_id, proxy_country_code, timeout(1-240min), enable_recording }|None
# Launch
headless: bool|None          # None=auto; adds --headless=new when true
executable_path, channel('chrome'|'chrome-beta'|'msedge'|...), args: list[str],
ignore_default_args, chromium_sandbox(default = not IN_DOCKER),
user_data_dir: str|None      # validator: if None -> tempfile.mkdtemp() (fresh isolated profile!)
profile_directory: str = 'Default'
# Context
storage_state: path|dict|None, viewport: {width,height}|None, no_viewport, user_agent,
permissions: list = ['clipboardReadWrite','notifications'], accept_downloads=True, record_har_path, record_video_dir
# Proxy
proxy: { server: str|None, bypass: str|None, username: str|None, password: str|None }|None
# Stealth / anti-bot
disable_security=False, deterministic_rendering=False, captcha_solver=True
# Navigation policy
allowed_domains, prohibited_domains, block_ip_addresses,
minimum_wait_page_load_time=0.25, wait_for_network_idle_page_load_time=0.5
# iframe / misc
keep_alive, enable_default_extensions, cross_origin_iframes=True, max_iframes=100, max_iframe_depth=5

get_args():  # compile final Chrome CLI
  start CHROME_DEFAULT_ARGS (~48 flags, incl. --disable-blink-features=AutomationControlled
       and AutomationControlled in --disable-features)
  subtract ignore_default_args; append user args
  + CHROME_DOCKER_ARGS if IN_DOCKER or chromium_sandbox=False
  + ['--headless=new'] if headless
  + CHROME_DISABLE_SECURITY_ARGS if disable_security
  + CHROME_DETERMINISTIC_RENDERING_ARGS if deterministic_rendering
  + window size/pos; extension --load-extension/--disable-extensions-except
  + --proxy-server=/--proxy-bypass-list= if proxy.server; + --user-agent= if set
  MERGE all --disable-features= values into ONE deduped flag   # Chrome ignores duplicate flags otherwise
```

### Session start (event-bus + watchdogs)
```
BrowserSession.__init__: accepts every BrowserProfile field as a flat kwarg (or browser_profile=...)
await session.start():  dispatch BrowserStartEvent ->
  attach_all_watchdogs(): Downloads, StorageState(if storage_state), LocalBrowser, Security, AboutBlank,
     Popups, Permissions, DefaultAction, Screenshot, DOM, Recording, HarRecording(if record_har_path), Captcha(if captcha_solver)
     # each watchdog auto-registers its on_<EventName> handlers onto the bus
  acquire browser (mutually exclusive):
     cloud      -> CloudBrowserClient.create_browser(params) -> cdp_url
     local      -> dispatch BrowserLaunchEvent (handled by LocalBrowserWatchdog)
     existing   -> use profile.cdp_url
  await self.connect()
```

### Local launch (`LocalBrowserWatchdog.on_BrowserLaunchEvent`)
```
path = find_installed_browser(): executable_path -> channel -> ~/.cache/ms-playwright/chromium-*/chrome ->
       system paths -> last resort `uvx playwright install chromium`
port = free TCP port
subprocess = create_subprocess_exec(path, *get_args(), f'--remote-debugging-port={port}')  # wrapped in psutil.Process
poll http://127.0.0.1:{port}/json/version until ready
return BrowserLaunchResult(cdp_url='ws://...')
# NOTE: Playwright is only an install fallback — never used to control the browser
```

### Connect (`session.connect`)
```
if cdp_url is HTTP: fetch /json/version -> webSocketDebuggerUrl
cdp_root = TimeoutWrappedCDPClient(cdp_url, max_ws_frame_size=200MB); await cdp_root.start()   # cdp_use.CDPClient
if proxy.username/password: Fetch.enable + on Fetch.authRequired -> Fetch.continueWithAuth(ProvideCredentials) for source=='proxy'
session_manager = SessionManager(self); start_monitoring()
Target.setAutoAttach(autoAttach=True, waitForDebuggerOnStart=False, flatten=True)
discover page targets; redirect chrome://newtab -> about:blank; create about:blank if none; set agent focus
dispatch BrowserConnectedEvent -> StorageState loads cookies/localStorage; Permissions grants; Captcha registers handlers
```

### SessionManager (tab tracking)
```
maps: _targets{TargetID->Target}, _sessions{SessionID->CDPSession}, _target_sessions, _session_to_target
updated by CDP events: Target.attachedToTarget / detachedFromTarget / targetInfoChanged
get_all_page_targets(): target_type in ('page','tab')
on focused target detach: _recover_agent_focus() -> switch to another page or create one
```

### Page state (parallel)
```
get_browser_state_summary(include_screenshot=True) -> dispatch BrowserStateRequestEvent:
  ScreenshotWatchdog: Page.captureScreenshot(format='png', captureBeyondViewport=?) -> base64
  DOMWatchdog: DomService.get_serialized_dom_tree() -> EnhancedDOMTreeNode tree + selector_map  (see indexed-dom build)
-> BrowserStateSummary { dom_state, screenshot, url, title, tabs: list[TabInfo{url,title,target_id,parent_target_id}],
                         page_info, browser_errors, pending_network_requests }
```

### Stealth (FLAGS ONLY — no JS patching, no patchright/playwright-stealth)
```
CHROME_DEFAULT_ARGS includes: --disable-blink-features=AutomationControlled
--disable-features=...,AutomationControlled,...   # both hide navigator.webdriver / automation markers
+ --no-first-run --no-default-browser-check --no-service-autorun --disable-background-networking
  --disable-client-side-phishing-detection --disable-sync --metrics-recording-only
  --disable-domain-reliability --safebrowsing-disable-auto-update --silent-debugger-extension-api
```

### CAPTCHA (external solver — Python only waits)
```
CaptchaWatchdog listens for CDP events BrowserUse.captchaSolverStarted / captchaSolverFinished
  (emitted by a browser-side component in the cdp_use 'BrowserUse' domain — companion extension/proxy, NOT this package)
blocks the agent step via asyncio.Event until solved or timeout (default 120s; env TIMEOUT_CaptchaSolverWait)
-> CaptchaWaitResult { waited, vendor, url, duration_ms, result: 'success'|'failed'|'timeout'|'unknown' }
```

### Proxy (two layers) & storage persistence
```
1) launch flag --proxy-server={server} (+ --proxy-bypass-list); covers unauthenticated proxies
2) authenticated: CDP Fetch.authRequired -> Fetch.continueWithAuth(ProvideCredentials, username, password)
StorageStateWatchdog: on connect load storage_state -> Network.setCookies + Page.addScriptToEvaluateOnNewDocument (localStorage)
  poll every 30s; on change atomic write JSON (.tmp -> rename, .bak backup)
  export_storage_state() -> Storage.getCookies -> Playwright format {cookies:[...], origins:[]}
keep_alive: on BrowserStopEvent if keep_alive and not force -> abort teardown
auto-reconnect: WS-drop callback -> exp backoff (1s,2s,4s), reuse cdp_url, clear stale SessionManager, restore focus
```

## Data contracts
```
BrowserStateSummary: { dom_state: SerializedDOMState, screenshot: str(base64 png), url, title,
                       tabs: list[TabInfo], page_info, browser_errors, pending_network_requests }
TabInfo: { url, title, target_id, parent_target_id }
ProxySettings: { server, bypass, username, password }
CloudBrowserParams: { profile_id, proxy_country_code, timeout, enable_recording }
```

## Dependencies & assumptions
- `cdp_use` (CDP WebSocket client + the browser-side `BrowserUse` CDP domain for captcha events). A generic CDP client works for everything EXCEPT the captcha-event domain, which is browser-use-specific.
- A Chromium/Chrome binary (or a cloud endpoint, or an existing `cdp_url`). `psutil` for subprocess lifecycle.
- An event-bus library (`bubus` here) — swappable for any pub/sub.
- Playwright is OPTIONAL (binary install fallback only).

## To port this, you need:
- [ ] A single config model that compiles Chrome CLI args (default set, conditional Docker/headless/security, merged `--disable-features`).
- [ ] A launch path (find binary -> free port -> `--remote-debugging-port` -> poll `/json/version`) AND a connect path (CDP WS, `Target.setAutoAttach`, target discovery).
- [ ] A session/target manager driven by `Target.attached/detached/infoChanged` with focus recovery.
- [ ] Parallel screenshot (`Page.captureScreenshot`) + DOM capture producing a state summary.
- [ ] Stealth flags (`--disable-blink-features=AutomationControlled` + `AutomationControlled` in `--disable-features`).
- [ ] Proxy: launch flag + `Fetch.authRequired` interceptor for auth.
- [ ] (Optional) storage-state persistence, keep-alive, auto-reconnect, and a captcha-wait hook if you have an external solver.

## Gotchas
- **CDP, not Playwright** — if you reach for `playwright.async_api` to control pages you've diverged from this design; here Playwright only installs the binary.
- **`user_data_dir=None` => fresh temp profile** every run; set it explicitly for persistent logins.
- **Stealth is only as strong as the flags** — no fingerprint spoofing; sophisticated bot detection may still catch it.
- **CAPTCHA solving is external** — the Python side just blocks on an event; without the companion browser component nothing solves.
- **Authenticated proxy needs the `Fetch.authRequired` handler** — the `--proxy-server` flag alone won't supply credentials.
- **Watchdog attach order**: LocalBrowser before `connect()`; StorageState must load on `BrowserConnectedEvent` before first action.
- **`--disable-features` must be merged into one flag** — Chrome silently ignores duplicate `--disable-features` occurrences.
- **200MB max WS frame size** is set deliberately — big DOM/screenshot payloads exceed default CDP frame limits.

## Origin (reference only)
Repo: https://github.com/browser-use/browser-use (`main`). `browser_use/browser/`: `profile.py` (`BrowserProfile`, `get_args`),
`session.py` (`BrowserSession`, `connect`), `session_manager.py`, `views.py` (`BrowserStateSummary`,`TabInfo`),
`events.py`, `watchdog_base.py`, `watchdogs/` (`local_browser_watchdog.py`, `captcha_watchdog.py`, `screenshot_watchdog.py`,
`dom_watchdog.py`, `storage_state_watchdog.py`, `security_watchdog.py`, `permissions_watchdog.py`), `cloud/cloud.py`.
Gaps to verify if reachable: private `_cdp_*` cookie/storage helpers and `DefaultActionWatchdog` internals (file ~4000 lines,
truncated in fetch); the `cdp_use` `BrowserUse` captcha domain internals; default-extension names/URLs; CrashWatchdog (present but disabled).
