# Adaptive Element Relocation — from [Scrapling](https://github.com/D4Vinci/Scrapling)

> Domain: [[_domain]] · Source: https://github.com/D4Vinci/Scrapling · NotebookLM: <add link after upload>

## What it does
You scrape a website today and grab some element — say a product price — with a normal
CSS selector like `.product`. Weeks later the site gets redesigned and that selector now
points to nothing; a normal scraper silently breaks. Scrapling's adaptive feature lets the
scraper *find that element again on its own*, even though the selector no longer matches,
by remembering what the element "looked like" and locating the closest match on the new page.

## Why it exists
The single most expensive, soul-draining part of running scrapers at scale is maintenance:
sites change their HTML constantly, and every change snaps your selectors. The whole product
is built around killing that maintenance loop. This feature is Scrapling's reason to exist —
its headline differentiator. Everything else it does (fast fetching, stealth, a shell) is
table stakes other libraries also offer; *this* is the thing you can't easily get elsewhere.

## How it actually works
Think of it as taking a fingerprint of an element, then later doing facial recognition to
find it again.

1. **Fingerprint on first scrape.** The first time you select an element, you pass a flag
   (`auto_save=True`). Scrapling records a bundle of properties about that element: its tag
   name, its text, its attributes (names and values), its siblings (their tag names), its
   path through the page (tag names only), and even facts about its *parent* (tag, attributes,
   text). No single one of these is treated as an identity — because a website owner could
   change any of them.

2. **Store it keyed by domain + an identifier.** It saves that fingerprint to a small local
   database (SQLite by default). Nothing about the element itself can be the database key
   (it might all change), so the key is two things: the **website's domain**, and an
   **identifier** for that element (often derived automatically). Together those let it pull
   the right fingerprint back later.

3. **Relocate when the selector fails.** Later, when the page has changed and your selector
   returns nothing, you pass `adaptive=True`. Scrapling pulls the stored fingerprint, then
   scores *every* element on the new page for how similar it is — not an exact match, a
   fuzzy similarity across all those remembered properties. The highest-scoring element(s)
   above a threshold get returned. As of recent versions the default threshold is 40%
   similarity, and if nothing clears the bar it warns you with the best score it saw so you
   can decide whether to lower it.

That's the whole trick: don't trust the selector as identity; trust a fuzzy fingerprint and
re-find the element by resemblance.

## The non-obvious parts
- **It's opt-in twice, on purpose.** You save (`auto_save`) on the first run and relocate
  (`adaptive`) on later runs — two separate switches. Newcomers expect one magic "adaptive"
  flag; the two-phase design (record now, recover later) is the actual mental model.
- **Nothing about the element is a stable ID** — that realization is the heart of the design.
  The domain+identifier key exists *because* the element's own properties are all untrustworthy.
- **It degrades, it doesn't guarantee.** Small/incremental layout shifts → it recovers.
  Full redesigns → it can still break. It reduces maintenance, doesn't abolish it. Honest
  framing matters when deciding whether to rely on it.
- **The storage is pluggable.** SQLite is default, but you can swap in your own backend
  (even an online DB like Firebase) so multiple scrapers on different machines share
  fingerprints. That "shared memory across a fleet of scrapers" idea is quietly powerful.

## Related
- [[fingerprint-storage-system]] (the pluggable SQLite/online store this depends on)
- [[find-similar-fallback]] (structural-similarity search used when primary match fails)
- See also: AutoScraper does similarity matching too, but ~5x slower in Scrapling's benchmark
