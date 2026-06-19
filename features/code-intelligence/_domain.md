# Domain: code-intelligence

Tools and infrastructure that give AI agents (or humans) semantic, symbol-level understanding of a codebase — going beyond raw text search to understand *what* code means: what a symbol is, where it's defined, what references it, what its type hierarchy is, and how to edit it safely.

Distinct from `code-generation` (producing new code) and `diagnostics` (runtime/build errors). This domain is about **navigating and editing code by its structure**, not by its line numbers or text patterns.

## Features in this domain
- [[semantic-symbol-tools--from-serena]] — LSP-backed symbol find/navigate/edit toolkit for AI coding agents
