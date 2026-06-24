# Ranking-Rules Bucket Sort (build spec) — distilled from meilisearch

## Summary
Rank search candidates by a fixed, reorderable cascade of ranking rules applied as a bucket sort over compressed bitmaps. Each rule breaks ties left by the previous; you only sort as deep as the requested page.

## Core logic (inlined)

**1. The ranking rules, in priority order** (`crates/milli/src/criterion.rs`):
```rust
enum Criterion {
    Words,       // by DECREASING number of matched query terms
    Typo,        // by INCREASING number of typos
    Proximity,   // by INCREASING distance between matched terms
    Attribute,   // matches in more important fields + nearer the front rank higher
    Sort,        // caller-specified asc/desc on a field, at query time
    Exactness,   // closer to the exact query terms ranks higher
    Asc(String), Desc(String), // custom numeric/date sorts inserted anywhere in the list
}
// An index stores this as an ordered list; reordering it changes ranking with no code change.
```

**2. The bucket sort** (`crates/milli/src/search/new/bucket_sort.rs`, conceptually):
```
universe: Bitmap = all docs matching the query at all      // RoaringBitmap of doc ids
rules: [RankingRule]                                        // in the order above
result: Vec<DocId>
fn rank(universe, rules[0..], result, needed):
    if rules empty or |result| >= needed: result += universe (any order); return
    rule = rules[0]
    rule.start(universe)
    while let Some(bucket) = rule.next_bucket():            // bucket ⊆ universe, in rank order
        rank(bucket, rules[1..], result, needed)           // recurse: next rule breaks ties inside the bucket
        if |result| >= needed: break                       // lazy: stop once the page is filled
```
Each rule partitions the still-tied set into ordered buckets; ties fall through to the next rule. Everything is bitmap intersection/difference, not per-doc scoring.

**3. Typo & proximity as graph costs.** A query is a graph of terms; each term has derivations (exact, typo-1, typo-2, prefix, synonym). The Typo rule yields buckets by total typo cost of the cheapest way the terms appear in a doc; Proximity by the cheapest total gap. These are shortest-path problems over the query-term graph (`ranking_rule_graph/{typo,proximity}`), not string distance per document.

## Data contracts
- Candidate set + every bucket: a compressed bitmap of integer doc ids (RoaringBitmap or equivalent).
- Per-(term, document) you need: which derivation matched (for typo cost), positions (for proximity/attribute), field id + field weight (for attribute).

## Dependencies & assumptions
- A compressed-bitmap library (RoaringBitmap). An inverted index that, per query term, gives the doc set + positions. A way to expand a word into typo/prefix derivations (see the typo feature).
- Language-agnostic pattern; Meilisearch is Rust + `roaring`.

## To port this, you need:
- [ ] Ranking rules as an ordered list, each exposing `start(universe)` + `next_bucket() -> Option<Bitmap>` in rank order.
- [ ] A recursive bucket-sort driver that stops at the requested page depth.
- [ ] Doc sets as bitmaps so partitioning is set algebra.
- [ ] (For typo/proximity) a query-term graph + a cheapest-path cost per document.

## Gotchas
- **Don't fully sort the tail.** The whole point is laziness, stop once the page is filled or you lose the speed.
- Lexicographic ≠ weighted: a later rule can NEVER override an earlier one. Choose the order deliberately.
- Exactness/attribute need term positions stored at index time; retrofitting them later is expensive.
- Custom `Sort` mid-cascade means the rules after it only tie-break within equal sort values.

## Origin (reference only)
`crates/milli/src/criterion.rs`, `crates/milli/src/search/new/{bucket_sort.rs,ranking_rules.rs,graph_based_ranking_rule.rs,ranking_rule_graph/}`, `exact_attribute.rs`, `sort.rs`.
