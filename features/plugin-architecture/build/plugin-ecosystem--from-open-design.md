# Plugin Ecosystem (build spec) — distilled from open-design

## Summary

Zero-registration discovery of skills and design systems via directory scan at daemon startup. Three tiers: official (bundled), community (registry-installed), user custom (local drop-in). plugin-runtime package normalizes all sources to PluginManifest. 22+ agent CLI adapters in `agents.ts` — each defines bin, versionArgs, buildArgs, streamFormat. Agent execution via stdio child processes.

## Core logic (inlined)

**Discovery on startup:**
```
scan skills/*/SKILL.md          → register as skill plugins
scan design-systems/*/DESIGN.md → register as design-system plugins
scan plugins/_official/*/       → register official plugins (auto)
// community plugins installed separately via plugin install command
```

**Skill resolver:**
```typescript
resolveSkill(skillId: string, ctx: Context): ContextItem {
  for (skill of ctx.skills) {
    id = skill.ref ?? skill.path
    if (id === skillId || id === "./" + skillId):
      return {
        kind: 'skill',
        id: skillId,
        label: skill.title ?? skillId
      }
  }
  // Records digest ref: { kind: 'skill', ref: skillId }
}
```

**Agent adapter contract (one object per supported CLI):**
```typescript
AgentAdapter = {
  id: string,                          // e.g. 'claude-code'
  name: string,                        // display name
  bin: string,                         // binary to invoke
  versionArgs: string[],               // e.g. ['--version']
  buildArgs: (prompt: string) => string[],  // invocation args
  streamFormat: 'plain' | 'acp-json' | 'json'  // output parsing
}
```

**Confirmed adapters (22+ total):**
Claude Code, Cursor, GitHub Copilot, Hermes, Codex, Qwen, Devin, Trae CLI, Kiro, Kilo, Vibe, Pi, and others.

**Agent invocation flow:**
```
1. Build system prompt: skill instructions + design system + official-system.ts rules
2. Combine with user brief into full prompt
3. Invoke agent CLI as child process via buildArgs(prompt)
4. Stream stdout/stderr via SSE to web UI
5. Parse tool calls from output (file-write, live-artifact-create, etc.)
6. Write artifacts to project storage
```

**Communication protocol:**
```
Primary: stdio (child_process.spawn)
Tool access: MCP server (if agent supports MCP)
Protocol: Agent Client Protocol (ACP) JSON-RPC over stdio for ACP-capable agents
Fallback: plain text streaming for non-ACP agents

Typed events from agent stream:
  thinking    → planning/reasoning text
  tool_call   → file-write, live-artifact, search, etc.
  file_write  → content written to project dir
  text_delta  → response text chunks
  completion  → done signal
```

**Fallback for non-PATH agents:**
```
env var: HERMES_CLI_PATH (overrides auto-detection)
detection command: open-design detect (re-runs PATH scan)
```

**Sidecar override pattern:**
```
skills/<skill-name>/open-design.json   → highest priority in 3-layer merge
skills/<skill-name>/SKILL.md           → adapter-normalized (medium priority)
built-in defaults                      → lowest priority

Merge: sidecar keys overwrite adapter keys; compat arrays are UNIONED
```

## Data contracts

**Agent adapter registration (in agents.ts):**
```typescript
{
  id: 'claude-code',
  name: 'Claude Code',
  bin: 'claude',
  versionArgs: ['--version'],
  buildArgs: (prompt: string) => ['--print', prompt],
  streamFormat: 'plain'
}
```

**MCP server config (for tool-capable agents):**
```typescript
{
  transport: 'stdio' | 'sse' | 'http',
  command?: string,
  args?: string[],
  env?: Record<string, string>,
  oauthConnectorId?: string  // for OAuth-protected MCP servers
}
```

**Plugin manifest fields relevant to runtime routing:**
```typescript
{
  capabilities_required: string[],  // e.g. ['surgical_edit', 'fs:read']
  od: {
    mode: string,          // determines which generation pathway
    pipeline: { stages: [...] },  // overrides default 3-stage loop
    design_system: { requires: boolean, sections?: string[] }
  }
}
```

## Dependencies & assumptions

- `plugin-runtime` package: pure ESM TS, no Node imports, injectable loader pattern
- `better-sqlite3` for persisting plugin registry state
- Agent CLIs must be in PATH (or env var fallback)
- MCP: requires daemon to serve MCP endpoints; agents connect via stdio or HTTP
- Community plugin registry: URL/format not publicly confirmed in source

## To port this, you need:

- [ ] Directory scanner for skills/ and design-systems/ with no registration file
- [ ] Agent adapter registry (one object per supported CLI — start with Claude Code + Cursor)
- [ ] Child process spawner with stdio streaming + SSE relay to UI
- [ ] MCP server integration for file access (optional but needed for surgical edits)
- [ ] Sidecar JSON support: `open-design.json` adjacent to `SKILL.md` with highest merge priority
- [ ] Recoverable exit codes (64-75) for agent failures that can be retried
- [ ] `AGENT_CLI_PATH` env var override for non-PATH installations

## Gotchas

- **Exit codes 64-75 are semantic.** These signal specific recoverable errors (`daemon-not-running`, `capabilities-required`, etc.). Agents can inspect and retry. Use them; don't collapse all failures to exit code 1.
- **Streaming format varies by agent.** Plain text, ACP JSON-RPC, and Anthropic-specific formats all exist. Your stream parser must handle all three if you want broad agent support.
- **MCP OAuth is daemon-hosted.** The daemon manages the full OAuth flow for MCP servers — no transient `localhost:<port>` needed. This is significantly cleaner than tools that require the user to manually complete browser flows.
- **Community registry format is not public.** The three-tier structure (_official, community, registry dirs) is referenced in code but the registry API/format was not confirmed. Plan your own registry format.

## Origin (reference only)

Repo: https://github.com/nexu-io/open-design  
Key files: `apps/daemon/src/agents.ts`, `packages/plugin-runtime/src/`, `apps/daemon/src/plugin-routes.ts`, `apps/daemon/src/mcp-routes.ts`
