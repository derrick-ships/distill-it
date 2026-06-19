# Deterministic Security Hooks (build spec) — distilled from PagoKit

## Summary

A pattern for **enforcing code-quality/security rules on an AI agent's output deterministically**, using Claude Code hooks. Register `PreToolUse`/`PostToolUse`/`Stop` hooks on the `Write|Edit|MultiEdit` tools, all pointing at one dispatcher script. Claude Code pipes the tool call (file path + content) to the script on stdin; the script runs a set of pluggable `check` modules, and if any returns a `deny` finding it **exits with code 2** — which Claude Code interprets as "block this tool call" — printing an actionable, bilingual error to stderr. Crashes/timeouts in the validator fail *open* (exit 0, never block); only a confirmed violation blocks. This is a general guardrail engine; PagoKit uses it for payment security, but the spine is domain-agnostic.

## Core logic (inlined)

### 1. Hook registration (`hooks.json`)

```json
{
  "hooks": {
    "PreToolUse": [
      { "matcher": "Write|Edit|MultiEdit",
        "hooks": [{ "type": "command", "command": "node $CLAUDE_PLUGIN_ROOT/hooks/pagokit-validate.js pre" }] }
    ],
    "PostToolUse": [
      { "matcher": "Write|Edit|MultiEdit",
        "hooks": [{ "type": "command", "command": "node $CLAUDE_PLUGIN_ROOT/hooks/pagokit-validate.js post" }] }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "command": "node $CLAUDE_PLUGIN_ROOT/hooks/pagokit-validate.js stop" }] }
    ]
  }
}
```

`$CLAUDE_PLUGIN_ROOT` is set by Claude Code to the plugin's root dir. In a non-plugin project, register the same in `.claude/settings.json` with an absolute/relative path to the script.

### 2. The dispatcher (`pagokit-validate.js`) — control flow

```
phase = argv[2]  // "pre" | "post" | "stop"

// Read tool-call JSON from stdin, with a 2s timeout so it can never hang.
input = readStdinWithTimeout(2000)   // on timeout/empty -> exit 0 (allow)
try { payload = JSON.parse(input) } catch { exit 0 }   // never block on parse error

// Claude Code hook payload shape (the fields we use):
//   payload.tool_name        -> "Write" | "Edit" | "MultiEdit"
//   payload.tool_input       -> { file_path, content }            (Write)
//                            -> { file_path, new_string }          (Edit)
//                            -> { file_path, edits:[{new_string}] }(MultiEdit)
{ filePath, content } = extractFileAndContent(payload)   // join MultiEdit new_strings
if (!filePath || !content) exit 0

// Filter: only scan real source, skip tests/fixtures/templates.
if (!isSourceFile(filePath)) exit 0
if (isAllowlistedTestFile(filePath)) exit 0

// Pick checks for this phase.
CHECKS = {
  pre:  ['existing-webhook-check', 'gitignore-check'],
  post: ['webhook-has-signature','no-hardcoded-keys','idempotency-canonical','raw-body','no-pii-logs'],
  stop: ['webhook-has-signature','no-hardcoded-keys','raw-body'],   // critical backstop re-run
}[phase] || []

findings = []
for (id of CHECKS) {
  try {
    const mod = require(`./checks/${id}`)         // each exports run(ctx)
    const r = mod.run({ filePath, content })       // null = pass
    if (r) findings.push(r)
  } catch (e) { /* isolate: a broken check never blocks */ }
}

// Emit + decide.
if (findings.length) process.stderr.write(JSON.stringify(findings, null, 2))
const denied = findings.filter(f => f.level === 'deny')
if (denied.length) {
  appendAudit('.pagokit/audit.log', { ts: Date.now(), filePath, phase, denied })
  process.exit(2)   // <-- Claude Code blocks the tool call on exit code 2
}
process.exit(0)     // pass, or warn-only
```

Key contract: **exit 2 = block, exit 0 = allow.** Everything that isn't a positively-confirmed `deny` (timeouts, parse errors, check crashes, warns, clean) exits 0.

