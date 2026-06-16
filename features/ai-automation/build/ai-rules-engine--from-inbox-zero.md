# AI Rules Engine (build spec) — distilled from inbox-zero

## Summary

Build a natural-language inbox-automation engine: users author rules combining optional **static conditions** (from/to/subject/body/group/category) and optional **plain-English instructions**; for each incoming message the engine resolves matches as cheaply as possible (static/pattern first, LLM only for the ambiguous remainder), then runs the matched rule's **actions**, generating any dynamic action content via templated LLM calls, and writes an auditable execution record. Assume the source repo is gone; everything needed is below.

## Core logic (inlined)

### Stage A — evaluate each rule's static conditions (no LLM)

```
evaluateRuleConditions(rule, email) -> { matched: bool, potentialAiMatch: bool }

  hasStatic = rule.from || rule.to || rule.subject || rule.body || rule.group || rule.categoryFilters
  staticMatch = matchesStaticRule(rule, email)   // false if no static conditions defined

  if rule.conditionalOperator == OR:
      if staticMatch: return { matched: true,  potentialAiMatch: false }   // confident, skip LLM
      else:           return { matched: false, potentialAiMatch: rule.hasInstructions }
  else: # AND
      if hasStatic and not staticMatch: return { matched: false, potentialAiMatch: false } # reject
      # static passed (or none) -> instructions still must be checked by AI
      return { matched: false, potentialAiMatch: rule.hasInstructions }
```

```
matchesStaticRule(rule, email):
  from/to:  lowercase; test with an ADDRESS-ANCHORED regex (must match the real address
            boundary, not a substring — blocks boss@company.com.evil.com spoofing) OR
            against the display name. Glob '*' allowed.
  subject/body: unanchored pattern, glob '*' wildcards allowed.
  a missing condition field = passes (true).
  return true only if every present field matches.
```

Learned patterns (senders the user previously corrected) are checked here too and can short-circuit to a confident match without the LLM.

### Stage B — LLM rule selection (only the `potentialAiMatch` rules)

Single-rule mode (default): `generateObject` with schema
```
z.object({
  reasoning: z.string(),
  ruleName: z.string().nullable(),
  noMatchFound: z.boolean(),
})
```
Multi-rule mode (opt-in via `emailAccount.multiRuleSelectionEnabled`):
```
z.object({ matchedRules: z.array(z.object({
  ruleName: z.string(),
  isPrimary: z.boolean(),   // exactly one primary enforced
})) })
```
Prompt shape: system message ("select a rule; match to a SPECIFIC user-defined rule that addresses the email's exact content; prefer specific over generic; pick none if nothing fits; respect rules that explicitly reject categories of email"). User message = the email (sender, subject, truncated body) + each candidate rule rendered as a named block with its instructions + the user's past classification feedback + account metadata. Multi-rule system prompt adds "BE SELECTIVE — rare to need more than 1-2 rules."

### Stage C — fill action template variables (LLM)

```
extractTemplateVars(actionString): find all /{{(.*?)}}/ -> one schema field per placeholder (var1, var2, ...)
  Only processes STRING fields that contain {{...}}. Applies to action fields:
  label, subject, content, to, cc, bcc, url.
generate z.object({ var1: z.string(), var2: z.string(), ... }) with description:
  "Return ONLY the value for each variable, not the surrounding template text."
mergeTemplateWithVars(template, vars): interleave generated values with the static text
  segments, preserving exact surrounding formatting.
```

### Stage D — execute + record

```
executeMatchedRule(rule, email, emailAccount, isTest):
  actions = rule.actions
  actions = removeBlockedLowTrustActions(actions)            # e.g. no auto-reply to untrusted senders
  actions = getActionItemsWithAiArgs(actions)                # Stage C fills {{...}}
  (immediate, delayed) = partition(actions, a => a.delayInMinutes)

  if isTest:   return { rule, actionItems: actions, status: 'would-apply' }   # NO writes

  executedRule = db.ExecutedRule.create({ status: APPLYING, ruleId, threadId, messageId,
                                          reason, matchMetadata, automated })
  for a in immediate: db.ExecutedAction.create(fromAction(a, executedRule.id))
  if delayed: scheduleDelayedActions(delayed, executedRule.id)
  results = for a in immediate: executeAct(client, email, a, emailAccount)
  status = any(r.failed) ? ERROR : (delayed && !immediate ? APPLYING : APPLIED)
  db.ExecutedRule.update(executedRule.id, { status })
```

```
executeAct -> runActionFunction({ client, email, action, emailAccount }) per ActionType.
  ACTION_FAILURE_TYPES = { DRAFT_MESSAGING_CHANNEL, NOTIFY_MESSAGING_CHANNEL, NOTIFY_SENDER }
    -> these return { success, errorCode } instead of throwing.
  DRAFT_EMAIL success -> store returned draftId on the ExecutedAction.
```

### Orchestrator order (runRules)

1. `prepareRulesWithMetaRule` — inject synthetic conversation-tracking meta-rule if any conversation-status rule is enabled.
2. `findMatchingRules` — run Stage A on all; collect confident matches + `potentialAiMatch` candidates; run Stage B on candidates.
3. `ensureConversationRuleContinuity` — if a conversation meta-rule matched earlier in this thread, re-apply it now.
4. `determineConversationStatus` — resolve the meta-rule to a concrete status (reply/awaiting/FYI/resolved).
5. `limitDraftEmailActions` — only ONE rule may draft a reply; static drafts beat AI drafts; merge messaging channels from other draft rules onto the winner.
6. For each final matched rule → Stage D.

## Data contracts

