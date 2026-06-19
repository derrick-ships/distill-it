# Domain: ui-architecture

How a front-end is *structured* — the shell, the routing, the component boundaries, and the data-driven rendering patterns that let one UI scale to many features and ship to multiple targets (web + desktop) from a single codebase.

## What this domain is about

This domain is not about visual styling; it's about the skeleton. It covers the patterns that keep a large feature-rich UI maintainable: a single app shell that hosts many interchangeable "modes" or "studios," schema-driven forms that build themselves from config instead of being hand-coded per feature, shared component libraries consumed by more than one app (e.g. a web build and an Electron build), and the wiring that connects UI state to credentials and async work.

## Key design principle

**Push variation into data, keep the shell generic.** A good UI architecture has a thin, stable shell and lets the differences between features live in configuration (a model registry, a tab list, a parameter schema) rather than in bespoke screens. The same shell then renders any number of features, and adding one is a data edit. The shell also owns cross-cutting concerns — auth state, the key modal, drag-and-drop, history — so individual features don't each reinvent them.

## Features in this domain

- [[multi-studio-shell-architecture--from-open-generative-ai]] — one shared component library exports ~12 "studios"; a single tab-switching shell mounts any of them, owns API-key/auth/balance state, and is reused unchanged by both the web (Next.js) and desktop (Electron) builds.
