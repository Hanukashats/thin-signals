# Runtime portability strategy

GoalOps defines behavior in the portable layer and compiles/maps it into each host's native mechanism.

## Canonical portable layer

- `SKILL.md` + references/scripts/assets following the Agent Skills shape where supported;
- neutral role contracts;
- neutral goal/task/handoff/forecast schemas;
- MCP/A2A/API contracts for external tools/services;
- platform-owned memory/state rather than runtime-owned chat state.

## Capability probe

Resolve these booleans/capabilities before execution:

- skill discovery;
- nested/subagents;
- parallel subagents;
- peer/team messaging;
- persistent GOAL/objective;
- hooks/lifecycle gates;
- isolated worktree/VM/sandbox;
- MCP;
- A2A;
- model routing;
- structured output;
- scheduler/durable events;
- granular tool permissions.

Then choose the best available implementation without changing GoalOps semantics.

## Host mappings (snapshot: 2026-09-02)

### Cursor

Use native Agent Skills/custom modes, `/goal` for long-lived objective, custom subagents, `/loop`/automations when appropriate, and isolated worktree/VM subagents when available. Keep project instructions concise and use nested `AGENTS.md`/project rules only for local invariants.

### Claude Code

Use Agent Skills, subagents, hooks and—when justified—experimental Agent Teams for peer collaboration. `/batch` is suitable for large independent codebase changes. Enforce completion gates with lifecycle hooks where practical.

### OpenCode

Use portable skills (`.agents/skills` or supported compatibility paths), primary/subagent definitions and explicit tool permission rules. Keep roles in generated host manifests, not inside the portable core.

### Codex

Use skills, parallel/worktree agents and automations where available. Keep `AGENTS.md` short and navigational; store detailed operating knowledge in structured repository docs.

### Hermes

Use Agent Skills-compatible skills, isolated/parallel subagents, Bot Mode/team specialists and MCP. Treat Hermes memory/runtime state as replaceable unless deliberately mapped into platform-owned memory.

### Ruflo

Use as an optional orchestration/intelligence substrate for swarms, hooks, routing, memory/cache helpers and autonomous loops. Do not make Ruflo-specific state or commands canonical GoalOps semantics if portability is required.

### Future/unknown agent

Fallback order:

1. Agent Skills + native subagents/hooks;
2. portable `SKILL.md` + AGENTS/project instructions + MCP tools;
3. single-agent execution that simulates role phases sequentially with independent contexts/checkpoints where possible.

## Adapter compiler concept

Maintain canonical files under `goalops/` and generate/sync host-specific manifests into:

- Cursor agent/skill locations;
- Claude agent/skill locations;
- OpenCode agent/skill locations;
- Codex skill/instruction locations;
- other host-defined directories.

Never fork the methodology per runtime. Fork only the adapter/manifest layer.