### 3. A check module (the `run(ctx) -> finding | null` contract)

Every rule is `checks/<id>.js` exporting `{ run, RULE_ID }`. Example — the webhook-signature rule, inlined whole because it shows the full shape (heuristic gate → comment strip → pattern match → structured finding):

```javascript
'use strict';
const path = require('node:path');
const { isWebhookFilePath, hasIgnoreTag, hasSignatureVerifiedTag, stripCommentsAndStrings } = require('../lib/utils');
const RULE_ID = 'webhook-has-signature';

const VERIFIER_PATTERNS = [
  /stripe\.webhooks\.constructEvent/, /stripe\.Webhook\.construct_event/, /constructEvent\s*\(/,
  /verify[A-Z]\w*Signature\s*\(/, /verify[_]\w*signature\s*\(/i, /verify[A-Z]\w*Checksum\s*\(/,
  /verify[A-Z]\w*Webhook\s*\(/, /verify[_]webhook[_]signature/i,
  /createHmac\s*\(/, /createHash\s*\(/, /HMAC[._]new\s*\(/, /Hmac::new/,
  /WebhookSignature\.verify/, /timingSafeEqual\s*\(/,
];
const NON_PAYMENT_KEYWORDS = ['clerk','inngest','resend','svix','github']; // other webhooks -> skip

function looksLikeWebhookFile(filePath, content) {
  if (isWebhookFilePath(filePath)) return true;
  if (!content) return false;
  const hasPaymentImport = /from\s+['"](?:stripe|@stripe\/|mercadopago|@lemonsqueezy\/|wompi)/.test(content)
    || /require\s*\(\s*['"](?:stripe|mercadopago|@lemonsqueezy\/lemonsqueezy\.js|wompi)/.test(content)
    || /import\s+stripe/i.test(content) || /from\s+stripe/i.test(content);
  const hasHandler = /export\s+async\s+function\s+POST/.test(content)
    || /app\.post\s*\(\s*['"][^'"]*webhook/i.test(content)
    || /router\.post\s*\(\s*['"][^'"]*webhook/i.test(content)
    || /@app\.post\s*\(\s*['"][^'"]*webhook/i.test(content);
  return hasPaymentImport && hasHandler;
}

function run(ctx) {
  const { filePath, content } = ctx;
  if (!filePath || !content) return null;
  if (hasIgnoreTag(content, RULE_ID)) return null;            // // pagokit-ignore: <id> -- reason
  if (!looksLikeWebhookFile(filePath, content)) return null;
  // skip non-payment webhooks (clerk/svix/github/...)
  if (NON_PAYMENT_KEYWORDS.some(kw => new RegExp(`from\\s+['"][^'"]*${kw}`,'i').test(content))) return null;
  if (hasSignatureVerifiedTag(content)) return null;          // // @pagokit:signature-verified
  const stripped = stripCommentsAndStrings(content);          // so docs/strings don't match
  if (VERIFIER_PATTERNS.some(p => p.test(stripped))) return null;  // pass
  return {
    rule: RULE_ID, level: 'deny', code: 'ERR_WEBHOOK_NO_SIG',
    message_en: `Webhook handler does not verify request signature. ${path.basename(filePath)} looks like a payment webhook but no verification call was detected.`,
    message_es: `El handler del webhook no verifica la firma. ${path.basename(filePath)} parece un webhook de pagos pero no se detectó verificación.`,
    suggested_fix: `Add the canonical verifier (Stripe: stripe.webhooks.constructEvent(rawBody, sig, process.env.STRIPE_WEBHOOK_SECRET)). Custom wrapper? add "// @pagokit:signature-verified". Bypass: "// pagokit-ignore: ${RULE_ID} -- reason".`,
  };
}
module.exports = { run, RULE_ID };
```

The same skeleton drives the other rules — only the heuristic gate, the patterns, and the message change:
- **no-hardcoded-keys**: deny if a live-key literal (`/sk_live_[A-Za-z0-9]{16,}/`, `/pk_live_…/`, `/lmnsq_live_…/`, MP `/APP_USR-…/`, etc., plus per-provider `secret_key_pattern`s loaded from data) appears on a non-comment line; `.env.example`/`.env.sample` are scanned to ensure they hold *only* test placeholders; skip matches containing `REPLACE|EXAMPLE|PLACEHOLDER|YOUR_|XXXX|FAKE|TODO` or shorter than ~25 chars.
- **idempotency-canonical**: on checkout/refund/payment files, if the content uses an `idempotency_key`/`Idempotency-Key` header but no canonical UUID generator (`crypto.randomUUID()`, `uuidv4()`, `uuid.uuid4()`, `SecureRandom.uuid`, `Uuid::new_v4`) — `deny` if a *weak* source (`Math.random`, `Date.now`, `time.time`) sits within ±2 lines of the key, else `warn` (generator may be in a helper).
- **raw-body**: on webhook files, `deny` (Next.js/Express) or `warn` (Ruby) if the body is parsed before verification — `request.json()` before verify (Next), missing `express.raw()` middleware (Express), `request.json()`/`get_json()` (Python, suggest `request.body()`), `$request->all()` (Laravel, suggest `getContent()`), `params` (Rails, suggest `request.raw_post`).
- **no-pii-logs** (post only): flags logging of card numbers / emails / PII.
- **gitignore-check** / **existing-webhook-check** (pre only): cheap pre-write checks — is `.env` gitignored; does a webhook for this provider already exist (avoid duplicates).

### 4. The shared utilities (`lib/utils.js`) — inline these, they're the false-positive engineering

- `stripCommentsAndStrings(content)` — **character-by-character** scanner that replaces line comments (`//`, `#`), block comments (`/* */`), and string literals (`'`, `"`, backtick template literals incl. `${}`), with spaces while **preserving newlines/line numbers**. Handles escape sequences. Run rule regexes against the *stripped* text so example code in comments/strings never trips a rule (but keep the original for line-number reporting).
- `hasIgnoreTag(content, ruleId)` — case-insensitive match of `// pagokit-ignore: <ruleId>` or `# pagokit-ignore: <ruleId>` (multi-language comment styles).
- `hasSignatureVerifiedTag(content)` — case-insensitive match of `// @pagokit:signature-verified`.
- `isWebhookFilePath(fp)` — true for basenames `webhook`/`webhooks`, paths containing `api/webhook`, provider-specific webhook filenames, and ambiguous names (`events`,`notifications`,`callback`,`ipn`,`hook`) *only* when the path also contains a webhook segment.
- `isAllowlistedTestFile(fp)` — true for `/__tests__/`, `*.test.*`, `/__fixtures__/`, the plugin's own `integration-builder/templates/`, and `node_modules`. **Critical** — without it the rules fire on your own fake-key fixtures.
- `loadProviders()` — reads + caches `providers.json` (the per-provider key regexes the keys-check uses); returns `{ providers: [] }` on error so the check degrades gracefully.

