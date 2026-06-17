# Centralized Model Registry (build spec) — distilled from open-generative-ai

## Summary
One data file (`models.js`) is the single source of truth for all 200+ models. Each model is a plain object describing its `id`, display `name`, the gateway `endpoint` to hit, and a self-describing `inputs` schema (each parameter's type, default, allowed values, min/max). Models are grouped into capability arrays (`t2iModels`, `i2iModels`, `t2vModels`, …) and looked up by id via tiny helpers. This data drives *both* the API layer (which endpoint + which params to send) *and* the UI (which controls to render). Adding a model = adding an object; no code changes anywhere else. This is the config-over-code pattern that makes a 200-model app maintainable.

## Core logic (inlined)

A model entry is a declarative record. Real shape (abridged from `models.js`):

```javascript
// text-to-image models
export const t2iModels = [
  {
    id: "nano-banana",
    name: "Nano Banana",
    endpoint: "nano-banana",            // ← what submitAndPoll posts to: /api/v1/{endpoint}
    inputs: {
      prompt: {
        name: "prompt",
        title: "Prompt",
        type: "string",
        description: "Text prompt describing the image...",
        examples: ["A portrait of me in a modern living room..."],
      },
      aspect_ratio: {
        name: "aspect_ratio",
        title: "Aspect Ratio",
        type: "string",
        description: "Aspect ratio of the output image.",
        enum: ["1:1", "3:4", "4:3", "9:16", "16:9" /* ... */],
        default: "1:1",
      },
    },
  },
  {
    id: "flux-dev",
    name: "Flux Dev",
    endpoint: "flux-dev-image",          // ← note: endpoint != id; the indirection matters
    inputs: {
      prompt: { /* ...as above... */ },
      width:      { type: "int", default: 1024, minValue: 128, maxValue: 2048 },
      height:     { type: "int", default: 1024, minValue: 128, maxValue: 2048 },
      num_images: { type: "int", default: 1,    minValue: 1,   maxValue: 4 },
    },
  },
  // ...50+ more
];

// parallel arrays for each capability
export const i2iModels = [ /* image-to-image */ ];
export const t2vModels = [ /* text-to-video  */ ];
// (and i2v, lipsync, audio, etc.)
```

Lookups are one-liners; the API layer uses them to resolve an endpoint from a chosen id:

```javascript
export const getModelById      = (id) => t2iModels.find(m => m.id === id);
export const getVideoModelById = (id) => t2vModels.find(m => m.id === id);
```

How the two consumers read the same record:

```javascript
// API side (muapi.js): id → endpoint
const modelInfo = getModelById(params.model);
const endpoint  = modelInfo?.endpoint || params.model;   // fall back to id if not found
return submitAndPoll(endpoint, payload, apiKey, params.onRequestId, 60);

// UI side (a studio component): inputs schema → form controls
Object.entries(model.inputs).forEach(([key, def]) => {
  if (def.enum)            renderSelect(def.title, def.enum, def.default);   // dropdown
  else if (def.type === 'int')  renderNumber(def.title, def.minValue, def.maxValue, def.default);
  else                     renderText(def.title, def.examples?.[0]);          // text input
});
```

## Data contracts
- **Model record**:
  ```
  {
    id: string,              // stable key, used in UI selection + lookups
    name: string,            // human label
    endpoint: string,        // gateway path segment — decoupled from id on purpose
    inputs: {                // map of paramName → ParamDef
      [paramName]: {
        name: string,
        title: string,       // label for the control
        type: "string" | "int" | ...,
        description?: string,
        default?: any,
        enum?: any[],        // present → render a select
        examples?: any[],    // present → placeholder / suggestion
        minValue?: number,   // int constraints
        maxValue?: number,
      }
    }
  }
  ```
- **Grouping**: separate exported arrays per capability (`t2iModels`, `i2iModels`, `t2vModels`, `i2vModels`, `lipsyncModels`, …). A model that does two things appears in two arrays (or you keep capability flags — here it's separate arrays).
- **Lookup contract**: `getXById(id)` returns the record or `undefined`; callers fall back to using the raw id as the endpoint.

## Dependencies & assumptions
- Zero runtime dependencies — it's a static JS data module. Could equally be JSON, YAML, or a DB table.
- Assumes the gateway's parameter names match the keys in `inputs` (the payload builder copies them straight through).
- Assumes `endpoint` is the only thing the API layer needs to route a request; everything else is generic submit+poll.

## To port this, you need:
- [ ] A declarative record format that captures, per model: a stable id, the routing target (endpoint/path/model-string), and a parameter schema rich enough to render UI from (type, default, allowed values, ranges).
- [ ] Capability grouping so each studio/screen can list only the models it supports.
- [ ] Lookup helpers (`byId`) used by the API layer to resolve the routing target.
- [ ] A UI layer that renders controls *from* the schema rather than hardcoding a form per model.
- [ ] A payload builder that copies known param keys onto the request (see submit-and-poll doc).

## Gotchas
- **`endpoint` is deliberately separate from `id`.** `flux-dev` → `flux-dev-image`. Never assume they're equal; the fallback `modelInfo?.endpoint || params.model` papers over a missing record but will hit the wrong endpoint if a record is mistyped. Treat a missing lookup as a bug, not a silent fallback, in stricter ports.
- **The schema is the contract for *both* sides.** If `inputs` and the gateway's actual accepted params drift apart, the UI shows a control that the API ignores (or vice versa). One file to keep honest, two consumers depending on it.
- **`enum` vs `int` vs free-text is how the UI decides the control.** Forgetting `enum` turns a dropdown into a text box; forgetting `min/maxValue` removes guardrails. The richness of each `ParamDef` directly determines UX quality.
- **No validation engine ships with it.** The schema *describes* constraints but nothing enforces them at submit time except the UI. A bad payload still reaches the gateway. Add client-side validation from the same schema if you need it.
- **Scaling to 200+ entries by hand is a maintenance load.** Consider generating `models.js` from the gateway's own model-list API rather than hand-maintaining it.

## Origin (reference only)
`Anil-matcha/Open-Generative-AI` — `packages/studio/src/models.js` (`t2iModels`, `i2iModels`, `t2vModels`, … arrays; `getModelById`, `getVideoModelById`). Consumed by `muapi.js` (endpoint resolution) and by the studio components (form rendering).
