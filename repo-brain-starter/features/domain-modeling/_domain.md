# Domain: Domain Modeling

Features that connect *code* to *business* — mapping files and functions to the real-world
processes they implement (Order Management → Create Order → Validate Input). The common thread: a
three-level hierarchy (Domain → Flow → Step) laid over the structural graph, with ordered steps,
entities, and business rules extracted only from what the code actually does.

## Features in this domain
- [[business-domain-mapping--from-understand-anything]] — produces a domain-graph of
  `domain` / `flow` / `step` nodes with `contains_flow` and ordered `flow_step` edges, plus
  cross-domain interactions, entities, and business rules. (from Understand-Anything)

## Why this domain matters
Engineers think in files; the business thinks in processes. A layer that translates between them
makes a codebase legible to product, support, and new hires — and surfaces where business logic
actually lives. The "Domain → Flow → Step with ordered edges, grounded only in real code" pattern
is reusable for any code-to-process mapping. When studying a repo, anything mapping code to
business workflows belongs here.
