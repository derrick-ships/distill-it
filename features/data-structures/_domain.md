# Domain: data-structures

Foundational data representations that make higher-level features possible. Covers ordering schemes, identifiers, and the invariants/repair logic that keep them valid — especially structures designed to survive concurrent editing with minimal conflict surface.

## Features in this domain

- [[fractional-indexing--from-excalidraw]] — string order keys (base-62) where any two have a key between them, so insert/move/reorder mutates only one item; invariant `predecessor < current < successor` with detect-and-repair; jittered key generation for collision-free concurrent inserts.
- [[mbql-query-ast--from-metabase]] — a database-agnostic query as a typed nested data structure (tagged-vector clauses) formally specified by a schema. The query is DATA, not a SQL string, so permissions/drill-through/params are all just map transforms. The spine the whole BI product hangs on.
