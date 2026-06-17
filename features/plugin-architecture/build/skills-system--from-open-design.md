# Skills System (build spec) — distilled from open-design

## Summary

Skills are YAML-frontmatter markdown files that declare a design workflow. The plugin-runtime package parses SKILL.md → PluginManifest via a 3-layer merge (sidecar > adapter > fallback). Manifests are Zod-validated. SHA-256 digest computed from manifest + inputs + context refs for reproducibility. Pure-TS runtime (no Node imports) runs in daemon, browser, and CI.

## Core logic (inlined)

**SKILL.md frontmatter parsing (minimal YAML subset):**
```
Line-by-line parser with stack-based indentation tracking
Handles: scalars, block-literal strings (|), inline arrays [a,b,c], dash-prefixed lists
Type coercion: string, boolean, null, integer, decimal
Does NOT handle: YAML anchors, flow-style nested objects
Returns: { metadata: ParsedFrontmatter, body: string }
```

**Adapter — adaptAgentSkill():**
```typescript
Input: raw SKILL.md string
Output: PluginManifest

Type mapping:
  "integer" → "number"
  "enum"    → "select"
  "upload"  → "file"

Compat path: manifest.compat.agentSkills[].path = "./SKILL.md"
  (daemon resolver uses this to locate original file)

Prompt fallback sequence:
  1. od.example_prompt
  2. first line of description
  3. first markdown heading in body

Warnings generated for unmappable fields (e.g., "od.parameters preserved as adapter metadata")
```

**3-layer manifest merge (highest to lowest priority):**
```
1. Sidecar open-design.json (explicit override)
2. Adapter output (agent-skill adapter result)
3. Lower-priority adapters as fallback gap-fillers

Special rule: compat arrays are UNIONED with Set-based deduplication
(not overwritten — each layer can add compat entries)
```

**Digest computation (deterministic SHA-256):**
```typescript
canonicalRecord = {
  manifest: PluginManifest,
  inputs: Record<string, string|number|boolean>,  // user form values
  context: Array<{ kind: 'skill'|'design-system', ref: string }>
}
serialized = JSON.stringify(canonicalRecord, sortedKeys)  // alphabetical key sort, array order preserved
digest = sha256(serialized).toLowerCase()
// Guarantee: same manifest + same inputs + same context refs → same digest
// Algorithm frozen for backward compat; input changes require CI fixture updates
```

**Validation (2-stage):**
```typescript
// Stage 1: Schema
result = PluginManifestSchema.safeParse(manifest)  // Zod

// Stage 2: Cross-field rules
if (stage.until expression exists && stage is repeating):
  require until expression be declared
capabilities whitelist: ['prompt:inject', 'fs:read', 'network']
  warn on unknown (forward-compat: 'connector:' prefix accepted)
OAuth: validate connectorId references exist
MCP: validate server references exist
```

**Pipeline fallback resolution:**
```
priority: declared pipeline → scenario match (by taskKind) → none
source tracked as: 'declared' | 'scenario' | 'none'
scenarios never self-reference (identity guard)
```

## Data contracts

**SKILL.md frontmatter schema:**
```yaml
---
name: web-prototype          # required: skill identifier
description: |               # required: one paragraph
  Surface, audience, what artifact, what's excluded.
triggers:                    # required: specific activation phrases
  - "interactive web prototype"
  - "HTML landing page"
od:                          # optional: Open Design extensions
  mode: prototype            # prototype|deck|template|design-system|image|video|audio
  platform: desktop          # desktop|mobile
  scenario: saas-landing
  preview:
    type: html               # html|jsx|pptx|markdown
    entry: example.html      # relative path
    reload: debounce-100     # refresh strategy
  example_prompt: "Build a SaaS dashboard for a project management tool"
  example_prompt_i18n:
    zh-CN: "为项目管理工具构建SaaS仪表板"
  design_system:
    requires: true
    sections: ["2. Color Palette & Roles", "3. Typography Rules"]
  craft:
    requires: [web-hierarchy, component-density]
  inputs:
    - name: target_audience
      type: text
      required: true
      default: "B2B SaaS users"
  parameters:                # live-tweakable sliders (Phase 4, not yet exposed)
    - name: spacing_scale
      type: hue|spacing|font-scale|opacity
  outputs:
    primary: index.html
    secondary: [assets/]
  capabilities_required:
    - surgical_edit
version: 1.0.0               # optional
author: open-design          # optional
license: MIT                 # optional
platforms: [linux, macos, windows]  # optional
---

# Skill body — the actual agent instructions as markdown
```

