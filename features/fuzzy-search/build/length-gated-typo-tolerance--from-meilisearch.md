# Length-Gated Typo Tolerance (build spec) — distilled from meilisearch

## Summary
Expand each query word into the set of index words it may match (exact + within-edit-distance + prefix), with the typo budget gated by word length, an exact-words override, and last-word prefix search. Compute the budget once; keep the hot path a lookup.

## Core logic (inlined)

**1. The typo-budget policy** (`crates/milli/src/search/new/query_term/parse_query.rs`, `number_of_typos_allowed`):
```rust
// returns a closure word -> allowed_typos (u8), precomputed from index settings
let authorize_typos    = index.authorize_typos();        // global on/off
let min_len_one_typo   = index.min_word_len_one_typo();   // e.g. 5
let min_len_two_typos  = index.min_word_len_two_typos();  // e.g. 9
let exact_words        = index.exact_words();             // FST of words forced to 0 typos
move |word: &str| -> u8 {
    let n = word.chars().count();
    if !authorize_typos
        || n < min_len_one_typo
        || exact_words.map_or(false, |fst| fst.contains(word)) { 0 }
    else if n < min_len_two_typos { 1 }
    else { 2 }
}
```

**2. Word -> derivations.** With the budget `k` for a word, build the set of index words to actually search:
```
derivations(word, k, is_last_word):
    set = { word }                                  // exact
    set += index_words within edit_distance <= k    // typo variants (use a Levenshtein automaton / DFA
                                                    //   intersected with the words FST for speed)
    if is_last_word and prefix_search_allowed:
        set += index_words starting_with(word)       // prefix (FST range scan)
    return set   // looked up in the inverted index; each derivation tagged with its typo cost for ranking
```
Meilisearch represents these as a `QueryTermSubset` (interned derivations) attached to the term's position; the last token also gets prefix expansion (`parse_query` + `is_prefix_search_allowed`).

**3. Feed ranking.** Each derivation carries its typo cost (0 for exact/prefix-exact, 1, 2). The Typo ranking rule later buckets documents by the cheapest total typo cost across the query's terms, so exact matches rank above fuzzy ones.

## Data contracts
- Settings: `authorize_typos: bool`, `min_word_len_one_typo: u8`, `min_word_len_two_typos: u8`, `exact_words: FST<set>`, `prefix_search: bool`.
- A words dictionary as an FST (finite-state transducer) for fast prefix range scans and edit-distance intersection.

## Dependencies & assumptions
- An FST library for the words dictionary (Meilisearch uses `fst`), and a Levenshtein automaton to intersect "all words within k edits" against it. An inverted index keyed by word.
- Pattern is language-agnostic; for a smaller corpus you can replace FST+automaton with a trie + bounded BK-tree or even precomputed deletions.

## To port this, you need:
- [ ] A length-gated typo-budget function over your index settings (the closure above).
- [ ] A way to enumerate index words within k edits of a query word (FST + Levenshtein automaton, or a BK-tree).
- [ ] Prefix expansion for the last query token (FST range scan / trie subtree).
- [ ] Per-derivation typo cost passed to your ranker so exact still wins.

## Gotchas
- **Short-word over-fuzzing is the classic bug.** Gate by length; never allow 2 typos on a 4-char word.
- Edit-distance over a whole dictionary is only cheap with an FST/automaton or a precomputed structure, naive comparison per word does not scale.
- Prefix on the last word only; prefixing every word explodes the candidate set.
- Keep the budget a pure function of length+settings so it can run per keystroke.

## Origin (reference only)
`crates/milli/src/search/new/query_term/{mod.rs,parse_query.rs,compute_derivations.rs}`, `crates/milli/src/search/new/ranking_rule_graph/typo/`.
