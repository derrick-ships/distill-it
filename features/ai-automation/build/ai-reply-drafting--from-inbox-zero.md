# AI Reply Drafting (build spec) — distilled from inbox-zero

## Summary

Generate a tone-matched email reply draft + a confidence score by assembling thread/profile/knowledge/calendar/style context into a single prompt, calling an LLM for `{ reply, confidence }`, normalizing the output formatting, and writing it as a provider draft. Includes a side loop that *learns* the user's writing style from their edits and distills it into a compact, PII-free style guide reused on every future draft. Assume the source repo is gone; everything needed is below.

## Core logic (inlined)

### Draft generation

```
aiDraftReplyWithConfidence({ messages, emailAccount, knowledgeBaseContent, calendarSlots, toolData }) -> { reply, confidence }

  system = "You are an expert assistant that drafts email replies.
            Avoid repetition. Use plain text. Write the reply in the SAME LANGUAGE
            as the latest message in the thread.
            <if signature configured> Do not write any closing, sign-off, name, title,
            contact details, or signature block."

  user = getUserPrompt():
    - thread messages, each truncated to ~3000 chars
    - "Context about the user": emailAccount.about / role / timezone
    - "Relevant knowledge base content": knowledgeBaseContent (if any)
    - writing style block (priority order below)
    - calendar availability: concrete suggested slots already converted to user's timezone
    - external tool/CRM data (if any)
    - past drafts to this sender (tone consistency)

  schema = z.object({ reply: z.string(), confidence: z.enum(['LOW','MEDIUM','HIGH']) })
  result = generateObject({ system, prompt: user, schema })

  reply = normalizeDraftReplyFormatting(result.reply)
  if REPETITIVE_TEXT_PATTERN.test(reply): retry   // char repeated 50+ times = degenerate
  return { reply, confidence: result.confidence }
```

Writing-style priority inside the prompt:
```
1. emailAccount.writingStyle            (explicit, user-typed)         -> authoritative
2. emailAccount.learnedWritingStyle     (learned summary, see below)   -> advisory, complements #1
3. default                              "Keep replies concise, direct, friendly.
                                         Aim for 2 sentences at most."
```

### Output normalization

```
normalizeDraftReplyFormatting(text):
  - standardize line endings (\r\n -> \n)
  - strip trailing whitespace per line
  - repair collapsed paragraphs using sentence-boundary detection
  - if >= 60% of lines end with sentence punctuation: promote single \n to double \n\n
```

### Learned writing-style loop (runs periodically, not per-draft)

```
summarizeLearnedWritingStyle(preferenceEvidence) -> { learnedWritingStyle: string<=1500 }

  preferenceEvidence = compiled record of how the user edited prior AI drafts
                       (original draft vs. user-sent version deltas)

  system = "Summarize the user's learned writing style from this preference evidence.
            Make the guidance OPERATIONAL: concrete constraints — sentence count,
            greetings/sign-offs yes/no, how many questions or next steps.
            Focus on directness, verbosity, greeting habits, sign-off habits,
            paragraph structure, formatting.
            Do NOT mention names, email addresses, company names, phone numbers,
            dates, links, or other identifying details."

  schema = z.object({ learnedWritingStyle: z.string().max(1500) })  // 3-6 actionable bullets
                                                                    // + 2-3 before/after examples
  -> persist to emailAccount.learnedWritingStyle
```

## Data contracts

```prisma
// fields on EmailAccount consumed/written by this feature:
writingStyle           String?               // explicit user setting (authoritative)
learnedWritingStyle    String?               // distilled summary (advisory), <=1500 chars
signature              String?               // if set, model omits sign-off
about                  String?  role String?  timezone String?
draftReplyConfidence   DraftReplyConfidence @default(ALL_EMAILS)  // gate: which confidence levels auto-draft
calendarBookingLink    String?

// the resulting draft is recorded on ExecutedAction (see ai-rules-engine build doc):
draftId String?  draftStatus DraftEmailStatus?  wasDraftSent Boolean?
draftModelProvider String?  draftModelName String?  draftPipelineVersion Int?  draftContextMetadata Json?
```

```ts
type DraftReplyResult = { reply: string; confidence: 'LOW' | 'MEDIUM' | 'HIGH' }
```

## Dependencies & assumptions

- **LLM with structured output** (Vercel AI SDK `generateObject` + Zod here; swappable).
- **A knowledge-base store** (optional) the user maintains; passed in as text.
- **Calendar availability** pre-computed into concrete timezone-resolved slots BEFORE the prompt (don't make the model do timezone math).
- **Provider draft write** — see [[email-provider-abstraction--from-inbox-zero]] (`provider.draftEmail(...)`).
- **Edit-capture** — you must record original-draft vs. user-sent deltas somewhere to feed the learning loop.

## To port this, you need:
- [ ] A per-account `writingStyle` (explicit) and `learnedWritingStyle` (summary) field, plus a `signature` and a `draftReplyConfidence` gate.
- [ ] A context assembler: thread (per-message truncation ~3000 chars), profile, knowledge, calendar slots, past drafts.
- [ ] An LLM call returning `{ reply, confidence }` via schema.
- [ ] An output normalizer + a degenerate-output (repetition) guard with retry.
- [ ] A mechanism to capture user edits and a periodic job to distill them into the PII-free style summary.
- [ ] A way to write the draft into the mailbox via your provider layer.

## Gotchas

- **PII in the learned style is a leak risk** — the summarization prompt MUST forbid names/addresses/companies/dates/links. Style only.
- **Explicit style must win** over learned, or the system fights the user's stated preference.
- **Double sign-offs** — if a signature is configured, instruct the model to omit closings, else every draft ends with two names.
- **Per-message (not whole-thread) truncation** — whole-thread truncation drops either the oldest or newest context; cap each message instead.
- **Degenerate repetition loops** are a real LLM failure mode — keep the 50+ repeated-char guard + retry, or broken drafts ship.
- **Confidence must gate behavior** — wire `draftReplyConfidence` so low-confidence drafts aren't silently auto-created when the user only wants high-confidence ones.
- **Could not confirm from source:** exact cadence/trigger of the learning job, and the precise model used for summarization vs. drafting — verify before relying on them.

## Origin (reference only)

Repo: https://github.com/elie222/inbox-zero — `apps/web/utils/ai/reply/`:
`draft-reply.ts` (`aiDraftReplyWithConfidence`, `getUserPrompt`, `normalizeDraftReplyFormatting`),
`summarize-learned-writing-style.ts`, `reply-context-collector.ts`, `reply-memory.ts`, `draft-confidence.ts`,
`draft-follow-up.ts`, `generate-nudge.ts`. EmailAccount fields in `apps/web/prisma/schema.prisma`.
