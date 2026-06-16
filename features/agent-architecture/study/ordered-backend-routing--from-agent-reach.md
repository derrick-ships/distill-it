# Ordered Backend Routing — from [Agent-Reach](https://github.com/Panniantong/Agent-Reach)

> Domain: [[_domain]] · Source: https://github.com/Panniantong/Agent-Reach · NotebookLM:

## What it does

Agent-Reach gives an AI agent the ability to read ~12 internet platforms (Twitter, Reddit, Bilibili, Xiaohongshu, YouTube, GitHub…). The problem is that *each platform can be reached more than one way*, and the ways keep breaking — a CLI gets abandoned, a site changes its anti-bot rules, an account gets logged out. Ordered Backend Routing is the pattern that keeps a capability working anyway: every platform declares an **ordered list of backends** (the preferred one first, then fallbacks), and the system automatically uses the first one that is actually healthy *right now*. "Switching to a fallback" is not a code change — it's just picking the next item in a list.

## Why it exists

The whole product promise is "your agent can see the entire internet, for free, and it keeps working." That promise is impossible if every platform has a single hard-wired access method, because those methods rot constantly. The author's framing is blunt: Agent-Reach is "the selector, installer, health checker and router — never a wrapper." It doesn't reimplement Twitter; it knows there are three ways to read Twitter (twitter-cli → OpenCLI → bird), tries them in order, and tells the agent which one is live. The job-to-be-done is *resilience of a capability*, decoupled from *which tool happens to provide that capability today*.

## How it actually works

Each platform is modelled as a **Channel** — a small class with a name, a human description, a **tier** (how hard it is to set up), and the load-bearing field: an ordered `backends` list. The first entry is the preferred backend; the rest are fallbacks.

When the system needs to know whether a platform works, it asks the channel to `check()` itself. A multi-backend channel does this in a deliberate two-phase way:

1. **Probe every candidate backend in order** and record what it found. A backend can come back as *not installed* (skip it entirely, it's not even a candidate), *healthy and ready*, *installed but not logged in / needs config*, or *installed but broken*.
2. **Choose with a priority rule**: first look for any backend that came back fully healthy (`ok`) — the first such one wins. Only if *nothing* is healthy do you fall back to the first "installed but needs login" (`warn`) backend.

That ordering rule is the clever bit. Imagine twitter-cli is installed but you're not logged in (a `warn`), while OpenCLI further down the list is fully working (an `ok`). A naive "first non-missing backend wins" loop would stop at twitter-cli and report the platform as half-broken — hiding the perfectly good OpenCLI behind it. By collecting *all* findings first and preferring `ok` over `warn` regardless of position, the live backend always wins.

Whatever backend ends up serving the channel is recorded as the channel's **active backend**, so the rest of the system (and the agent) can see not just "Twitter works" but "Twitter works *via OpenCLI right now*."

Two more touches make it robust:

- **A health check is a real execution, not a file-existence check.** Finding the command on disk (`which`) is *not* proof it runs — a stale virtual-env shim passes `which` but fails to execute. So a channel actually runs a cheap, side-effect-free command (`twitter status`, `bird check`) and reads the output to classify health. (This probing primitive is its own feature — see [[channel-health-diagnostics--from-agent-reach]].)
- **The user can pin a backend.** A config key like `twitter_backend` (or env var `TWITTER_BACKEND`) moves the named backend to the front of the order. Critically, an *unknown* override value is ignored rather than honored — a stale or typo'd pin can never hide every working backend.

## The non-obvious parts

- **Ordering is policy; selection is health.** The list encodes the *preference* ("we'd rather use twitter-cli"), but the actual choice is gated on *live health*. Preference never overrides reality. This separation is why the maintainer can re-rank backends across the whole product just by editing lists.
- **`warn` is a first-class outcome, distinct from `off`.** "Installed but not logged in" is genuinely different from "not installed" — the fix is different (log in vs. install), and a `warn` backend is still usable as a last resort if nothing better exists. Collapsing them into a boolean would lose the information the agent needs to self-repair.
- **Status is interpreted from tool output, not just exit codes.** `twitter status` exits non-zero when unauthenticated but the tool itself is alive, so the channel inspects the *text* (`"ok: true"` vs `"not_authenticated"`) to tell "needs login" apart from "actually broken." Exit code alone would misfile a logged-out tool as broken.
- **The fallback chain is per-platform, not global.** Reddit's chain (OpenCLI → rdt-cli) and Twitter's chain (twitter-cli → OpenCLI → bird) are independent; OpenCLI happens to appear in several chains as a shared fallback because it reuses the browser's login state for many sites at once.

## Related

- [[channel-health-diagnostics--from-agent-reach]] — the probe + doctor layer that decides whether a backend is healthy; routing consumes its verdict
- [[cookie-credential-extraction--from-agent-reach]] — supplies the credentials a `warn` (logged-out) backend needs to become `ok`
- [[agent-driven-install--from-agent-reach]] — installs the backends that this router selects among
- [[plugin-system--from-markitdown]] — same "ordered, pluggable registry where first-that-works wins" shape, applied to document converters instead of platform backends
- See also: [[email-provider-abstraction--from-inbox-zero]] (adapter seam over interchangeable providers — but static, no health-gated fallback)
