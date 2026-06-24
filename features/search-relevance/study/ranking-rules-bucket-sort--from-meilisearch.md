# Ranking-Rules Bucket Sort — from [meilisearch](https://github.com/meilisearch/meilisearch)

> Domain: [[_domain]] · Source: https://github.com/meilisearch/meilisearch · NotebookLM: <add link>

## What it does
Decides what order search results come back in. When a query matches thousands of documents, this is the part that puts the most relevant ones first, and does it in a way you can understand and tune: results are ranked by how many query words matched, then by how few typos, then by how close the words are to each other, then by which field they appeared in, and so on.

## Why it exists
A single relevance score (like classic TF-IDF/BM25) is a black box: you can't easily say "I care about exact matches more than proximity here." Meilisearch's bet is that relevance should be an explicit, ordered list of rules the user can reorder per index. The job-to-be-done is great out-of-the-box ranking that's also transparent and tunable, fast enough for search-as-you-type.

## How it actually works
The order of importance is a fixed list of ranking rules: Words (more matched query terms first), Typo (fewer typos first), Proximity (matched words closer together first), Attribute (matches in more important fields, nearer the front, first), Sort (any custom asc/desc sort the caller asked for), and Exactness (closer to the exact query first). An index can reorder this list or add custom numeric sorts.

It's applied as a "bucket sort." Start with the whole candidate set (every document that matched at all), represented as a compressed bitmap of document ids. The first rule splits that set into ordered buckets, e.g., "matched 3 words," "matched 2 words," "matched 1 word." Within each bucket the documents are still tied, so the second rule (Typo) is applied to just that bucket to split it further, and so on down the list. You only ever run an expensive rule on the documents still tied at that level, and you stop as soon as you've filled the requested page. The whole thing is set algebra on bitmaps, which is why it stays fast even on big candidate sets.

The clever structural piece is that the query itself is a graph: a word can expand into several "derivations" (typo variants, prefixes, synonyms), and several rules (typo, proximity) are computed as cheapest-path problems over that graph. The ranking rule asks "what's the cheapest way these query terms appear in this document," and the cost is the rule's bucket.

## The non-obvious parts
- **Lexicographic, not weighted.** Rules don't sum into a score; each is a strict tie-breaker for the previous. That's what makes the behaviour predictable and reorderable.
- **Bitmaps make it cheap.** Candidate sets and every bucket are RoaringBitmaps; partitioning is intersection/difference, not per-document scoring.
- **Lazy and paginated.** A rule only runs on the documents still tied above the requested page; you don't fully sort the long tail.
- **The query is a graph.** Typo and proximity are shortest-path costs over a graph of query-term derivations, not per-document string math.
- **Per-index tunable.** Reordering the rule list (or inserting a custom sort) changes ranking with no code change.

## Related
- [[engagement-signal-ranking--from-last30days-skill]] — a different ranking philosophy (RRF + LLM rerank) for the same job of ordering candidates.
- [[length-gated-typo-tolerance--from-meilisearch]] — supplies the typo derivations the Typo rule ranks by.
