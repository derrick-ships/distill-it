# Agent Dashboard (build spec) — distilled from Serena

## Summary
Build a live monitoring dashboard for an AI agent, served as a Flask REST API in a background thread alongside the agent process. Captures log output in an in-memory ring buffer. Exposes agent state (config, tool stats, active project, memories, queued tasks) via JSON endpoints consumed by a single-page frontend. Adapts display mode (browser tab / native webview / system-tray aggregator) to the running platform.

## Core logic (inlined)

### In-memory log handler
```python
import logging
from collections import deque
from threading import Lock

class MemoryLogHandler(logging.Handler):
    def __init__(self, maxlen: int = 5000):
        super().__init__()
        self._buffer: deque[dict] = deque(maxlen=maxlen)
        self._lock = Lock()
        self._seq = 0

    def emit(self, record: logging.LogRecord):
        with self._lock:
            self._seq += 1
            self._buffer.append({
                "seq":     self._seq,
                "level":   record.levelname,
                "time":    self.formatTime(record),
                "message": self.format(record),
                "logger":  record.name,
            })

    def get_since(self, after_seq: int) -> list[dict]:
        with self._lock:
            return [m for m in self._buffer if m["seq"] > after_seq]

    def clear(self):
        with self._lock:
            self._buffer.clear()
```

### Flask dashboard API
```python
from flask import Flask, jsonify, request
import threading, socket

class DashboardAPI:
    def __init__(self, agent, log_handler: MemoryLogHandler,
                 tool_stats, memory_manager, base_port: int = 9020):
        self.agent = agent
        self.log_handler = log_handler
        self.tool_stats = tool_stats
        self.memory_manager = memory_manager
        self.port = self._find_free_port(base_port)
        self.app = Flask(__name__)
        self._register_routes()

    def _find_free_port(self, start: int) -> int:
        for port in range(start, start + 100):
            try:
                s = socket.socket(); s.bind(("127.0.0.1", port)); s.close()
                return port
            except OSError:
                continue
        raise RuntimeError("No free port found")

    def _register_routes(self):
        app = self.app

        @app.get("/logs")
        def get_logs():
            after = int(request.args.get("after", 0))
            active_project = self.agent.active_project_name
            messages = self.log_handler.get_since(after)
            return jsonify({
                "messages": messages,
                "last_seq": messages[-1]["seq"] if messages else after,
                "active_project": active_project,
            })

        @app.delete("/logs")
        def clear_logs():
            self.log_handler.clear()
            return jsonify({"ok": True})

        @app.get("/tools/stats")
        def tool_stats():
            return jsonify(self.tool_stats.to_dict())

        @app.delete("/tools/stats")
        def clear_tool_stats():
            self.tool_stats.reset()
            return jsonify({"ok": True})

        @app.get("/config")
        def config_overview():
            return jsonify({
                "active_project":      self.agent.active_project_name,
                "active_modes":        self.agent.active_mode_names,
                "active_context":      self.agent.context_name,
                "active_tools":        self.agent.active_tool_names,
                "registered_projects": self.agent.registered_project_names,
            })

        @app.get("/memories")
        def list_memories():
            return jsonify(self.memory_manager.list_memories())

        @app.post("/memories")
        def write_memory():
            data = request.get_json(force=True)
            self.memory_manager.write(data["name"], data["content"])
            return jsonify({"ok": True})

        @app.delete("/memories/<path:name>")
        def delete_memory(name):
            self.memory_manager.delete(name)
            return jsonify({"ok": True})

        @app.post("/memories/<path:name>/rename")
        def rename_memory(name):
            data = request.get_json(force=True)
            self.memory_manager.rename(name, data["new_name"])
            return jsonify({"ok": True})

        @app.post("/shutdown")
        def shutdown():
            threading.Thread(target=self.agent.shutdown, daemon=True).start()
            return jsonify({"ok": True})

    def run_in_thread(self) -> tuple[threading.Thread, int]:
        t = threading.Thread(
            target=lambda: self.app.run(host="127.0.0.1", port=self.port,
                                        use_reloader=False, debug=False),
            daemon=True
        )
        t.start()
        return t, self.port
```

