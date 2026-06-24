# Domain: search-relevance

Ordering search results by relevance: turning a candidate set of matching documents into a ranked list using a defined, multi-stage policy rather than a single score.

## What this domain is about
Full-text search has two halves: finding candidates and ordering them. This domain is the ordering. The interesting engineering is making relevance a transparent, tunable cascade of rules (match count, typos, term proximity, field importance, exactness, custom sorts) instead of one opaque scoring function, and doing it fast over large candidate sets.

## Key design principle
Relevance is a lexicographic cascade. Apply ranking rules in a fixed priority order; each rule partitions the still-tied documents into buckets; the next rule only breaks ties within a bucket. Represent candidate sets as compressed bitmaps so each partition is fast set algebra.

## Features in this domain
- [[ranking-rules-bucket-sort--from-meilisearch]] — Meilisearch's ordered ranking-rule cascade (words, typo, proximity, attribute, sort, exactness) applied as a bucket sort over RoaringBitmap candidate sets.
