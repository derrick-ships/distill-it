# Domain: code-generation

Using an LLM to write *runnable code* as the deliverable, rather than to produce data directly. The model's output is a program — typically to be executed afterward — that does the actual work. The payoff is amortization: pay the LLM once to author the routine, then run that routine many times for free.

## Features studied
- [[scraper-code-generation--from-llm-scraper]] — generate a self-contained IIFE that extracts a schema's worth of data from a page, so you don't pay per-scrape LLM cost on every run.
- [[interview-driven-scaffolding--from-whatsapp-agentkit]] — the product IS a prompt: a guided 5-phase interview drives Claude Code to generate a complete, deployable app from inline templates parameterized by the user's answers (LLM as one-time app author, at whole-app scale).
- [[connector-builder-test-read--from-airbyte]] — backend for a no-code builder: run a bounded, instrumented test read of an in-progress config with the SAME production engine (capped by max_records/pages/slices, capturing every HTTP request↔response + inferred schema), returned over the existing protocol. Zero preview/prod drift — the live-feedback pattern for config-driven tools.

## Cross-domain links
- Alternative-to [[schema-driven-extraction--from-llm-scraper]] — same goal (typed data from a page), opposite cost model (codegen once vs. inference every time).
- Consumes [[content-preprocessing]] — the page content is fed to the model as context for the code it writes.