### Platform-adaptive display mode
```python
import platform, webbrowser, subprocess, os

class DashboardMode:
    BROWSER = "browser"
    WEBVIEW = "webview"
    TRAY = "tray"

def default_mode_for_platform() -> str:
    if platform.system() == "Windows":
        return DashboardMode.WEBVIEW
    return DashboardMode.BROWSER   # macOS and Linux

class DashboardManager:
    def __init__(self, url: str, port: int, mode: str | None = None,
                 icon_path: str | None = None):
        self.url = url
        self.port = port
        self.mode = mode or default_mode_for_platform()
        self.icon_path = icon_path

    def open(self):
        if self.mode == DashboardMode.BROWSER:
            webbrowser.open(self.url)
        elif self.mode == DashboardMode.WEBVIEW:
            self._open_webview()
        elif self.mode == DashboardMode.TRAY:
            self._register_with_tray()

    def _open_webview(self):
        # Spawn a subprocess running: python -m webview_runner --url URL --icon ICON
        # pywebview must be installed; falls back to browser if not available
        try:
            import pywebview  # noqa: verify importable
            subprocess.Popen(
                ["python", "-m", "serena.webview_runner",
                 "--url", self.url, "--icon", self.icon_path or ""],
                start_new_session=True
            )
        except ImportError:
            webbrowser.open(self.url)

    def _register_with_tray(self):
        import requests
        try:
            requests.post("http://127.0.0.1:9042/register", json={
                "port": self.port,
                "url":  self.url,
                "pid":  os.getpid(),
            }, timeout=2)
        except Exception:
            # Tray manager not running — fall back to browser
            webbrowser.open(self.url)
```

### Tray manager (multi-instance aggregator)
```python
import threading, time, requests, os
from flask import Flask

TRAY_PORT = 9042

class TrayManager:
    """Singleton Flask app managing multiple Serena instances via system tray."""

    def __init__(self):
        self._instances: dict[int, dict] = {}  # port → instance info
        self._lock = threading.Lock()
        self.app = Flask(__name__)
        self._setup_routes()

    def _setup_routes(self):
        @self.app.post("/register")
        def register():
            data = request.get_json(force=True)
            with self._lock:
                self._instances[data["port"]] = {
                    "port":    data["port"],
                    "url":     data["url"],
                    "pid":     data.get("pid"),
                    "project": data.get("project", "unknown"),
                    "started": data.get("started", time.time()),
                }
            self._refresh_tray_menu()
            return jsonify({"ok": True})

        @self.app.get("/instances")
        def list_instances():
            return jsonify(list(self._instances.values()))

    def _is_alive(self, instance: dict) -> bool:
        pid = instance.get("pid")
        if pid:
            try:
                os.kill(pid, 0)  # signal 0 = existence check
                return True
            except ProcessLookupError:
                return False
        # fallback: HTTP heartbeat
        try:
            requests.get(f"http://127.0.0.1:{instance['port']}/config",
                         timeout=1)
            return True
        except Exception:
            return False

    def cleanup_dead_instances(self):
        with self._lock:
            dead = [p for p, inst in self._instances.items()
                    if not self._is_alive(inst)]
            for p in dead:
                del self._instances[p]
        if dead:
            self._refresh_tray_menu()

    def _refresh_tray_menu(self):
        # Rebuild the pystray menu. One item per live instance.
        # Clicking opens that instance's URL in the browser.
        # Implementation depends on pystray / rumps (macOS) / other.
        pass

    def run_cleanup_loop(self, interval: int = 30):
        def loop():
            while True:
                time.sleep(interval)
                self.cleanup_dead_instances()
        threading.Thread(target=loop, daemon=True).start()

    def start(self):
        self.run_cleanup_loop()
        self.app.run(host="127.0.0.1", port=TRAY_PORT,
                     use_reloader=False, debug=False)
```

### News with ETag caching
```python
import json, time
from pathlib import Path

class NewsFeed:
    def __init__(self, news_url: str, cache_path: Path):
        self.news_url = news_url
        self.cache_path = cache_path
        self._etag: str | None = None
        self._cached: list[dict] = []

    def fetch_background(self):
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        import requests
        headers = {}
        if self._etag:
            headers["If-None-Match"] = self._etag
        try:
            r = requests.get(self.news_url, headers=headers, timeout=10)
            if r.status_code == 304:
                return  # nothing changed
            if r.status_code == 200:
                self._etag = r.headers.get("ETag")
                self._cached = r.json()
                self.cache_path.write_text(json.dumps(self._cached))
        except Exception:
            pass  # silently use stale cache

    def get(self) -> list[dict]:
        if not self._cached and self.cache_path.exists():
            self._cached = json.loads(self.cache_path.read_text())
        return self._cached
```

