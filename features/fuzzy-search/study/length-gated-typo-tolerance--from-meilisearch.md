# Length-Gated Typo Tolerance — from [meilisearch](https://github.com/meilisearch/meilisearch)

> Domain: [[_domain]] · Source: https://github.com/meilisearch/meilisearch · NotebookLM: <add link>

## What it does
Lets search find results even when the query is misspelled or half-typed, without drowning in noise. Type "phnoe" and it still finds "phone"; type "lapt" and it finds "laptop." But it's careful: very short words must match exactly (so "cat" doesn't match "car"), and you can mark certain words as exact-only.

## Why it exists
Typo tolerance is the single feature people notice in a good search box, and the easiest to get wrong. Allow too many typos and every query matches everything; allow too few and real misspellings miss. The job is a typo policy that feels magic on long words and strict on short ones, configurable per index, and cheap enough to run on every keystroke.

## How it actually works
For each word in the query, the engine decides a typo budget before searching: by default a word gets 0 allowed typos if it's short, 1 typo once it passes a length threshold, and 2 typos once it's longer still (the thresholds are index settings). Words the index has marked "exact" always get 0, and a global switch can turn typo tolerance off entirely. The last word of the query is also treated as a prefix (so partial words match) unless prefix search is disabled.

With the budget decided, the query word becomes a small set of "derivations": the exact word, every index word within the allowed edit distance, and (for the last word) every index word that starts with it. That whole set is what actually gets looked up in the inverted index, and the ranking stage later prefers the derivations with fewer typos (so exact matches still win). Because the allowance is computed once up front (as a tiny function of word length and settings), the per-keystroke path stays fast.

## The non-obvious parts
- **Typo budget scales with length.** This is the core insight: 2 typos on a 4-letter word is nonsense, 2 typos on a 10-letter word is reasonable. Gating by length is what keeps fuzziness relevant.
- **Exact-words override.** Brand names, codes, IDs can be pinned to exact-only so "iphone" never fuzzes into "iphones-store."
- **Last word is a prefix.** Search-as-you-type works because the final, still-being-typed word matches by prefix, not exact.
- **Derivations feed ranking.** Fuzziness widens the candidate net, but the typo ranking rule then prefers fewer-typo matches, so tolerance doesn't hurt precision at the top.
- **Precomputed allowance.** The typo count is a cheap closure over settings, not recomputed per index word.

## Related
- [[adaptive-element-relocation--from-scrapling]] — the same "match by fuzzy similarity within a threshold" idea, applied to relocating DOM elements.
- [[ranking-rules-bucket-sort--from-meilisearch]] — consumes these derivations; the Typo rule ranks by them.
