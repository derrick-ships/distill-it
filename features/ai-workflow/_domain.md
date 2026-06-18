# Domain: ai-workflow

Orchestration systems that turn user intent into multi-step agent-driven execution pipelines. Covers iterative design loops, agent CLI detection and spawning, streaming output into sandboxed previews, and convergence mechanics.

## Features in this domain

- [[agentic-loop--from-open-design]] — 3-stage plan→generate→critique pipeline with intra-stage refinement loops
- [[agent-cli-integration--from-open-design]] — detects 22+ installed coding-agent CLIs, streams output via SSE into sandboxed iframe preview
- [[chat-completion-middleware--from-open-webui]] — one ordered async pipeline (filters→memory→web search→image→code→tools→files) mutating a shared form_data; native-FC exposes capabilities as tools vs non-native prompt-injection + separate task-model tool selection; merges server/MCP/terminal/builtin tools into one tools_dict; POST-phase outlet filters + background title/tag/follow-up tasks
