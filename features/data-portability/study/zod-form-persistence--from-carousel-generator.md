# Zod Form Persistence & JSON Portability — from [carousel-generator](https://github.com/FranciscoMoretti/carousel-generator)

> Domain: [[_domain]] · Source: https://github.com/FranciscoMoretti/carousel-generator · NotebookLM:

## What it does

Your work is never lost and never locked in. The carousel you're editing is auto-saved to the
browser so it survives a refresh, and you can export the whole document (or just its config, or just
its slides) to a JSON file and re-import it later — or hand it to someone else. There's no account,
no server database; the document lives in your browser and in files you control.

## Why it exists

The app is server-less by design — no login, no backend store. That makes two things essential:
**persistence** (so a reload doesn't wipe your carousel) and **portability** (so "no backend" doesn't
mean "no way to save or move my work"). Together they deliver the "you own your data" promise that a
no-account tool has to make to be trustworthy: close the tab, come back, it's there; want a backup or
to move machines, download a JSON.

## How it actually works

Everything is one big React Hook Form document validated by a Zod `DocumentSchema`
(`{ slides, config, filename }`). Persistence and import/export all hang off that single form.

**Auto-persist (write side).** A hook watches the form's values and, on every change, writes
`JSON.stringify(values)` to `localStorage` under a fixed key. It's deliberately dumb: an effect with
the values in its dependency array, no debounce — every edit re-serializes the whole document.

**Rehydrate with validation (read side).** On load, a companion hook reads the string back,
`JSON.parse`s it, and — crucially — runs it through the Zod schema's `safeParse`. If it validates, the
saved document is used. If it *doesn't* (e.g. the schema changed since it was saved, or storage was
tampered with), it doesn't try to limp along with half-valid data: it **clears localStorage and
falls back to defaults**. Parse errors (corrupt JSON) likewise fall back. This makes a schema bump
self-healing rather than a crash.

**JSON import.** A file picker reads the chosen `.json` with a `FileReader`, `JSON.parse`s it, and
validates against the matching schema — `ConfigSchema` if you're importing config, `MultiSlideSchema`
if you're importing slides — then writes the parsed value straight into the form via React Hook
Form's `setValue`. Import is *targeted*: you can replace just the config or just the slides, not only
the whole document.

**JSON export.** The inverse: serialize the relevant slice of the form to JSON and trigger a file
download (named from the document's `filename` field).

## The non-obvious parts

- **The Zod schema is the trust boundary for stored data.** localStorage is untrusted input — it can
  be stale (old schema) or hand-edited. Validating on read, and *clearing on failure*, turns a
  potential crash-on-load into automatic recovery. This is the highest-value idea in the feature.
- **No debounce on write is a conscious simplicity/cost trade.** Every keystroke re-serializes and
  re-writes the entire document. Fine for a single small document; it's flagged in the code as a
  known rough edge, and the obvious upgrade is a debounced write.
- **Import is per-field, validated per-field.** Using `ConfigSchema` vs `MultiSlideSchema` depending
  on the target field means you can swap themes/branding (config) without touching content (slides),
  and bad files are rejected by `.parse()` before they can poison form state.
- **Same schema, three jobs.** The one `DocumentSchema` (and its `ConfigSchema`/`MultiSlideSchema`
  parts) validates AI output, gates persistence, and guards imports — one source of truth for shape.
- **`localStorage.clear()` (not `removeItem`)** on a validation miss is blunt — it wipes the whole
  origin's storage, not just this key. Works here because the app stores little else; worth narrowing
  in a bigger app.

## Related

- [[ai-carousel-generation--from-carousel-generator]] — the AI fills this same form; generation and import are two front doors to one document model
- [[oklch-theme-palettes--from-carousel-generator]] — the `config` slice that's imported/exported holds the chosen theme
- [[csv-import-export--from-auto-crm]] — the same "escapability + onboarding" promise, done with CSV + partial-success bulk insert instead of whole-document JSON
- See also: any "save draft to localStorage" pattern — the differentiator here is validate-and-self-heal on read
