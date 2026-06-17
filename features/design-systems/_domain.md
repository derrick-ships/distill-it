# Domain: design-systems

Systems for defining brand-grade design decisions — typography, color, components, elevation, spacing, design tokens — once, in a single source of truth, then propagating them consistently to every consumer. Two patterns appear here: structured markdown specs injected into AI agents at generation time (open-design), and design tokens compiled to platform-native style code (style-dictionary).

## Features in this domain

- [[design-systems-library--from-open-design]] — 150 DESIGN.md files with fixed 9-section schema, zero-config discovery, CSS variable injection, and design system picker UI
- [[token-pipeline-orchestration--from-style-dictionary]] — the build engine: load+merge tokens → per-platform transform↔resolve convergence loop → filter → format → write files, on an abstracted (browser-capable) filesystem
- [[reference-resolution-engine--from-style-dictionary]] — resolves `{token.path}` aliases across the token graph: chains, multi-ref strings, object refs, number preservation, cycle detection, and safe `outputReferences`
- [[transforms-and-transform-groups--from-style-dictionary]] — composable name/value/attribute transforms with the CTI convention, ordered per-platform groups (css/ios/android/...), and the `transitive` flag for ref-derived values
