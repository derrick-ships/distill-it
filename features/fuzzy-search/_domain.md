# Domain: fuzzy-search

Matching queries to content despite differences: typos, prefixes, and near-misses, so a search finds what the user meant, not only what they typed exactly.

## What this domain is about
Exact matching fails real users: they mistype, they search-as-they-type (incomplete words), they don't know exact spellings. This domain is the controlled fuzziness that fixes that, expanding a query term into the set of index words it should be allowed to match, with limits so "fuzzy" doesn't become "irrelevant."

## Key design principle
Fuzziness must be bounded and earned. Allow more typos only for longer words (a 3-letter word with 2 typos matches almost anything); let the index force exact matches for chosen words; treat the last word as a prefix for search-as-you-type. Precompute the allowance so the hot path is a lookup, not a calculation.

## Features in this domain
- [[length-gated-typo-tolerance--from-meilisearch]] — Meilisearch's typo policy: typo budget gated by word length, an exact-words override, and last-word prefix expansion.
