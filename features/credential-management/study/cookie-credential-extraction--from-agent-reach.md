# Cookie Credential Extraction + Secure Local Store — from [Agent-Reach](https://github.com/Panniantong/Agent-Reach)

> Domain: [[_domain]] · Source: https://github.com/Panniantong/Agent-Reach · NotebookLM:

## What it does

Several platforms (Twitter/X, Xiaohongshu, Bilibili, Xueqiu) have no free API — the only way an agent can read them is to act as a logged-in browser, which means reusing the cookies from a browser where the user is already logged in. This feature does that harvesting in one shot: `agent-reach configure --from-browser chrome` reaches into the user's local browser cookie store, pulls out exactly the cookies each platform needs, saves them to a local config file with locked-down permissions, and (best-effort) mirrors them into the credential files that the downstream tools expect. The user logs into sites in their normal browser; the agent inherits that session without anyone copy-pasting tokens.

## Why it exists

The job-to-be-done is "make logged-in platforms work with zero friction and zero leaked secrets." Manually exporting cookies is error-prone (which cookies? what format?) and pasting them around is a security hazard. Cookies *are* full account access — so the design has to (a) grab only what's needed, (b) never let the saved file be readable by other users on the machine, even for a millisecond, and (c) fit into a world where each upstream tool keeps its credentials in its own place and its own format. There's also a recurring real-world failure this guards against: a cookie set that *looks* present but is actually an anonymous (logged-out) session — useless, and worth rejecting up front.

## How it actually works

**Harvesting.** The extractor tries a fast, stable Rust-based cookie reader (`rookiepy`) first and falls back to the pure-Python `browser_cookie3` if that isn't installed — same logic either way, just different engines, normalized to objects with `.name/.value/.domain`. It supports Chrome, Firefox, Edge, Brave, and Opera. (Both libraries read the browser's on-disk cookie DB, so the browser generally needs to be closed and the OS may prompt for keychain access.)

**Per-platform specs.** Each platform is described declaratively: its name, the cookie domains that belong to it (e.g. `.x.com` and `.twitter.com` for Twitter), and *which* cookies it needs. There are two modes here, and the distinction is deliberate:

- **Named cookies** — for platforms where a couple of specific cookies are the credential (Twitter needs `auth_token` + `ct0`; Bilibili needs `SESSDATA` + `bili_jct`). Only those are pulled out by name.
- **Whole-header capture** (`cookies: None`) — for platforms (Xiaohongshu, Xueqiu) where the session is spread across many cookies and the upstream tool just wants a raw `Cookie:` header string. Here it concatenates *all* cookies for the domain into one `key=val; key=val` string.

**Validation, not just presence.** The configurer doesn't blindly save whatever it finds. For Twitter it confirms *both* required cookies are present (and reports exactly which is missing if not). For Xueqiu it refuses to save unless the telltale logged-in token (`xq_a_token`) is in the string — because a stranger's anonymous cookies would otherwise be saved as if they were a valid session. Each platform reports back `(name, success, message)` so the agent can tell the user precisely what worked and what to fix.

**Secure persistence (the careful bit).** The config file lives at `~/.agent-reach/config.yaml`. The naive way to protect it — write the file, then `chmod 600` — leaves a window where the file with your tokens in it is briefly world-readable. Instead, the file is *created* with owner-only permissions atomically: open with the create flag and a `0o600` mode argument in the same syscall, so it is never readable by anyone else, not even for an instant. There's a Windows fallback (where those POSIX flags don't apply) to a plain write. Reads layer config-file values over uppercase environment variables, and any dump of the config masks anything that looks like a key/token/password.

**Cross-tool sync (best-effort).** Agent-Reach's own config is the source of truth, but the actual reading is done by upstream tools that keep credentials elsewhere. So after saving, it also writes Twitter creds into the formats those tools read — a JSON session file for one legacy tool, and a shell-sourceable `credentials.env` for another. The `.env` writer passes values through shell-quoting so a token containing a quote, `$`, or backtick can't break out into shell syntax when the file is sourced. All of this is wrapped so a sync failure never breaks the main save — it's a convenience mirror, not the system of record.

## The non-obvious parts

- **Two capture modes for two realities.** "Grab these two named cookies" and "grab the entire cookie header" aren't interchangeable — they reflect how each upstream tool consumes the credential. Modeling both in one declarative spec keeps adding a platform to a few lines of data.
- **The atomic-permission write is the whole security story.** `write-then-chmod` has a race; `open(O_CREAT, mode=0o600)` does not. The same pattern is reused everywhere a secret is written (the config and every cross-tool mirror), which is why the codebase factors it into one helper.
- **Presence ≠ validity.** Requiring `xq_a_token`/`auth_token` before saving rejects anonymous-session cookies that would otherwise masquerade as a real login and then fail mysteriously later. Validate the *signal of being logged in*, not just the existence of cookies.
- **Source of truth vs. mirrors.** One canonical store, plus best-effort copies into each tool's native location — wrapped so the copies can fail silently. This avoids the trap of N tools each being a half-authority on the credential.
- **Shell-quoting the `.env` is a real injection defense.** A `.env` meant to be `source`d is executable shell; an unquoted token is an injection vector. `shlex.quote` closes it.
- **A dedicated/secondary account is the recommended hygiene.** The install guide explicitly steers users to a throwaway account for cookie auth, because cookies grant full access and platforms may ban automated use — limiting the blast radius if creds leak.

## Related

- [[ordered-backend-routing--from-agent-reach]] — these credentials are what turn a `warn` (logged-out) backend into an `ok` one
- [[channel-health-diagnostics--from-agent-reach]] — doctor audits the permissions of the very file this writes
- [[multi-tier-credentials--from-last30days-skill]] — the sibling pattern: the three-tier keyless→cookie→API-key ladder this cookie tier sits inside; that doc covers the env-file hierarchy, this one covers the browser-harvest + atomic-write mechanics
