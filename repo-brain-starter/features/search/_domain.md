# Domain: Search

Features that find the right node in a large graph — by name (fuzzy/lexical) or by meaning
(semantic) — and then expand the hit into useful local context. The common thread: retrieval is
not just "match a string," it's "match, then walk one hop out to neighbors and their edges and
layers" so the answer carries its surroundings.

## Features in this domain
- [[graph-search-retrieval--from-understand-anything]] — a `SearchEngine` over graph nodes plus
  one-hop edge expansion to build a focused context window for an LLM chat, instead of dumping
  the whole graph. (from Understand-Anything)

## Why this domain matters
Every "ask questions about your codebase" feature is a retrieval problem in disguise. The trick
that makes it work — match a small set of seed nodes, then expand along edges to pull in just
their neighborhood — is a general RAG-over-a-graph pattern. When studying a repo, anything that
selects a relevant subgraph to feed a model belongs here.
