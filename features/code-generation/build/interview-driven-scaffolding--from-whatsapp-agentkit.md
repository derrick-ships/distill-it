# Interview-Driven App Scaffolding (build spec) — distilled from whatsapp-agentkit

## Summary
Build a Claude-Code-native "kit" that turns a guided interview into a complete, generated application. The shipped artifact is **not code** — it's an orchestration prompt (`CLAUDE.md`) plus a slash command (`.claude/commands/<name>.md`) that drives a strict, phase-gated state machine: verify env → interview the user one question at a time → generate the full app from inline templates parameterized by the answers → test locally → optionally deploy. The model both *instantiates templates* (fill the `[SLOTS]`) and *reasons* (writes use-case-specific code, folds user knowledge files into a system prompt). Generate only the variant the user chose, never all variants.

## Core logic (inlined)

### The two entry files

**`start.sh`** — prerequisite gate, nothing more:
```bash
#!/bin/bash
set -e
# 1) check python3 exists and is >= 3.11 (exit 1 with install URL if not)
PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then exit 1; fi
# 2) check `claude` on PATH (else print: npm install -g @anthropic-ai/claude-code)
command -v claude &> /dev/null || { echo "install claude code"; exit 1; }
# 3) mkdir -p knowledge
# 4) tell the user to run `claude` then type the slash command
```

**`.claude/commands/build-agent.md`** — thin trigger; the whole point is it delegates to CLAUDE.md:
```
Lee el archivo CLAUDE.md completo. Contiene todas las instrucciones detalladas.
Ejecuta el flujo de onboarding siguiendo las 5 fases EN ORDEN:
FASE 1 — verificación del entorno (python>=3.11, crear carpetas, requirements.txt, .env)
FASE 2 — entrevista (10 preguntas UNA POR UNA; P9 = proveedor; P10 = credenciales del elegido)
FASE 3 — generación (business.yaml, prompts.yaml, providers/, main.py, brain.py, memory.py,
         tools.py, test_local.py, Dockerfile, docker-compose.yml; configura .env)
FASE 4 — testing local (test_local.py; ajustar prompts.yaml hasta aprobación)
FASE 5 — deploy a Railway (solo si el usuario quiere)
REGLAS: español; una pregunta a la vez; nunca hardcodear keys; no avanzar sin confirmación;
        generar SOLO el adaptador del proveedor elegido (no los 3).
```

**`CLAUDE.md`** — the brain. Auto-loaded by Claude Code on session start. Holds: (1) a fixed persona, (2) a pinned tech stack + dependency list, (3) the target architecture diagram, (4) the full 5-phase script with **every code template inlined**, (5) behavioral rules. The phases are the algorithm:

```
PHASE 1  verify python>=3.11 → mkdir -p agent/providers config knowledge tests
         → write requirements.txt → pip install -r → cp .env.example .env
PHASE 2  ask Q1..Q10 sequentially, BLOCK on each answer. Branch Q10 on Q9's provider choice.
         If user lacks an account, walk them through creating it.
PHASE 3  with all answers: render each template file, substituting [SLOTS] from answers;
         read any files in /knowledge and paste their text into the system prompt;
         emit ONLY the chosen provider's adapter.
PHASE 4  run the terminal simulator; loop: if user unhappy → edit prompts.yaml → rerun.
         Do not proceed without explicit "yes".
PHASE 5  (opt-in) docker build → swap dev .gitignore for prod .gitignore → Railway steps.
```

### The interview (Phase 2) — the parameter-collection step
Ten questions, asked one at a time. The answers are the generation parameters:
1. Business name → `business.yaml.negocio.nombre`, system-prompt identity
2. What the business does → system-prompt "Sobre el negocio"
3. Use cases (FAQ / scheduling / sales-leads / orders / support / other) → which functions to write in `tools.py`
4. Agent display name → system-prompt identity
5. Tone (formal / friendly / salesy / warm) → system-prompt behavior
6. Hours → out-of-hours fallback line
7. Knowledge files? → if yes, read `/knowledge/*` and inline into the prompt
8. Anthropic API key → `.env` `ANTHROPIC_API_KEY`
9. **Provider: Twilio (free sandbox, recommended) or Meta Cloud API** → `WHATSAPP_PROVIDER`, which adapter to emit
10. Provider-specific credentials (Meta: access token, phone-number-id, verify-token; Twilio: account SID, auth token, WhatsApp number)

