# Centralized Model Registry — from [open-generative-ai](https://github.com/Anil-matcha/Open-Generative-AI)

> Domain: [[_domain]] · Source: https://github.com/Anil-matcha/Open-Generative-AI · NotebookLM: <add link>

## What it does
This is the master catalog that lets one app offer 200+ AI models without 200 different screens. Every model — Flux, Kling, Sora, Veo, and the rest — is described once as a simple entry in a list: its name, the address to send jobs to, and a description of every setting it accepts (which knobs exist, what they default to, what values are allowed). That one description feeds two things at once: the code knows where to send the request, and the screen knows which controls to draw.

## Why it exists
When you support hundreds of models, the naive approach — a hand-built form and a hand-wired API call for each one — collapses under its own weight. The job-to-be-done is **"make adding or changing a model a data edit, not a coding project."** With a registry, onboarding a new model is appending one object to a list; the dropdown updates itself, the right sliders appear, and the API call routes correctly — all for free. It's the difference between a catalog you maintain and a codebase you rewrite.

## How it actually works
Think of it as a spreadsheet of models where each row knows everything about itself:

- **Identity** — a stable id and a friendly name (what you see in the picker).
- **Destination** — the `endpoint`, the exact address the generation request gets posted to. (Subtle but important: the address is *not* the same as the id — "flux-dev" actually sends to "flux-dev-image." The two are kept separate on purpose so the friendly name and the technical route can change independently.)
- **A description of its settings** — for each option (prompt, aspect ratio, width, number of images…), the entry says what type it is, its default, and its limits. If it lists a fixed set of choices, the UI shows a dropdown; if it's a number with a min and max, the UI shows a bounded number input; otherwise, a text box.

Models are sorted into groups by what they can do — text-to-image, image-to-image, text-to-video, and so on — so each studio screen lists only the models relevant to it. When you pick a model and hit generate, the code looks it up by id, reads its endpoint, and the generation client (the submit-and-poll machinery) takes it from there.

## The non-obvious parts
- **One description, two readers.** The same model entry is consumed by the API layer (to route the call) and by the UI (to draw the form). This is the quiet superpower: the form and the request can never disagree about what parameters exist, because they read from the same place.
- **The id/endpoint split is a forward-compatibility move.** Decoupling the user-facing id from the technical endpoint means the gateway can rename or re-route a model under the hood without breaking saved presets or the UI.
- **The schema is what makes the UI "self-building."** Because each parameter declares its own type and limits, the studios don't hardcode forms — they render whatever the chosen model says it needs. Swap the model, the controls rearrange themselves.
- **It's config, not code.** The whole thing is just data. It could be JSON, a database table, or even fetched from the gateway's own model-list API — and at 200+ entries, generating it automatically rather than hand-maintaining it is the obvious next step.

## Related
- [[submit-and-poll-generation-client--from-open-generative-ai]] — reads each model's `endpoint` to know where to submit the job.
- [[multi-studio-shell-architecture--from-open-generative-ai]] — the studios that render forms directly from each model's `inputs` schema.
- See also: [[register-extensibility-api--from-style-dictionary]] and [[plugin-system--from-markitdown]] — other "extend by registering an entry" designs, here applied to models instead of plugins.
