# browser-use

- **Source:** https://github.com/browser-use/browser-use
- **Product:** Open-source Python framework that lets an LLM control a real web browser to accomplish tasks ("make websites accessible for AI agents"). You give it a task + an LLM; it perceives the page as an indexed element list, decides actions, and drives Chromium via CDP in a think->act->observe loop.
- **Stack:** Python 3.11+ · Chrome DevTools Protocol (via `cdp_use`, not Playwright at runtime) · Pydantic v2 · an in-house multi-provider LLM layer (no LangChain) · `bubus` event bus
- **Providers:** OpenAI, Anthropic, Google Gemini, Groq, Azure, AWS, DeepSeek, Ollama, OpenRouter, Mistral, LiteLLM, and a native ChatBrowserUse gateway
- **Date distilled:** 2026-06-19

## Architecture in one breath
A `BrowserSession` (event-bus + watchdogs) owns a CDP-controlled Chromium. Each step the `DomService` captures the page (4 parallel CDP calls) and serializes it to an indexed, filtered element list; the `Agent` builds a 3-slot message, calls the LLM through a unified `BaseChatModel` with a forced Pydantic `AgentOutput` schema, and dispatches the chosen actions through a decorator-based `Tools` registry — looping with layered failure-recovery until done. Five reusable subsystems, one product.

## Features distilled

| Feature | Domain | Study | Build |
|---|---|---|---|
| Indexed DOM Serialization | web-extraction | [study](../features/web-extraction/study/indexed-dom-serialization--from-browser-use.md) | [build](../features/web-extraction/build/indexed-dom-serialization--from-browser-use.md) |
| Agent Loop & Recovery | agent-architecture | [study](../features/agent-architecture/study/agent-loop-recovery--from-browser-use.md) | [build](../features/agent-architecture/build/agent-loop-recovery--from-browser-use.md) |
| Action / Tool Registry | agent-architecture | [study](../features/agent-architecture/study/action-tool-registry--from-browser-use.md) | [build](../features/agent-architecture/build/action-tool-registry--from-browser-use.md) |
| Multi-Provider LLM Abstraction | ai-integration | [study](../features/ai-integration/study/multi-provider-llm-abstraction--from-browser-use.md) | [build](../features/ai-integration/build/multi-provider-llm-abstraction--from-browser-use.md) |
| Browser Session & Stealth | browser-automation | [study](../features/browser-automation/study/browser-session-stealth--from-browser-use.md) | [build](../features/browser-automation/build/browser-session-stealth--from-browser-use.md) |

## Source files (reference only — repo may be gone later)
- `browser_use/dom/` — `service.py`, `enhanced_snapshot.py`, `views.py`, `serializer/` (indexed DOM serialization).
- `browser_use/agent/` — `service.py` (the loop), `views.py` (AgentOutput/state/history), `message_manager/`, `prompts.py`.
- `browser_use/tools/` — `service.py` (Tools + built-in actions), `registry/service.py` + `registry/views.py` (decorator registry), `views.py` (action param models).
- `browser_use/llm/` — `base.py` (Protocol), `messages.py`, `views.py`, `schema.py`, per-provider `openai/`, `anthropic/`, `google/`, etc.
- `browser_use/browser/` — `profile.py`, `session.py`, `session_manager.py`, `events.py`, `watchdogs/` (session + stealth).