## Data contracts

**Hook input (stdin, from Claude Code):**
```jsonc
{ "tool_name": "Write", "tool_input": { "file_path": "app/api/webhook/stripe/route.ts", "content": "..." } }
// Edit:      tool_input: { file_path, old_string, new_string }
// MultiEdit: tool_input: { file_path, edits: [{ old_string, new_string }, ...] }  // concat new_strings as content
```

**Finding object (a check returns this or null):**
```jsonc
{ "rule": "webhook-has-signature", "level": "deny" | "warn",
  "code": "ERR_WEBHOOK_NO_SIG", "message_en": "...", "message_es": "...", "suggested_fix": "..." }
```

**Output:** findings JSON → stderr; **exit 2 to block, 0 to allow.** Denials appended to `.pagokit/audit.log` (`{ts, filePath, phase, denied[]}` per line).

## Dependencies & assumptions

- **Claude Code hooks** (or any harness that runs a command per tool call and honors a non-zero "block" exit code). The exit-2-blocks contract is Claude-Code-specific; on another harness, map "deny" to whatever its block signal is.
- **Node ≥18**, zero npm deps — pure `node:path`, `node:fs`, regex. (Keeps the validator from being a supply-chain surface and starting fast on every write.)
- Phase→check mapping, the file allowlist, and per-rule patterns are the swappable parts. The dispatcher + finding contract + comment-stripping are the reusable spine.

