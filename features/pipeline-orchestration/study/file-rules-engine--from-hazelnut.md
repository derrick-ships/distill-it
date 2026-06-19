# File Rules Engine — from [hazelnut](https://github.com/ricardodantas/hazelnut)

> Domain: [[_domain]] · Source: https://github.com/ricardodantas/hazelnut · NotebookLM: <link once added>

## What it does

This is the "if this, then that" brain. You define rules — each a **condition** (match files by
extension, glob, regex, size, age, hidden-ness, directory-or-not) paired with an **action**. The engine
takes a file path, finds the rule(s) whose condition matches, and runs their action. Rules can be
enabled/disabled, ordered, and a matching rule can declare "stop here" so later rules don't also fire.

## Why it exists

The whole product is "automate file chores by rules," so the rules engine is the core. The design goal
is to make conditions both *expressive* (combine extension + size + age + name pattern) and *fast*
(this runs on every file event and during full-folder scans), and to make the match logic dead simple:
a condition is just a struct of optional criteria, and a file matches if it satisfies every criterion
that's set.

## How it actually works

A `Rule` is `{name, enabled, condition, action, stop_processing}` — and it's serializable, so rules
live in a config file. A `Condition` is a struct of **all-optional** fields: `extension` /
`extensions[]`, `name_matches` (glob), `name_regex`, `size_greater_than` / `size_less_than`,
`age_days_greater_than` / `age_days_less_than`, `is_directory`, `is_hidden`. Matching is **AND across
whatever is set**: the engine checks each criterion present and bails to `false` on the first miss; if
nothing contradicts, it's a match. Unset fields are simply ignored — so an empty condition matches
everything.

Two performance touches stand out. First, all the size/age checks share a **single `metadata()`
syscall** — it's fetched once only if any size/age criterion is set, not per-check. Second, compiled
**glob and regex patterns are cached** in thread-local maps (capped at 1000 entries, cleared wholesale
when full) so the same pattern isn't recompiled on every file. Extension matching is case-insensitive.

The `RuleEngine` holds an ordered list of rules and offers a few evaluation modes: `evaluate_first`
(first matching action), `evaluate_all` (every matching action, stopping early if a matched rule says
`stop_processing`), and `evaluate_filtered` (only rules whose names are in an allow-list — this is what
the per-directory watch filtering uses). The `process*` variants actually **execute** the matched
actions, with one critical rule: after a **destructive** action (move, rename, trash, delete) the file
no longer exists at the original path, so processing stops — you can't copy a file you just moved.

## The non-obvious parts

- **A condition is a struct of optionals, matched by AND.** No expression language, no parser — just
  "every set field must hold." Empty condition = matches all. Simple, fast, serializable.
- **Short-circuit on first failed criterion** keeps the common case (a quick extension mismatch) cheap.
- **One metadata syscall for all size+age checks**, fetched lazily only when needed — file stat is the
  expensive part, so it's done once.
- **Thread-local compiled-pattern caches** (glob + regex), cap-and-clear at 1000 — avoids recompiling
  patterns hot in a scan, without unbounded memory.
- **`stop_processing` is per-rule ordering control** — a matched rule can prevent later rules from
  firing, so you can layer specific-then-general rules.
- **Destructive actions stop the chain.** The engine knows move/rename/trash/delete remove the source,
  so it won't try to run a second action on a vanished file.
- **Name-only matching.** Glob/regex run against the file *name*, not the full path — intentional for
  organizing-by-filename.

## Related
- [[file-actions-executor--from-hazelnut]] (what a matched rule runs)
- [[debounced-file-watcher--from-hazelnut]] (feeds file paths in, with a per-directory rule allow-list)
- [[query-processor-middleware-pipeline--from-metabase]] (a different rule/transform pipeline — middleware vs condition-action rules)
- See also: [[pipeline-orchestration]] peers.