```prisma
model Rule {
  id String @id
  name String
  enabled Boolean @default(true)
  automate Boolean @default(true)       // false = require manual approval
  runOnThreads Boolean @default(false)
  conditionalOperator LogicalOperator @default(AND)   // AND | OR
  instructions String?                  // the plain-English part
  from String?  to String?  subject String?  body String?   // static conditions
  groupId String? @unique               // sender/pattern group condition
  categoryFilterType CategoryFilterType?  categoryFilters Category[]
  systemType SystemType?                // TO_REPLY|FYI|AWAITING_REPLY|ACTIONED|COLD_EMAIL|NEWSLETTER|MARKETING|CALENDAR|RECEIPT|NOTIFICATION
  actions Action[]
  emailAccountId String
}

model Action {
  id String @id
  type ActionType
  ruleId String
  label String?  labelId String?
  subject String?  content String?      // may contain {{template vars}}
  to String?  cc String?  bcc String?  url String?
  folderName String?  folderId String?
  delayInMinutes Int?                   // present => delayed action
  staticAttachments Json?
}

model ExecutedRule {
  id String @id
  threadId String  messageId String
  status ExecutedRuleStatus             // APPLIED|APPLYING|REJECTED|PENDING|SKIPPED|ERROR
  automated Boolean
  reason String?  matchMetadata Json?
  ruleId String?
  actionItems ExecutedAction[]
}

model ExecutedAction {
  id String @id  type ActionType  executedRuleId String
  label String? labelId String? subject String? content String?
  to String? cc String? bcc String? url String? folderName String? folderId String?
  draftId String?  draftStatus DraftEmailStatus?  wasDraftSent Boolean?
  draftModelProvider String? draftModelName String?  draftContextMetadata Json?
}

model Group { id String @id  name String  prompt String?  items GroupItem[]  rule Rule? }
model GroupItem { id String @id  type GroupItemType /*FROM|SUBJECT|BODY*/  value String  exclude Boolean @default(false) }

enum ActionType { ARCHIVE LABEL REPLY SEND_EMAIL FORWARD DRAFT_EMAIL DRAFT_MESSAGING_CHANNEL
                  NOTIFY_MESSAGING_CHANNEL MARK_SPAM CALL_WEBHOOK MARK_READ STAR DIGEST MOVE_FOLDER NOTIFY_SENDER }
enum LogicalOperator { AND OR }
enum ExecutedRuleStatus { APPLIED APPLYING REJECTED PENDING SKIPPED ERROR }
```

Internal email shape (normalized by the provider layer — see [[email-provider-abstraction--from-inbox-zero]]):
```ts
type ParsedMessage = {
  id: string; threadId: string;
  headers: { from: string; to?: string; subject?: string; date?: string; "list-unsubscribe"?: string };
  textPlain?: string; textHtml?: string; internalDate: string;
}
```

## Dependencies & assumptions

- **LLM with structured output** — Vercel AI SDK `generateObject` + Zod. Swappable for any provider that supports schema-constrained JSON (instructor, OpenAI tool-calls, etc.).
- **Relational DB** (Prisma/Postgres here) for Rule/Action/ExecutedRule/ExecutedAction. Swappable.
- **A provider abstraction** exposing per-action operations (archive/label/draft/send/markRead/...) — see the email-platform feature. The engine itself is provider-agnostic.
- **A job scheduler** for delayed actions (Upstash/QStash here). Only needed if you support `delayInMinutes`.
- Per-account flags consumed: `multiRuleSelectionEnabled`, `rulesPrompt`, plus the `automate` flag per rule.

## To port this, you need:
- [ ] A Rule model with both static-condition columns AND a free-text `instructions` column, plus a per-rule AND/OR operator.
- [ ] An Action model whose string fields tolerate `{{template}}` placeholders.
- [ ] An ExecutedRule/ExecutedAction audit pair with a status enum.
- [ ] A static matcher with **address-anchored** from/to matching (do not use naive `includes`).
- [ ] Two LLM call sites with Zod schemas: rule-selection and template-var-fill.
- [ ] An action dispatcher mapping each ActionType to a side-effecting handler against your mail/back-end.
- [ ] A dry-run/test path that returns the decision without persisting or executing.
- [ ] (optional) A scheduler for delayed actions; a conversation-status meta-rule if you want thread tracking.

## Gotchas

- **Never substring-match sender addresses** — spoofable. Anchor to the address boundary.
- **AND vs OR changes whether static failure rejects the rule.** Get this wrong and rules silently never fire (or fire on everything).
- **Only one drafting rule per email**, and static drafts must beat AI drafts, or you get duplicate/competing replies.
- **Template-var fill must return values only**, never the surrounding template — enforce in the schema description and re-merge yourself; don't let the model rewrite static text.
- **Guard auto-actions on low-trust senders** (don't auto-reply/forward to unverified cold senders) before executing.
- **Status lifecycle:** APPLYING → APPLIED/ERROR; if only delayed actions exist, leave APPLYING and let the delayed-completion handler finalize — otherwise records look stuck.
- **Reject over-matching:** keep the explicit "no match" branch in the selection schema; a forced weak match erodes user trust faster than a miss.
- **Could not confirm from source:** the exact retry/backoff policy on failed LLM calls and the precise body-truncation length used in the selection prompt — verify before relying on them.

## Origin (reference only)

Repo: https://github.com/elie222/inbox-zero — `apps/web/utils/ai/choose-rule/`:
`run-rules.ts` (orchestrator), `match-rules.ts` / `evaluateRuleConditions` (static), `ai-choose-rule.ts` (LLM selection), `choose-args.ts` (template-var fill), `execute.ts` (`executeAct`/`runActionFunction`), `types.ts`. Schema: `apps/web/prisma/schema.prisma`.
