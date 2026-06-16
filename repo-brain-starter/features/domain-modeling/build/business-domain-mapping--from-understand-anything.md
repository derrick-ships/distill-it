# Business Domain Mapping (build spec) — distilled from Understand-Anything

## Summary
Map code to business processes as a domain-graph: a 3-level hierarchy (Domain → Flow → Step) with
`contains_flow` and ordered `flow_step` edges plus `cross_domain` links. Domains carry entities +
business rules; steps point at filePath/lineRange. Grounded strictly in real code.

## Core logic (inlined)
```
input: domain-context.json  OR  existing knowledge-graph.json
agent domain-analyzer builds:

nodes:
  domain node: { id:"domain:<kebab>", type:"domain", name,
                 domainMeta:{ entities[], businessRules[], crossDomainInteractions[] } }
  flow node:   { id:"flow:<kebab>",   type:"flow", name, entryPoint, entryType }
  step node:   { id:"step:<kebab>",   type:"step", name, filePath, lineRange:[s,e] }

edges:
  contains_flow: domain -> flow            (EVERY flow must have one)
  flow_step:     flow -> step, ORDERED via weight:
                 for N steps, weight increments by round(1/N, 1), bounded [0.0,1.0],
                 monotonically increasing == process order
  cross_domain:  domain <-> domain         (interactions)

constraints:
  - all ids kebab-case
  - do NOT invent flows/steps not present in code
  - weights monotonically increasing, within [0,1]

output: <root>/.understand-anything/intermediate/domain-analysis.json
        { project:{name,languages,frameworks,description,analyzedAt,gitCommitHash},
          nodes:[...], edges:[...] }
```

## Data contracts
`project` block same as the structural graph. Node/edge shapes as above. Three node types
(domain/flow/step), three edge types (contains_flow / flow_step / cross_domain). Ordering lives in
`flow_step.weight`.

## Dependencies & assumptions
- Either a preprocessed `domain-context.json` (file tree, entry points, exports/imports, snippets)
  or a completed `knowledge-graph.json`.
- An LLM (the domain-analyzer agent). No extra runtime.

## To port this, you need:
- [ ] A Domain/Flow/Step node vocabulary + contains_flow/flow_step/cross_domain edges.
- [ ] The ordered-edge-weight scheme (round(1/N,1) increments) to encode step order.
- [ ] kebab-case ID generation.
- [ ] A "ground in real code only" prompt constraint + filePath/lineRange on steps.
- [ ] (Optional) reuse your structural graph as input instead of re-extracting.

## Gotchas
- Don't let the model invent business flows — require every step to cite a real filePath/lineRange.
- Weights must stay monotonic and ≤1.0; with many steps round(1/N,1) can collide — verify strictly
  increasing (break ties by appending a small epsilon or use index-based ordering if N is large).
- Every flow needs a `contains_flow` to a domain or it orphans.

## Origin (reference only)
`understand-anything-plugin/agents/domain-analyzer.md`; surfaced via `/understand-domain`;
output `.understand-anything/intermediate/domain-analysis.json`.
