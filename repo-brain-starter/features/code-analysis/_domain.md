# Domain: Code Analysis

Features that turn a raw repository into structured, queryable facts about *what the code is and
does* — without a human reading it linearly. The common thread: pair a **deterministic parser**
(Tree-sitter, git, AST walks) that never hallucinates structure with an **LLM layer** that adds
the meaning a parser can't see (intent, purpose, business mapping). Structure is ground truth;
semantics are interpretation; keep them separable.

## Features in this domain
- [[multi-agent-analysis-pipeline--from-understand-anything]] — orchestrates 6 specialized
  subagents (scan → analyze → assemble → architecture → tour → review) with parallel,
  incremental file analysis. (from Understand-Anything)
- [[hybrid-static-semantic-extraction--from-understand-anything]] — Tree-sitter extracts
  functions/classes/imports deterministically; an LLM then writes summaries, tags, complexity.
  (from Understand-Anything)
- [[diff-impact-analysis--from-understand-anything]] — given changed files, computes the blast
  radius across the graph (contains-children + one-hop neighbors + affected layers). (from
  Understand-Anything)

## Why this domain matters
The expensive part of any "understand this codebase" tool is doing the analysis *cheaply,
reproducibly, and incrementally*. Anything that splits the work into a deterministic spine plus a
swappable LLM interpretation layer — and only re-runs the LLM on what changed — is the reusable
core. When studying a new repo, anything resembling "parse to a graph, then reason over the graph"
belongs here.