## To port this, you need:

- [ ] A `hooks.json` (plugin) or `.claude/settings.json` (project) registering `PreToolUse`/`PostToolUse`/`Stop` on `Write|Edit|MultiEdit` → one dispatcher command per phase.
- [ ] A dispatcher that: reads stdin with a timeout, extracts `{filePath, content}` for Write/Edit/MultiEdit, filters non-source + allowlisted-test files, runs the phase's checks with per-check try/catch, prints findings to stderr, exits 2 iff any `deny`.
- [ ] A `checks/` dir of `run(ctx)->finding|null` modules and a `lib/utils.js` with `stripCommentsAndStrings`, `hasIgnoreTag`, file heuristics, and the test allowlist.
- [ ] A documented bypass tag (`<prefix>-ignore: <rule> -- reason`) honored by every check, and an audit-log path.
- [ ] Your own rule set: each rule = (file heuristic to gate) + (patterns over stripped content) + (bilingual `suggested_fix`).

## Gotchas

- **Fail open, always.** Stdin timeout, JSON parse error, or a thrown check must exit 0. A validator that blocks the agent because of *its own* bug gets disabled within a day. Only a positively-confirmed violation exits 2.
- **The test/fixture allowlist is mandatory.** Your fixtures contain deliberately-fake keys and deliberately-insecure handlers. Skip them at the dispatcher, or the guardrail blocks your own test suite from ever being written.
- **Strip comments AND strings before matching.** Otherwise a code sample inside a comment (or a doc string showing the wrong pattern) trips the very rule documenting it. Preserve line numbers in the stripped copy so error messages point to the right line.
- **`exit 2` is the magic number.** Claude Code blocks on exit code 2 specifically; other non-zero codes may surface differently. Confirm the harness's block contract.
- **Re-run critical checks at `Stop`.** A file can pass when first written, then a later `Edit` in the same turn removes the signature check. The Stop-phase re-run is the backstop.
- **Heuristic gates cut both ways.** Too loose → fires on non-payment webhooks (Clerk/Svix/GitHub) and on unrelated files; too tight → misses real handlers. PagoKit gates on payment-SDK import + POST handler shape and explicitly excludes known non-payment webhook libs. Tune both directions.
- **Bypass-with-reason, not bypass-silent.** A hard gate with no escape hatch gets ripped out the first time it's a false positive. The ignore tag keeps the gate while leaving a grep-able audit trail of every override.
- **MultiEdit content is split.** Concatenate the `new_string`s (not `old_string`s) to form the scanned content, or you'll scan stale text.

## Origin (reference only)

Repo: https://github.com/Hainrixz/agente-pagokit
Key files: `hooks/hooks.json` (the 3 hook registrations), `hooks/pagokit-validate.js` (dispatcher: phases, stdin/timeout, exit 0/2, audit log), `hooks/checks/*.js` (`webhook-has-signature`, `no-hardcoded-keys`, `idempotency-canonical`, `raw-body`, `no-pii-logs`, `gitignore-check`, `existing-webhook-check`), `hooks/lib/utils.js` (`stripCommentsAndStrings`, `hasIgnoreTag`, `hasSignatureVerifiedTag`, `isWebhookFilePath`, `isAllowlistedTestFile`, `loadProviders`), `hooks/ERROR_CODES.md`, `skills/payment-advisor/SECURITY_RULES.md` (the rule definitions Rule 1, 3, 4, 5, 8). Phase 1 providers: Stripe, Mercado Pago, Wompi, Lemon Squeezy.
