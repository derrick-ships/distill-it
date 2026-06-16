# Channel Health Diagnostics (build spec) — distilled from Agent-Reach

## Summary

Two transplantable pieces. (1) **`probe_command`** — a primitive that answers "is this CLI actually usable?" by *executing* a side-effect-free command and classifying the result into `ok | missing | broken | timeout | error`, distinguishing the three failure modes that `which()` cannot (not-on-PATH vs. on-PATH-but-won't-run vs. runs-but-misbehaves). (2) **`doctor`** — an aggregator that runs every component's self-check, survives any single component throwing, groups results by setup tier, annotates which backend is live when there's a choice, summarizes inactive optionals into one nudge, and tacks on a credentials-file permission audit. Copy `probe_command` verbatim; adapt `doctor` to your component registry.

## Core logic (inlined)

### 1. The probe primitive (verbatim — copy as-is)

```python
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional, Sequence

#: Exit codes shells use for "found but not executable" / "not found".
_BROKEN_EXIT_CODES = (126, 127)


@dataclass
class ProbeResult:
    status: str  # "ok" | "missing" | "broken" | "timeout" | "error"
    output: str = ""
    hint: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def reinstall_hint(package: str) -> str:
    """Prescription for a broken (stale-venv) CLI install."""
    return (
        f"Command exists but cannot execute — usually the venv interpreter went "
        f"missing after a system Python upgrade. Reinstall to fix:\n"
        f"  uv tool install --force {package}\n"
        f"or: pipx reinstall {package}"
    )


def probe_command(
    cmd: str,
    args: Sequence[str] = ("--version",),
    timeout: int = 10,
    retries: int = 0,
    package: Optional[str] = None,
) -> ProbeResult:
    """Actually execute `cmd *args` and classify the result.

    SIDE-EFFECT-FREE health probes ONLY (version/status commands): retries
    re-run the command verbatim with no backoff, so a non-idempotent command
    would repeat its effect.

    package: pip/pipx package name used in the broken-install hint (defaults to cmd).
    """
    path = shutil.which(cmd)
    if not path:
        return ProbeResult("missing")           # not on PATH at all

    last: Optional[ProbeResult] = None
    for _ in range(retries + 1):
        last = _run_once(path, args, timeout, package or cmd)
        if last.ok:
            return last
        # missing/broken can't heal between retries — only timeout/error are transient
        if last.status in ("missing", "broken"):
            return last
    return last


def _run_once(path: str, args: Sequence[str], timeout: int, package: str) -> ProbeResult:
    try:
        r = subprocess.run(
            [path, *args],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            # NOTE: original forces a UTF-8 subprocess env; supply your own if on Windows.
        )
    except FileNotFoundError:
        # which() found it but exec failed: the shebang interpreter is gone.
        return ProbeResult("broken", hint=reinstall_hint(package))
    except OSError:
        return ProbeResult("broken", hint=reinstall_hint(package))
    except subprocess.TimeoutExpired:
        return ProbeResult("timeout", hint=f"`{path}` timed out (>{timeout}s)")

    if r.returncode in _BROKEN_EXIT_CODES:           # 126/127
        return ProbeResult("broken", hint=reinstall_hint(package))

    output = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        return ProbeResult("error", output=output.strip())
    return ProbeResult("ok", output=output.strip())
```

### 2. The aggregator (the key idea: survive any component throwing)

```python
def check_all(config) -> dict[str, dict]:
    """Check all channels; a single misbehaving channel must NEVER take the
    whole report down, so per-channel exceptions degrade to status='error'."""
    results = {}
    for ch in get_all_channels():
        try:
            status, message = ch.check(config)
            active = getattr(ch, "active_backend", None)
        except Exception as e:                       # noqa: BLE001 — doctor must survive any channel
            # Channels are registry singletons: a stale active_backend from a
            # previous check must NOT leak into an errored result.
            status, message, active = "error", f"check failed: {e}", None
        results[ch.name] = {
            "status": status, "name": ch.description, "message": message,
            "tier": ch.tier, "backends": ch.backends, "active_backend": active,
        }
    return results
```

### 3. The report (tiering, active-backend annotation, summary nudge, security audit)

```python
def _name_msg(r: dict) -> str:
    """One channel line; show the active backend ONLY when there's a choice."""
    text = f"{r['name']} — {r['message']}"
    active = r.get("active_backend")
    if active and len(r.get("backends", [])) > 1:    # >1 backend ⇒ annotation is useful
        text += f"  (current backend: {active})"
    return text


def format_report(results: dict[str, dict]) -> str:
    lines = ["Health", "=" * 40,
             "Legend: OK=usable  [!]=installed but needs config/login  [X]=not installed"]
    ok_count = sum(1 for r in results.values() if r["status"] == "ok")
    total = len(results)

    # Tier 0 — zero config: list every one with its status icon.
    lines += ["", "Works out of the box:"]
    for r in (r for r in results.values() if r["tier"] == 0):
        icon = {"ok": "OK ", "warn": "[!]", "off": "[X]", "error": "[X]"}[r["status"]]
        lines.append(f"  {icon} {_name_msg(r)}")

    # Tiers 1 & 2 — only LIST the active ones; summarize the rest in one line.
    optional = [r for r in results.values() if r["tier"] in (1, 2)]
    active   = [r for r in optional if r["status"] == "ok"]
    inactive = [r for r in optional if r["status"] != "ok"]
    if active:
        lines += ["", "Optional channels (installed):"]
        lines += [f"  OK  {_name_msg(r)}" for r in active]

    lines += ["", f"Status: {ok_count}/{total} channels available"]
    if inactive:
        names = ", ".join(r["name"] for r in inactive)
        lines.append(f"{len(inactive)} more optional channels available ({names}) — "
                     f"tell your agent 'install XXX'")

    # Security audit: credentials file permissions (Unix only).
    import os, stat, sys
    cfg = CONFIG_DIR / "config.yaml"
    if cfg.exists() and sys.platform != "win32":
        try:
            if cfg.stat().st_mode & (stat.S_IRGRP | stat.S_IROTH):   # group/other readable
                lines += ["", "[!] SECURITY: config.yaml is readable by other users",
                          "   Fix: chmod 600 ~/.agent-reach/config.yaml"]
        except OSError:
            pass
    return "\n".join(lines)
```

## Data contracts

```
ProbeResult: { status: "ok"|"missing"|"broken"|"timeout"|"error", output: str, hint: str }
  .ok == (status == "ok")

probe_command(cmd, args=("--version",), timeout=10, retries=0, package=None) -> ProbeResult
  status mapping:
    not on PATH ............................. "missing"
    exec raises FileNotFoundError/OSError ... "broken"  (+ reinstall hint)
    exit code in {126,127} ................. "broken"  (+ reinstall hint)
    TimeoutExpired ......................... "timeout" (+ hint)
    exit != 0 (with output) ............... "error"
    exit == 0 ............................. "ok"
  retry: re-run only on timeout/error; never on missing/broken

check_all(config) -> { channel_name: {
    status, name, message, tier:int(0|1|2), backends:list[str], active_backend:str|None } }

report line annotation: "(current backend: X)" appended IFF active_backend set AND len(backends) > 1
summary footer: "ok_count/total"
security: warn if (st_mode & (S_IRGRP | S_IROTH)) on the credentials file
```

## Dependencies & assumptions

- Python stdlib only for the probe: `shutil`, `subprocess`, `dataclasses`. No third-party deps.
- The probed commands MUST be side-effect-free (`--version`, `status`, `check`). This is a hard precondition of the retry logic.
- The aggregator assumes a component registry (`get_all_channels()`) where each component exposes `check(config) -> (status, message)`, plus `name`, `description`, `tier`, `backends`, and a mutable `active_backend`. (That's the [[ordered-backend-routing--from-agent-reach]] Channel.)
- `rich` is used in the original for colored markup; plain text works fine (shown above).
- The security audit is Unix-only (`sys.platform != "win32"`); skip on Windows where POSIX mode bits don't apply.

## To port this, you need:

- [ ] Drop `probe_command` + `ProbeResult` in verbatim (stdlib only). On Windows, supply a UTF-8 subprocess env or drop the `encoding=` kwargs.
- [ ] Replace `--version` per tool with whatever cheap, side-effect-free command reveals health (some tools need `status`/`check`, not `--version`).
- [ ] An aggregator that wraps each component check in `try/except Exception` → degrade to `error` AND null out `active_backend`.
- [ ] A tier field (0/1/2 or your equivalent) on components, to group the report and decide what to list vs. summarize.
- [ ] Append the active-backend annotation only when `len(backends) > 1`.
- [ ] (Optional, high ROI) a permission audit on any file where you store secrets, with the literal `chmod 600` fix in the message.

## Gotchas

- **Don't trust `shutil.which()` / `command -v` as a health check.** It passes for stale venv shims that can't execute. The whole value here is executing the command. If you skip the exec, you've rebuilt the broken check this replaces.
- **126/127 AND the exec exceptions both mean "broken."** A subprocess can fail to launch (`FileNotFoundError` on the interpreter → caught as exception) OR launch a wrapper that exits 126/127. Handle both paths or you'll miss half the broken installs.
- **Never retry missing/broken.** They can't heal in milliseconds; retrying just doubles latency. Retry only timeout/error, and only because the command is safe to repeat.
- **Clear `active_backend` to `None` on error.** Components are singletons that remember their last successful backend; without this, an errored check reports a stale "current backend."
- **Classify "logged out" by output, not exit code** (in the per-component check, not the probe): many tools exit non-zero when unauthenticated though they're installed fine. Map that to `warn`, or your fix suggestion ("reinstall") will be wrong (should be "log in").
- **The report must not crash on a bad component.** The broad `except` is deliberate; a diagnostic killed by the thing it diagnoses is useless.
- **Permission audit is best-effort.** Wrap the `stat()` in `try/except OSError` and skip on Windows — never let the audit break the report.

## Origin (reference only)

Repo: https://github.com/Panniantong/Agent-Reach
Key files: `agent_reach/probe.py` (`ProbeResult`, `probe_command`, `_run_once`, `reinstall_hint`, `_BROKEN_EXIT_CODES`); `agent_reach/doctor.py` (`check_all`, `_name_msg`, `format_report` incl. tier grouping + the `S_IRGRP|S_IROTH` security check); `agent_reach/channels/base.py` (the `check()` contract each channel implements). Surfaced via `agent-reach doctor` / `agent-reach doctor --json` / `agent-reach watch` (the cron variant).
