# AI Carousel Generation — from [carousel-generator](https://github.com/FranciscoMoretti/carousel-generator)

> Domain: [[_domain]] · Source: https://github.com/FranciscoMoretti/carousel-generator · NotebookLM:

## What it does

You type a topic ("how to negotiate a raise") and the app returns a fully-populated 8–15 slide
LinkedIn carousel — each slide already broken into a title, maybe a subtitle, and a short
description, with emojis sprinkled in. You don't write the slides; you edit what the AI drafted.
It's the "blank page killer" of the product.

## Why it exists

The whole tool is a carousel *editor* first, but a blank editor is intimidating and slow. The AI
generation step is the on-ramp: it converts a one-line intent into a structured draft you can
immediately refine. For a LinkedIn creator the job-to-be-done is "turn my idea into a postable
carousel in under a minute," and unstructured ChatGPT output doesn't fit a fixed slide format —
it rambles, over-runs character limits, and doesn't map to the app's data model. This feature
forces the model's output *into the exact shape the editor already understands.*

## How it actually works

The clever bit is a **two-schema split** — "unstyled" vs "styled" — and using the model's
function-calling to fill only the unstyled half.

1. **One Zod schema describes the content; another adds the styling.** Every text element
   (Title, Subtitle, Description) has two Zod definitions. The *unstyled* one carries only what
   the AI should decide: the element `type` and its `text` (with a `maxLength` and a `.describe()`
   that becomes the model's field hint). The *styled* one `.merge()`s in presentation defaults —
   font size, alignment — each marked `.default(...)` so they fill in automatically.

2. **The content schema is handed to the model as a function signature.** `zodToJsonSchema()`
   converts the unstyled document schema into JSON Schema, which becomes the parameters of a
   single function called `carouselCreator`. The model (OpenAI `gpt-4o-mini`, temperature 0) is
   *forced* to call exactly that function (`function_call: { name: "carouselCreator" }`), so it
   can only answer by emitting arguments that match the schema. There's no free-text reply to
   parse — the answer *is* the structured object.

3. **A system prompt encodes the editorial rules.** Plain-language constraints: use only the
   allowed element types; respect each field's `maxLength` but "write less than 70% of that
   number" (a margin so titles don't crowd the slide); 8–15 slides; 2–3 elements per slide; add
   emojis; no slide numbers; keep descriptions short.

4. **Validate, then re-hydrate with style.** The function-call arguments are JSON-parsed and run
   through the *unstyled* schema's `safeParse`. If it passes, the bare content is fed into the
   *styled* `MultiSlideSchema.parse()`, which injects all the styling defaults — and out comes a
   complete, editor-ready document. If validation fails, it logs and returns `null` rather than
   shipping garbage into the editor.

## The non-obvious parts

- **The model never decides styling.** By asking it for the *unstyled* schema only, the prompt
  stays small, the model can't pick bad fonts/colors, and the app keeps full control of look.
  Styling is added deterministically afterward via Zod `.default()`s. This is the single most
  reusable idea here.
- **`.describe()` on schema fields doubles as prompt engineering.** Those descriptions are
  emitted into the JSON Schema the model sees, so field-level guidance lives next to the field —
  not buried in the system prompt.
- **"Write less than 70% of maxLength"** is a soft buffer against text overflowing the fixed
  400×500 slide. The hard `max()` is enforced by Zod; the 70% is a vibe the model is nudged toward.
- **Temperature 0 + forced function call = near-deterministic structure**, trading creative
  variety for reliability — appropriate when the output must drop straight into a typed form.
- **Failure is silent-but-safe**: a schema mismatch returns `null` and the UI just doesn't
  populate, rather than throwing or corrupting the form state.

## Related

- [[byok-rate-limited-action--from-carousel-generator]] — the server action that wraps this call, gates it on an API key, and rate-limits it
- [[zod-form-persistence--from-carousel-generator]] — the generated document flows into the same Zod-validated form that's persisted and importable
- [[cross-source-clustering--from-last30days-skill]] — another "shape messy input into clean structured output" content-synthesis approach
- See also: any LangChain/OpenAI structured-output extractor — same forced-function-call trick
