# Ordered Backend Routing (build spec) — distilled from Agent-Reach

## Summary

A pattern for making a "capability" (e.g. "read Twitter", "convert a file", "send a notification") resilient to its underlying providers rotting. Model each capability as a **Channel** that owns an **ordered list of candidate backends** (preferred first, fallbacks after). To use the capability, probe each backend's *live* health and select the first one that is fully healthy (`ok`); only if none are healthy fall back to the first merely-degraded one (`warn`). Record which backend won as `active_backend`. Selecting a fallback is a data operation (reorder a list / read a config override), never a code change. Transplanting this means copying the `Channel` ABC, the two-phase `check()`/selection rule, and the override logic — the per-platform backend bodies are yours to write.

## Core logic (inlined)

### The Channel base class (verbatim, the load-bearing abstraction)

```python
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple


class Channel(ABC):
    """Base class for all channels (a 'channel' = one capability/platform)."""

    name: str = ""                    # e.g. "twitter"
    description: str = ""             # human label
    backends: List[str] = []          # ORDERED candidates — backends[0] = preferred
    tier: int = 0                     # 0=zero-config, 1=needs free key/login, 2=needs setup

    #: Backend currently serving this channel; set by check(), None = unavailable.
    active_backend: Optional[str] = None

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """Does this channel own this URL? (used to route a URL to a channel)"""
        ...

    def ordered_backends(self, config=None) -> List[str]:
        """Candidate backends in probe order, honoring a user override.

        Config key `<channel>_backend` (env `<CHANNEL>_BACKEND`) moves the named
        backend to the FRONT. Unknown override values are IGNORED so a stale/typo'd
        pin can never hide every working backend.
        """
        candidates = list(self.backends)
        override = config.get(f"{self.name}_backend") if config else None
        if override:
            for i, b in enumerate(candidates):
                if b == override or b.startswith(override):
                    candidates.insert(0, candidates.pop(i))
                    break
        return candidates

    def check(self, config=None) -> Tuple[str, str]:
        """Return (status, message); status ∈ {'ok','warn','off','error'}.
        Subclasses with real backends must override this and set self.active_backend.
        The default trivially marks the preferred backend active (for zero-config
        channels that are always available, e.g. a built-in HTTP fetch)."""
        self.active_backend = self.backends[0] if self.backends else "builtin"
        return "ok", (", ".join(self.backends) if self.backends else "builtin")
```

### The two-phase selection rule (the actual innovation), from the Twitter channel

The non-obvious part is **collect ALL findings first, then prefer `ok` over `warn` regardless of list position.** A naive `for backend: if usable: return` loop lets a logged-out-but-installed preferred backend mask a fully-working fallback.

```python
def check(self, config=None):
    """Probe candidates in order; first fully-usable backend wins.
    Two-phase: collect every candidate's status, then the first `ok` wins;
    only if there is no `ok` does the first `warn` win — otherwise an
    installed-but-unauthenticated preferred backend would hide a later,
    fully-working fallback."""
    self.active_backend = None
    findings = []  # list of (backend, status, message)

    for backend in self.ordered_backends(config):
        result = self._probe_backend(backend)   # returns None | (status, message)
        if result is None:
            continue                              # not installed → not a candidate
        findings.append((backend, *result))

    # Phase 2: priority selection. ok beats warn beats nothing.
    for wanted in ("ok", "warn"):
        for backend, status, message in findings:
            if status == wanted:
                self.active_backend = backend
                return status, message

    if findings:                                  # only broken/timeout left
        return "error", "\n".join(m for _, _, m in findings)

    return "warn", "No backend installed. Install one of: " + ", ".join(self.backends)
```

### A concrete backend probe (status is read from OUTPUT, not just exit code)

```python
from agent_reach.probe import probe_command   # see channel-health-diagnostics feature

def _check_twitter_cli(self):
    """Return None if not installed, else (status, message).
    `twitter status` is the health signal: prints "ok: true" when logged in,
    exits non-zero with "not_authenticated" when not — the tool is alive, so
    classify by OUTPUT, not exit code."""
    probe = probe_command("twitter", ["status"], timeout=15, retries=1, package="twitter-cli")
    if probe.status == "missing":
        return None                                  # not a candidate at all
    if probe.status == "broken":
        return "error", "twitter-cli exists but won't execute.\n" + probe.hint
    if probe.status == "timeout":
        return "error", "twitter-cli health check timed out (retried once).\n" + probe.hint
    out = probe.output
    if "ok: true" in out:
        return "ok",   "twitter-cli fully usable (search, read, timeline, threads)"
    if "not_authenticated" in out:
        return "warn", "twitter-cli installed but NOT authenticated. Set TWITTER_AUTH_TOKEN/TWITTER_CT0 or log into x.com in your browser."
    return "warn", "twitter-cli installed but auth check inconclusive."
```

