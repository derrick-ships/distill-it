# Interview-Driven App Scaffolding — from [whatsapp-agentkit](https://github.com/Hainrixz/whatsapp-agentkit)

> Domain: [[_domain]] · Source: https://github.com/Hainrixz/whatsapp-agentkit · NotebookLM: <add link>

## What it does
A non-technical business owner runs one command (`/build-agent`) inside Claude Code, answers ten plain-language questions about their business — name, what they sell, what they want the bot to do, tone, hours, their API keys — and ~20 minutes later they have a complete, working, deployable WhatsApp AI customer-service bot. They never see or write code. The repo they cloned ships almost nothing executable: no `agent/`, no server, no templates-as-files. The entire product is a *prompt* that tells Claude Code how to interview the user and then author the whole application from scratch, tailored to their answers.

## Why it exists
There's a huge gap between "I want an AI bot for my business" and the reality of standing one up: API accounts, webhook plumbing, a server, conversation memory, a system prompt that doesn't hallucinate prices, Docker, hosting. Each step loses non-technical owners. AgentKit's bet is that an LLM coding agent can collapse that whole gap into a conversation — the human supplies *intent* and *credentials*, the agent supplies *all the engineering*. The job-to-be-done is "turn my business knowledge into a deployed bot without learning to code," and the product monetizes nothing directly (MIT-licensed) — it's a distribution/lead vehicle that also happens to consume Anthropic API tokens at runtime.

## How it actually works
The cleverness is entirely in the orchestration prompt. Two files carry it: `CLAUDE.md` (the "brain" — auto-loaded by Claude Code, holds the full method and every code template) and `.claude/commands/build-agent.md` (a thin slash command that says "read CLAUDE.md and run the 5 phases in order"). A `start.sh` script just checks prerequisites (Python 3.11+, Claude Code installed) and tells the user to type `/build-agent`.

The method is a strict five-phase state machine the agent walks the user through, never skipping ahead, announcing "Phase X of 5" at each step:

1. **Environment check & scaffolding** — verify Python ≥ 3.11, create the folder skeleton (`agent/providers/ config/ knowledge/ tests/`), generate `requirements.txt`, `pip install`, copy `.env.example` to `.env`.
2. **The business interview** — ten questions, *one at a time, waiting for each answer*. Business name, what it does, use cases (FAQ / scheduling / sales / orders / support), the agent's display name, tone (formal / friendly / salesy / warm), hours, optional knowledge files dropped into `/knowledge`, the Anthropic key, and — question 9 — which WhatsApp provider (Twilio recommended for its free sandbox, or Meta Cloud API). Question 10 collects exactly the credentials for whichever provider they picked. If the user lacks any account, the agent walks them through getting it step by step.
3. **Generation** — with all answers in hand, the agent writes the entire app: a `business.yaml` and a *powerful, specific* `prompts.yaml` system prompt (incorporating any `/knowledge` file contents verbatim), the WhatsApp provider abstraction layer, the FastAPI webhook server, the Claude brain, the SQLite conversation memory, use-case-specific tools, a terminal test simulator, and Docker files. Crucially it generates **only the adapter for the chosen provider**, not all of them.
4. **Local testing** — runs a terminal chat simulator so the owner talks to their bot before any WhatsApp wiring. If the answers feel off, the agent edits `prompts.yaml` and they try again. It will not move on without explicit approval.
5. **Deploy (optional)** — only if asked: Docker build, swap the dev `.gitignore` for a production one (the dev one *excludes* the generated `agent/`, `config/` etc. to keep the template repo clean — but for deploy those files must ship), then step-by-step Railway + webhook setup specific to the chosen provider.

The whole flow is conducted in Spanish, with a fixed, friendly persona ("ask one thing at a time, never give up, celebrate each phase").

## The non-obvious parts
- **The product is a prompt, not a program.** What's distributed is a method and a set of inline code templates living *inside a markdown file*. The "software" materializes only when an LLM executes the instructions. This is the whole insight worth stealing: for a well-bounded app shape, you can ship the *recipe* and let the agent bake the cake per customer.
- **Templates with holes, filled by interview.** The code in `CLAUDE.md` isn't generic boilerplate — it has explicit `[NOMBRE_NEGOCIO]`-style slots and conditional branches ("if Meta… / if Twilio…"). The interview answers are the parameters; generation is template instantiation done by a model rather than a templating engine, which lets it also *reason* (e.g. write business-specific tools, fold knowledge files into the prompt).
- **"Generate only the chosen provider" is a deliberate simplicity rule.** A lesser design would scaffold all adapters and switch at runtime. AgentKit keeps the generated repo minimal — fewer files the non-technical owner could be confused by — at the cost of regeneration if they switch later.
- **Phase-gating is a guardrail against LLM over-eagerness.** Coding agents love to do everything at once. The explicit "never advance without confirmation, one question at a time" rules exist precisely to stop the model from bulldozing a non-technical user.
- **The dev/prod `.gitignore` swap is a sharp real-world gotcha.** The template repo hides generated artifacts so it stays a clean "kit"; deploying needs the opposite. The method bakes in this reversal so the owner doesn't push an empty repo to Railway and wonder why nothing runs.
- **Knowledge files are inlined into the system prompt, not retrieved.** No RAG, no embeddings — the owner's menu/price-list/FAQ text is pasted straight into `prompts.yaml`. Simple, and fine for small businesses whose entire knowledge base fits in a prompt.

## Related
- [[whatsapp-provider-adapter--from-whatsapp-agentkit]] — the multi-provider abstraction this method generates.
- [[conversation-memory--from-whatsapp-agentkit]] — the per-contact memory it generates.
- See also: [[agent-output-contract--from-last30days-skill]] and [[ordered-backend-routing--from-agent-reach]] — other "the skill/prompt IS the product" agent-architecture patterns.
- See also: [[scraper-code-generation--from-llm-scraper]] — another "LLM authors code, not data" economic flip, at function scale rather than app scale.
