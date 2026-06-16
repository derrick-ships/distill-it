# Domain: Onboarding

Features that take a new person (or agent) from "I have never seen this codebase" to "I know
where to start and why" — guided tours, dependency-ordered walkthroughs, generated onboarding
docs. The common thread: don't show files alphabetically; show them in *pedagogical* order
derived from the graph (entry points first, then their dependencies), with a narrative.

## Features in this domain
- [[dependency-ordered-guided-tours--from-understand-anything]] — a deterministic graph-analysis
  script (fan-in/fan-out, entry-point scoring, BFS depth map, coupled clusters) feeds an LLM that
  designs a 5–15 step tour with optional language lessons. (from Understand-Anything)

## Why this domain matters
The hardest part of any codebase is knowing where to begin. A tour that's ordered by actual
dependency structure — not by folder name — is the difference between onboarding in an hour and
onboarding in a week. The "compute structural signals deterministically, then let the LLM narrate
the path" split is reusable for any teach-me-this-system feature.