### Registry + how the rest of the system reads the result

```python
# channels/__init__.py
def get_all_channels() -> list[Channel]:
    return [TwitterChannel(), RedditChannel(), GitHubChannel(), ...]  # ordered list of singletons

# A consumer (the doctor / the agent) reads active_backend after check():
status, message = ch.check(config)
active = ch.active_backend           # e.g. "OpenCLI" — which backend is live RIGHT NOW
```

## Data contracts

```
Channel (per capability):
  name: str                 # stable id, also the override key prefix
  description: str
  backends: list[str]       # ORDERED; [0] preferred, rest fallbacks (display names)
  tier: int                 # 0 zero-config | 1 free key/login | 2 complex setup
  active_backend: str|None  # set by check(); the backend serving NOW (None = down)

check(config) -> (status, message)
  status: "ok"    backend fully usable
        | "warn"  installed but needs login/config (usable as last resort)
        | "off"   nothing installed
        | "error" installed but broken/timeout

per-backend probe -> None | (status, message)
  None = not installed → excluded from candidates entirely

Selection precedence: first "ok" in list order → else first "warn" → else "error"/"off"

Override: config["<name>_backend"] or env["<NAME>_BACKEND"]
  → matching backend moved to front; unknown value ignored
```

## Dependencies & assumptions

- A config object exposing `get(key)` that also falls back to uppercase env vars (see cookie-credential-extraction feature for one).
- A health-probe primitive that distinguishes missing / broken / timeout / ok by *executing* a side-effect-free command (see [[channel-health-diagnostics--from-agent-reach]]). **`which()`-style existence checks are insufficient** and will misreport stale installs as healthy.
- Backends are external CLIs/tools here, but the pattern is identical for in-process providers — `_probe_backend` just becomes "try to construct/ping the provider."
- Display names in `backends` are human strings ("bird CLI (legacy)"); the probe body maps each name to a concrete check. Keep that mapping in one place per channel.

## To port this, you need:

- [ ] A `Channel`/capability ABC with `name`, ordered `backends`, `tier`, mutable `active_backend`.
- [ ] `ordered_backends(config)` applying the `<name>_backend` override with **unknown-value-ignored** semantics.
- [ ] A two-phase `check()`: collect all candidate findings, then select `ok` → `warn` → error/off by precedence (NOT first-non-missing).
- [ ] Per-backend probes that return `None` for "not installed" so it's excluded, and classify the rest by inspecting real output.
- [ ] A registry (`get_all_channels()`) returning singletons, and consumers that read `active_backend` after `check()`.
- [ ] (If backends are external tools) the health-probe primitive that executes rather than stats the binary.

## Gotchas

- **The #1 mistake: `for b in backends: if installed(b): return b`.** This stops at the first *installed* backend even when it's only `warn` and a later backend is `ok`. You MUST collect everything then prefer `ok`. This is the whole point.
- **Existence ≠ health.** `shutil.which()` finds a stale venv shim that can't execute. Always run a cheap command. (Exit codes 126/127 = "found but not executable.")
- **Classify by output, not exit code, for "logged out."** Tools commonly exit non-zero when unauthenticated though they're perfectly installed; treat that as `warn`, not `error`, or your self-repair guidance is wrong ("reinstall" vs "log in").
- **Reset `active_backend` at the top of `check()`.** Channels are reused singletons; a stale active backend from a previous run must not leak into a later failed check. Set it to `None` first.
- **Ignore unknown overrides.** If you honor an arbitrary `<name>_backend` value by inserting it, a typo silently disables the platform. Only reorder when the value matches a known backend.
- **Probes must be side-effect-free.** Retries re-run the command verbatim with no backoff; a non-idempotent "backend check" would repeat its effect. Use `--version`/`status`/`check`, never an action.

## Origin (reference only)

Repo: https://github.com/Panniantong/Agent-Reach
Key files: `agent_reach/channels/base.py` (the `Channel` ABC + `ordered_backends`), `agent_reach/channels/twitter.py` (canonical two-phase `check()` with three backends), `agent_reach/channels/__init__.py` (`get_all_channels()` registry), `agent_reach/probe.py` (the health primitive). Backend display names appear in `docs/install.md` and `SKILL.md`; `agent-reach doctor --json` exposes `active_backend` per channel.
