# Domain: ai-automation

How software turns natural-language user intent into structured, automated actions over a stream of incoming items — with an LLM in the loop for the judgment calls and deterministic code for everything that can be decided cheaply.

## What this domain means across repos

The recurring shape:

1. **Plain-English instructions** the user writes once ("reply to recruiters politely declining", "archive newsletters").
2. A **cheap deterministic pre-filter** (static conditions, learned patterns) that resolves the obvious cases without paying for an LLM call.
3. An **LLM classifier** that picks which instruction/rule applies when the deterministic layer is ambiguous, returning a **structured (schema-constrained) decision** plus reasoning.
4. A second **LLM argument-filler** step that generates the dynamic content an action needs (a label name, a draft body) via template variables.
5. A **deterministic executor** that applies the chosen actions and records an audit trail.
6. **Feedback / learning loops** — past user corrections feed back into the prompt so classification and tone improve over time.

The art is the split: maximize what deterministic code decides, minimize and tightly schema-constrain what the LLM decides, and always keep an auditable record of why each action fired.

## Features distilled here

- [[ai-rules-engine--from-inbox-zero]] — plain-English → rule selection (static + LLM) → templated action args → execution + audit.
- [[ai-reply-drafting--from-inbox-zero]] — context-assembled, tone-matched reply generation with a learned-writing-style loop and confidence scoring.

## Related domains

- [[email-platform]] — the provider abstraction these automations act through.
- [[inbox-cleanup]] — bulk operations that overlap with rule actions (archive, unsubscribe).