### Generation (Phase 3) — template instantiation + reasoning
The system prompt template (`config/prompts.yaml`) is the highest-leverage output. Its shape:
```yaml
system_prompt: |
  Eres [AGENT_NAME], el asistente virtual de [BUSINESS_NAME].
  ## Tu identidad   → name, business, tone (with a tone-specific description)
  ## Sobre el negocio → [BUSINESS_DESCRIPTION]
  ## Tus capacidades  → derived from chosen use cases
  ## Información del negocio → [VERBATIM TEXT OF /knowledge FILES]
  ## Horario → [HOURS] + an out-of-hours canned reply
  ## Reglas de comportamiento:
    - always Spanish; stay in-tone
    - if you don't know: offer to connect to a human (do NOT invent)
    - NEVER invent prices/data not in the knowledge base
    - concise but useful; empathize if user is frustrated; end with a CTA when apt
fallback_message: "..."   # used for too-short/empty inbound messages
error_message: "..."      # used when the model call throws
```
`tools.py` is generated *conditionally* on use cases — the kit ships a base (`buscar_en_knowledge`, `obtener_horario`) and the model adds functions like `reservar_cita`, `agregar_al_carrito`, `registrar_lead`, `crear_ticket` per the chosen use case. (See the sibling build docs for the provider layer and memory.)

## Data contracts
- **Interview answers** → an in-session dict the agent holds; optionally persisted to `config/session.yaml` if the user pauses.
- **`config/business.yaml`**: `{negocio:{nombre,descripcion,horario}, agente:{nombre,tono,casos_de_uso[]}, metadata:{creado,version}}`
- **`config/prompts.yaml`**: `{system_prompt:str, fallback_message:str, error_message:str}`
- **`.env`** (only chosen provider's vars): `ANTHROPIC_API_KEY`, `WHATSAPP_PROVIDER` (`meta|twilio`), provider vars, `PORT=8000`, `ENVIRONMENT`, `DATABASE_URL` (`sqlite+aiosqlite:///./agentkit.db` local / `postgresql+asyncpg://…` prod).

## Dependencies & assumptions
- **Claude Code** is the runtime; the user must have it installed and authenticated. The kit is useless without an agentic coding tool that auto-reads `CLAUDE.md` and supports slash commands — that's the hard dependency.
- Generated app stack (pinned in `requirements.txt`): `fastapi>=0.104`, `uvicorn[standard]>=0.24`, `anthropic>=0.40`, `httpx>=0.25`, `python-dotenv>=1.0`, `sqlalchemy>=2.0`, `pyyaml>=6.0.1`, `aiosqlite>=0.19`, `python-multipart>=0.0.6`.
- Model id used by generated code: `claude-sonnet-4-6`.
- Assumes the business's knowledge fits in a single system prompt (no RAG).

## To port this, you need:
- [ ] An agentic coding host that auto-loads a project instruction file (Claude Code's `CLAUDE.md`, Cursor rules, etc.) and supports a user-invoked command.
- [ ] A `CLAUDE.md` (or equivalent) carrying: persona, pinned stack, target architecture, and **the full set of code templates with `[SLOT]` markers** for every file the app needs.
- [ ] A slash command that just says "read the brain and run the phases in order."
- [ ] A `start.sh`/prereq check appropriate to your stack.
- [ ] A `.env.example` enumerating every variable across all variants (commented per-variant).
- [ ] Two `.gitignore` strategies: dev (excludes generated artifacts to keep the kit repo clean) and prod (ships them) — and an explicit instruction to swap before deploy.

## Gotchas
- **The kit repo's dev `.gitignore` excludes the generated app** (`agent/`, `config/`, etc.). If the user pushes to a host without swapping to the prod `.gitignore`, they deploy an empty repo. Make the swap an explicit, non-skippable step.
- **Phase-gating must be enforced in the prompt**, or the agent races ahead and overwhelms a non-technical user. Spell out "one question at a time, never advance without confirmation."
- **"Generate only the chosen variant"** must be explicit too — models default to scaffolding everything. Emitting all adapters bloats the output and confuses the owner.
- **Secrets:** the method forbids hardcoding keys (python-dotenv only) and keeps `.env` gitignored in both modes. Don't let generated code bake keys into source.
- **Knowledge inlining has a ceiling**: large catalogs blow the context/prompt budget. Fine for SMBs; for bigger corpora you'd need to swap the inline approach for retrieval.
- **No webhook signature verification** is generated (Meta's `validar_webhook` only handles the GET challenge; Twilio's signature isn't checked). Add it before trusting inbound traffic in production.

## Origin (reference only)
Repo: https://github.com/Hainrixz/whatsapp-agentkit · Files: `CLAUDE.md` (the brain + all templates), `.claude/commands/build-agent.md` (trigger), `start.sh`, `.env.example`. The `agent/` tree referenced in the README does not exist in the repo — it is generated by the method at runtime.
