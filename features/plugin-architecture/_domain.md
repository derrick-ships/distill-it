# Domain: plugin-architecture

Patterns for making a library extensible by third parties via Python entry points, without modifying the core package.

## What this domain is about

Plugin architecture is the practice of defining a stable contract (interface + registration protocol) that external packages can implement to inject new behavior into a host library at runtime. The host discovers and loads plugins lazily via Python's `importlib.metadata` entry points system.

## Key concerns

- **Discovery**: how the host finds installed plugins without a central registry
- **Interface versioning**: how to prevent ABI mismatches between host and plugin
- **Isolation**: plugins that fail to load should not crash the host
- **Registration callback**: the pattern for handing a plugin a reference to the host so it can register itself

## Features in this domain

- [[plugin-system--from-markitdown]] — entry-point-based plugin discovery and converter registration
