# Adaptive Element Relocation (build spec) — distilled from Scrapling

## Summary
Make a scraper resilient to website HTML changes. On first extraction, persist a multi-property
"fingerprint" of each target element keyed by (domain, identifier). On later runs, if the original
selector returns nothing, load the fingerprint and re-find the element by scoring every candidate
on the page for fuzzy similarity, returning the best match(es) above a similarity threshold.

## Core logic (inlined)
Two phases, two entry points.

SAVE (first run, when selector still works):
```
def save_element(domain, identifier, element):
    fp = {
        "tag":        element.tag,
        "text":       element.text,
        "attributes": dict(element.attrs),              # names + values
        "siblings":   [s.tag for s in element.siblings], # tag names only
        "path":       [a.tag for a in element.ancestors],# tag names only
        "parent": {
            "tag":        element.parent.tag,
            "attributes": dict(element.parent.attrs),
            "text":       element.parent.text,
        },
    }
    storage.save(key=(domain, identifier), value=fp)
```

RELOCATE (later run, when selector returns empty):
```
def relocate(domain, identifier, page, threshold=0.40):
    fp = storage.retrieve(key=(domain, identifier))
    scored = []
    for el in page.all_elements:
        scored.append((similarity(fp, fingerprint_of(el)), el))
    scored.sort(reverse=True, key=lambda x: x[0])
    best_score, best_el = scored[0]
    if best_score < threshold:
        warn(f"no match >= {threshold}; best was {best_score:.2f}")
        return None
    return [el for score, el in scored if score >= threshold]
```

similarity() is a weighted fuzzy comparison across the fingerprint fields — NOT equality.
Compare tag (exact-ish), text (fuzzy string ratio), attributes (overlap of names+values),
siblings (sequence overlap of tag names), path (sequence overlap), parent (same sub-comparison).
Combine into a 0..1 score. Tune weights so no single field dominates (the whole point is that
any one field may have changed).

## Data contracts
Fingerprint record (what gets stored per element):
```
{
  "tag": str,
  "text": str | null,
  "attributes": { str: str },
  "siblings": [str],          # tag names
  "path": [str],              # tag names, root..element
  "parent": { "tag": str, "attributes": {str:str}, "text": str|null }
}
```
Storage key: (domain: str, identifier: str). Domain auto-derived from the fetch URL; identifier
auto-derivable from the selector/position or supplied by the caller.

Default storage: SQLite, WAL mode (thread-safe concurrent reads/writes — matters if multiple
workers share one DB).

## Dependencies & assumptions
- An HTML parser exposing tag/text/attrs/siblings/ancestors/parent per element (Scrapling uses lxml).
- A fuzzy string similarity function (e.g. difflib SequenceMatcher, RapidFuzz) — swappable.
- A persistence layer behind a small interface: `save(key, value)` / `retrieve(key)`.
  SQLite is fine for one machine; swap for a shared/online store if multiple machines must
  share fingerprints.
- Similarity threshold config (default 0.40). Expose it; callers will tune per-site.

## To port this, you need:
- [ ] Element fingerprint extractor over your parser's element objects.
- [ ] A storage interface with two impls minimum: in-process (SQLite) and your shared store.
- [ ] A similarity scorer with per-field weights (start equal, then tune).
- [ ] Two call sites: one to save on success, one to relocate on selector-miss.
- [ ] A threshold + a "no match, best was X" warning path so failures are visible, not silent.

## Gotchas
- **Don't let one field be identity.** If you weight, say, an `id` attribute too high, a single
  attribute change defeats the whole system. Spread the weight.
- **`auto_save` + relocation edge cases bite.** Scrapling shipped a real fix for an IndexError
  in relocation when auto_save was enabled, and another for wrong scoring when two elements had
  mismatched attribute counts — handle empty candidate lists and unequal-length comparisons.
- **Threshold of 0 is a trap.** Early versions defaulted to 0 (everything "matches"); they moved
  to 0.40. Don't default to 0 — you'll return garbage confidently.
- **SQLite concurrency.** Use WAL mode if multiple workers hit the same DB, or you'll get locks.
- **It is best-effort.** Major redesigns legitimately break it. Surface confidence to the caller;
  never present a low-confidence relocation as certain.

## Origin (reference only)
Repo: https://github.com/D4Vinci/Scrapling — adaptive parsing engine (Selector class +
scrapling.core.storage StorageSystemMixin). Docs: scrapling.readthedocs.io adaptive parsing.
If the repo is reachable, the storage adaptor interface and similarity scorer are the files to read.
