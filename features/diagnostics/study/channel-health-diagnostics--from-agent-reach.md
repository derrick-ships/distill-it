# Channel Health Diagnostics — from [Agent-Reach](https://github.com/Panniantong/Agent-Reach)

> Domain: [[_domain]] · Source: https://github.com/Panniantong/Agent-Reach · NotebookLM:

## What it does

`agent-reach doctor` prints a one-screen health report: for every platform the agent can reach, is it ✅ working, ⚠️ installed-but-needs-login, or ❌ not installed — and when a platform has several possible backends, *which one is live right now*. It also quietly audits one security thing (are your saved credentials world-readable?) and gives the agent copy-pasteable fix suggestions. Underneath it is a small, reusable primitive that answers a deceptively hard question: "is this command-line tool actually usable?" — which is harder than "does the file exist."

## Why it exists

Agent-Reach installs a dozen third-party CLIs the user never sees. They break in undramatic ways: a system Python upgrade leaves a tool's launcher pointing at an interpreter that's gone; a login session expires; a network hiccup makes a tool hang. To a casual check, all of these look like "the command is on disk, so it's fine" — and then it fails at the worst moment, mid-task, in front of the user. Doctor exists so the agent can find and fix these problems *proactively* (it's run after install, on demand, and on a daily cron), and so the failure is reported as an actionable diagnosis ("reinstall this", "log in here") instead of an opaque stack trace. The deeper reason it's a *primitive*, not a script: the same health verdict feeds the [[ordered-backend-routing--from-agent-reach]] selector, so "is it healthy?" needs one trustworthy answer used everywhere.

## How it actually works

There are two layers.

**The probe (the hard primitive).** Most tools check a CLI by asking the OS "is this name on the PATH?" That check is a lie in three common situations, and the probe is built to tell them apart:

- **missing** — genuinely not installed. Nothing on PATH.
- **broken** — on PATH, but it *won't run*. The classic case: you installed a Python CLI with pipx or uv, then upgraded system Python; the launcher's shebang now points at an interpreter that no longer exists. The name resolves, but trying to execute it fails immediately. Shells signal this same family with exit codes 126 ("found but not executable") and 127 ("not found").
- **timeout / error** — it runs but misbehaves (hangs, or exits non-zero with a real error).

The probe gets this right by *actually executing* a cheap, side-effect-free command (`--version`, or a tool's own `status`) and watching how it fails: a `FileNotFoundError` when launching means the interpreter is gone (broken); a timeout means it hung; a non-zero exit with output means it ran but errored. Because the check has no side effects, it can safely retry transient failures (timeout/error) once — but it does *not* retry missing/broken, because those can't heal between two attempts a millisecond apart. For a broken install it hands back a ready-made prescription: `uv tool install --force <pkg>` or `pipx reinstall <pkg>`.

**The doctor (the aggregator + report).** Doctor walks every registered channel, calls each channel's own `check()`, and collects the results. Its prime directive is *survivability*: one misbehaving channel must never crash the whole report. So every per-channel check is wrapped — if a channel throws, it degrades to `status="error"` with the exception as the message, and (importantly) its "active backend" is force-cleared to `None` so a stale value from a previous run can't leak into the error.

The report then groups channels by **tier**: tier 0 (works out of the box), tier 1 (needs a free key or login), tier 2 (complex setup). Each line shows a colored status icon and, *only when a channel actually has a choice of backends*, appends "(current backend: X)" so the user sees which fallback is carrying the platform. Inactive optional channels aren't listed one-by-one; they're summarized into a single nudge: "N more channels available — tell your agent 'install XXX'." A footer shows the headline score, `ok/total`.

Finally, a small **security audit**: on Unix, doctor stats the credentials file and, if it's group- or world-readable, prints a warning plus the exact fix (`chmod 600 ~/.agent-reach/config.yaml`). It's a free, high-signal check tacked onto a command users already run.

## The non-obvious parts

- **Existence is not health, and the gap is the entire reason this exists.** The stale-shebang case is invisible to `which()`; the only way to catch it is to try to run the thing. Every other diagnostic decision flows from taking that seriously.
- **"Broken" deserves its own status because its fix is unique.** missing → install; logged-out → authenticate; broken → *reinstall* (the install metadata is fine, the interpreter rotted). Collapsing broken into missing or error would send the user down the wrong repair path.
- **Retry policy is tied to side-effect-freedom, not to optimism.** It retries only the failure modes that might be transient *and* only because the probed commands are guaranteed harmless to repeat. This is a discipline, not a convenience.
- **The report degrades, it doesn't fail.** A diagnostic tool that can be taken down by the very thing it's diagnosing is worthless. The broad per-channel `except` is intentional, and clearing stale `active_backend` on error is a subtle correctness fix (singletons remember their last good state).
- **It shows the active backend *only when there's more than one*.** Annotating a single-backend channel with "(current backend: X)" is noise; the annotation appears precisely where the user benefits from knowing a fallback kicked in.
- **A security nudge rides along on a command users already run.** Permission drift is silent and dangerous; surfacing it during a routine health check is far more effective than a doc nobody reads.

## Related

- [[ordered-backend-routing--from-agent-reach]] — consumes the probe's verdict to pick a live backend; doctor reports what routing selected
- [[cookie-credential-extraction--from-agent-reach]] — writes the credentials file whose permissions doctor audits
- [[agent-driven-install--from-agent-reach]] — runs doctor after install and on a daily cron to self-heal
- [[multi-tier-credentials--from-last30days-skill]] — also does preflight source-availability checks, but reports source presence rather than executable health
