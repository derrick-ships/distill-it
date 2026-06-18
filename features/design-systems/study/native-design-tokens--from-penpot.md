# Native Design Tokens — from [penpot](https://github.com/penpot/penpot)

> Domain: [[_domain]] · Source: https://github.com/penpot/penpot · NotebookLM:

## What it does

Lets a design team define their brand's raw values — colors, spacing, font sizes, radii, shadows,
typography — **once**, by name (`colors.primary.blue`, `spacing.md`), and reuse them everywhere in
the design. Tokens can point at other tokens (`{colors.primary.blue}`), and you can flip the whole
design between variants — light/dark, brand A/brand B, compact/comfortable — by toggling which
*groups* of tokens are active. It's the design-system layer built straight into the editor, using
the same open format the rest of the industry is converging on.

## Why it exists

The job-to-be-done is single-source-of-truth styling. Without tokens, "our blue" is copy-pasted as a
hex value across hundreds of shapes; changing it means hunting every instance, and there's no clean
way to express "this is the same blue, just darker in dark mode." Tokens make values *named and
referenced* rather than *duplicated*, so one edit propagates everywhere and theming becomes a switch
rather than a rebuild. For Penpot specifically it's also a wedge against Figma: native, open,
exportable tokens (no plugin, no lock-in) are a credible reason for a design-system team to move.

## How it actually works

Three nested concepts: **tokens → token sets → themes.**

**A token** is a named value with a type. It carries `name` (a dot/slash-separated path like
`colors.primary.blue`), `type` (`color`, `spacing`/`dimension`, `border-radius`, `opacity`,
`font-size`, `font-family`, `font-weight`, `typography`, `shadow`, …), the `value`, and an optional
description. Each type validates its value differently — opacity must be 0–1, a shadow is a list of
offset/blur/spread/color maps, a typography token bundles font-family + size + weight + line-height +
letter-spacing, and so on.

**References (aliases) let tokens point at tokens.** A value containing a brace — `{colors.primary.blue}`
— is a reference. Detection is deliberately simple ("does the value contain `{`?"); resolution walks
the referenced token (which may itself be a reference) until it bottoms out at a concrete value. This
is what lets `colors.button.bg = {colors.primary.blue}` and `spacing.lg = {spacing.md} * 2`-style
composition exist without duplicating raw values.

**A token set** is an ordered, named group of tokens (e.g. a `core` set, a `light` set, a `brand-a`
set). Sets are stored in an insertion-ordered map keyed by token name, and they can be organized into
hierarchical groups.

**A theme** decides *which sets are active*. A theme is essentially a named selection of set names
("light theme = core + light + brand-a"). The library tracks a set of *active themes*, and the
**resolved set of tokens you actually see is computed by merging the active sets in order — later
sets override earlier ones.** So "dark mode" is just a theme that swaps the `light` set for the
`dark` set; everything referencing `{colors.bg}` re-resolves automatically. There's also an always-
present hidden theme used internally so the system has a consistent base to merge onto.

The whole tokens library (all sets, all themes, the active selection) lives inside the design file,
and — crucially — every edit to it flows through the file's normal change system (`:set-token`,
`:set-token-set`, `:set-token-theme`, `:set-active-token-themes`), so token edits are undoable,
saveable, and collaboratively synced like any other edit.

## The non-obvious parts

- **Override-by-merge-order is the entire theming mechanism.** There's no special "dark variant of a
  token" concept — you just have a `dark` set whose `colors.bg` shadows the `core` one, and the active
  theme controls merge order. Simple, and it composes (core → brand → mode).
- **Reference detection is intentionally dumb** (`value contains "{"`), with the real work in
  resolution. Cheap to check on every token; correctness lives in the resolver that follows the chain.
- **Resolved tokens are derived, never stored.** "What's the value of `colors.bg` right now" is
  computed from active themes → active sets → merge → resolve references. Change the active theme and
  everything downstream re-derives — no cached values to invalidate.
- **Tokens piggyback on the change/undo system.** They didn't build a separate persistence/sync path;
  token mutations are just more change types, so they inherit undo, autosave, and realtime for free.
- **It tracks the W3C-ish open token shape** (`name`/`type`/`value`/`description`, references in
  braces), which is what makes import/export interoperable with other token tools rather than a silo.
- **Sets are ordered maps, not plain maps** — insertion order is meaningful both for display and for
  the override semantics.

## Related

- [[change-based-mutation-model--from-penpot]] — same repo; token edits are change types (`:set-token*`) on that system
- [[reference-resolution-engine--from-style-dictionary]] — the dedicated, heavyweight engine for resolving `{token.path}` aliases (chains, cycles, multi-ref strings)
- [[transforms-and-transform-groups--from-style-dictionary]] — turning resolved tokens into platform-native code (the "output" half tokens feed)
- [[token-pipeline-orchestration--from-style-dictionary]] — the end-to-end build pipeline tokens like these flow through
- [[oklch-theme-palettes--from-carousel-generator]] — a much smaller "themes → derived colors" take on the same theming goal
- [[design-systems-library--from-open-design]] — design decisions as a single source of truth, via markdown specs instead of tokens