## Data contracts

**Log message**
```json
{
  "seq": 1042,
  "level": "INFO",
  "time": "2025-06-19 14:32:01",
  "message": "[find_symbol] Found 3 results for 'PaymentService/charge'",
  "logger": "serena.tools.symbol_tools"
}
```

**GET /logs response**
```json
{
  "messages": [ ...log dicts... ],
  "last_seq": 1042,
  "active_project": "my-app"
}
```

**GET /config response**
```json
{
  "active_project": "my-app",
  "active_modes": ["code", "debug"],
  "active_context": "claude-code",
  "active_tools": ["find_symbol", "replace_symbol_body", "..."],
  "registered_projects": ["my-app", "shared-lib"]
}
```

**Tray register payload**
```json
{
  "port": 9021,
  "url": "http://127.0.0.1:9021/dashboard/index.html",
  "pid": 98234,
  "project": "my-app"
}
```

## Dependencies & assumptions

- `flask` — REST API server
- `pywebview` — native window on Windows (optional; falls back to browser if missing)
- `pystray` or `rumps` (macOS) — system tray integration (only for TRAY mode)
- `requests` — for news fetching and tray registration
- Python's standard `logging` module — all agent logs must flow through it
- The dashboard must be launched *before* or *concurrent with* the agent starting, so early-startup logs are captured
- Single-machine only — the dashboard binds to `127.0.0.1`; not designed for remote access

## To port this, you need:
- [ ] `MemoryLogHandler` wired into your agent's root logger at startup (before anything else logs)
- [ ] `DashboardAPI` instantiated with a reference to the live agent, log handler, tool stats collector, and memory manager
- [ ] `run_in_thread()` called after agent init, before MCP server starts accepting requests
- [ ] A `GET /logs?after=<seq>` endpoint so the frontend can long-poll efficiently
- [ ] A static SPA (HTML/JS) served from Flask's `static_folder` at `/dashboard/index.html` — the API and frontend can be in the same Flask app
- [ ] `DashboardManager` deciding browser/webview/tray and opening the URL after the server is ready
- [ ] For tray mode: a separate always-on process running `TrayManager` on a fixed port (e.g. 9042); agents register on startup and the tray manages the menu

## Gotchas

**Flask debug mode + threading.** Always set `use_reloader=False` and `debug=False` when running Flask in a background thread. The reloader spawns subprocesses that will crash in daemon-thread context.

**Port race conditions.** The free-port scan (try bind → increment) has a TOCTOU race: another process could grab the port between your scan and Flask starting. It's acceptable in practice (ports 9020–9120 are usually quiet on dev machines) but retry on `Address in use` at Flask startup to be safe.

**Log buffer size.** An unbounded buffer will OOM on long sessions. Use `deque(maxlen=5000)` or similar. The frontend should paginate using sequence numbers, not load everything at once.

**pywebview subprocess.** Don't run `pywebview.start()` in the same process as your agent if the agent uses asyncio or heavy threading — pywebview has its own event loop that conflicts. The subprocess pattern (spawn a tiny wrapper script) is cleaner.

**Tray health check: PID vs HTTP.** On Linux in Docker/container contexts, PID-based checks can give false positives (PID reuse). The HTTP heartbeat fallback is more reliable but slower. Use PID first, HTTP as fallback.

**CORS.** If your frontend is served from a different origin than the API (unlikely since they're both `127.0.0.1:<port>`), you'll need `flask-cors`. Avoid it by serving the SPA from the same Flask app.

**News ETag invalidation.** Store the ETag alongside the cached JSON so it survives process restarts. Without persistence, every agent restart refetches the full news feed.

## Origin (reference only)
Repo: https://github.com/oraios/serena — files `src/serena/dashboard.py` (SerenaDashboardAPI, SerenaDashboardViewer, SerenaDashboardTrayManager), `src/serena/gui_log_viewer.py` (GuiLogViewer, GuiLogViewerHandler), `src/serena/agent.py` (DashboardManager, startup integration). The frontend SPA lives in `src/serena/resources/`. Main classes: `SerenaDashboardAPI` (Flask app), `SerenaDashboardTrayManager` (multi-instance aggregator).
