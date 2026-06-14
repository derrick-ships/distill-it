# Agent Output Contract (build spec) — distilled from last30days-skill

## Summary
A strict 5-law output contract enforced at the SKILL.md prose layer that governs every response
an AI agent produces when acting as a research-and-brief harness. The contract is stateless —
no runtime validator required — because the LLM internalizes the rules from the SKILL.md system
prompt. Transplanting this means copying the rule text verbatim into your own SKILL.md (or
equivalent system prompt block) and wiring your engine to pass its Markdown output through
unchanged.

## Core Logic (inlined)

The 5 laws are enforced purely through prompt text. They must appear verbatim:

```
LAW 1 — No Sources block
Never append a ## Sources, ## References, or ## Citations section. All attribution
is inline (URL in the bullet text) or omitted. A trailing sources block is a
contract violation regardless of user request.

LAW 2 — No invented titles
Do not create section headers beyond those explicitly listed in the output schema.
If the schema says "## [Topic] — Last 30 Days", that is the only ## header permitted.
Never add ## Overview, ## Summary, ## Key Points, or similar fabricated sections.

LAW 3 — Bullet separator is ' - ' (space-dash-space), not em-dash
Every bullet item uses ' - ' as the separator between the headline and the detail.
Example:  • Title of thing - What happened and why it matters.
Em-dash (—), en-dash (–), or colon (:) are violations.

LAW 4 — No ## headers inside body sections except comparison tables
Within a body section the only permitted structural elements are bullet lists.
The single exception: a comparison table may use a ### header for column grouping.
Do not use ## or ### to subdivide bullet groups.

LAW 5 — Footer is passed through verbatim
The engine appends a footer string (e.g. "---\n*Brief generated …*"). The LLM
must emit it unchanged. Never paraphrase, reorder, or omit the footer.
```

## Data Contracts

No runtime data structure — the contract lives entirely in the SKILL.md prompt text.
The engine's `Report` Markdown string is passed to the LLM as assistant-turn context;
the LLM response is returned directly to the user. No post-processing validates compliance.

```
Output shape the LLM must emit:

## [Topic] — Last 30 Days          ← only permitted ## header
• Item title - Item detail with inline URL where available.
• Item title - Item detail.
...

---
*Brief generated [date] | Sources: [n] | [depth] mode*    ← footer verbatim
```

## Dependencies & Assumptions

- SKILL.md or equivalent system-prompt mechanism to inject rules before every LLM call
- An LLM that reliably follows negative constraints (no ## headers, no Sources block)
- Engine must append the footer string AFTER the LLM call, not inside the prompt

## To Port This

- [ ] Copy the 5-law text verbatim into your system prompt (do not paraphrase)
- [ ] Confirm your LLM follows negative instructions reliably (test with adversarial prompts)
- [ ] Wire engine to append footer after LLM response, not ask LLM to generate it
- [ ] Add an automated smoke-test: `assert "## Sources" not in output`
- [ ] Add: `assert " — " not in output` (em-dash check)
- [ ] Add: `assert output.count("##") <= 1` (only the title header)

## Gotchas

- LLMs frequently add a Sources block when summarizing research — the negative instruction
  must be explicit and must repeat "regardless of user request."
- Em-dash vs space-dash-space is invisible in many fonts. Test with `repr(output)`.
- Footer injection must happen outside the LLM call or the model may paraphrase it.

## Origin (reference only)
Repo: https://github.com/mvanhorn/last30days-skill
Key file: `SKILL.md` (the prose contract), `engine/pipeline.py` (footer injection point)