**PluginManifest (normalized output):**
```typescript
{
  id: string,
  name: string,
  description: string,
  version: string,
  triggers: string[],
  mode?: "prototype"|"deck"|"template"|"design-system"|"image"|"video"|"audio",
  preview?: { type: string, entry: string, reload?: string },
  inputs?: Array<{ name, type, required, default?, min?, max?, enum? }>,
  pipeline?: { stages: Array<{ name, until? }> },
  capabilities?: string[],
  designSystem?: { requires: boolean, sections?: string[] },
  compat: {
    agentSkills: Array<{ path: string }>,
    claudePlugins: Array<{ path: string }>
  }
}
```

## Dependencies & assumptions

- `plugin-runtime` package: pure ESM TypeScript, `dist/index.mjs` + `dist/index.d.ts`
- No Node.js filesystem imports in runtime — loader injected by caller (daemon provides Node fs; browser/CI provide alternatives)
- Zod for manifest validation (version in package.json of plugin-runtime)
- SHA-256 via Web Crypto API (available in Node 18+ and all modern browsers)
- Skill directory: `skills/<skill-name>/SKILL.md`
- Optional sidecar: `skills/<skill-name>/open-design.json`
- Optional example: `skills/<skill-name>/example.html` (required for html/jsx preview types)
- Optional checklist: `skills/<skill-name>/references/checklist.md` (required for merge/contrib)

## To port this, you need:

- [ ] Minimal YAML parser (scalars, arrays, block-literal strings — no anchors)
- [ ] Directory scanner: `skills/*/SKILL.md` on startup, zero registration
- [ ] adaptAgentSkill() adapter: SKILL.md → PluginManifest with type mapping and warnings
- [ ] 3-layer merge: sidecar > adapter > fallback; union compat arrays
- [ ] Zod schema for PluginManifest validation
- [ ] Cross-field validation: repeating stages need `until`, capabilities whitelist
- [ ] SHA-256 digest from sorted-key JSON serialization of manifest+inputs+context
- [ ] Skill resolver: match by ID, handle `./` prefix stripping
- [ ] Pipeline fallback: declared → scenario match → none

## Gotchas

- **The minimal YAML parser is intentional** — full YAML is overkill and adds attack surface. Don't swap in js-yaml unless you need anchors.
- **Compat arrays are unioned, not overwritten.** If your merge implementation overwrites compat on each layer, sidecar additions will silently drop adapter entries.
- **Digest algorithm is frozen.** Changing key sort order or serialization format breaks backward compatibility with stored snapshots. Pin the algorithm version.
- **Skills can request design system sections — use this.** Injecting a full DESIGN.md into every skill bloats context. Section filtering is cheap and significantly reduces token usage.
- **`od.parameters` (live sliders) is Phase 4 and not yet exposed.** The field exists in the schema but has no runtime effect in v0.10.2. Don't build UI for it yet.

## Origin (reference only)

Repo: https://github.com/nexu-io/open-design  
Key files: `packages/plugin-runtime/src/`, `packages/plugin-runtime/src/adapters/agent-skill.ts`, `packages/plugin-runtime/src/digest.ts`, `packages/plugin-runtime/src/validate.ts`
