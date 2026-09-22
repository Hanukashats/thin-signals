# Research synthesis and two-pass audit

## Initial synthesis

The ecosystem already contains excellent pieces, but no single framework should become the universal truth for a portable GOAL system.
The strongest design is a neutral methodology core using Agent Skills-shaped packaging, neutral schemas/artifacts, dynamic role contracts, and thin adapters to native runtimes.

### What each family is best at

- **Skill/methodology:** Agent Skills, Superpowers, gstack, Spec Kit, BMAD.
- **Native execution:** Cursor `/goal`/subagents, Claude subagents/teams/hooks, OpenCode agents, Hermes subagents/Bot Mode, Codex worktrees/automations.
- **Swarm/runtime substrate:** Ruflo, Microsoft Agent Framework, LangGraph, CrewAI, Google ADK, OpenAI Agents SDK.
- **Controlled evolution:** AFlow/DSPy-style offline workflow/prompt optimization behind replay/evaluation gates.

## Audit #1 — architecture omissions found

The original idea was strong but needed additional invariants:

1. **Persistent artifacts/state** so GOAL progress survives context loss and agent replacement.
2. **Capability negotiation** because runtimes expose different primitives.
3. **Separation of duties** so implementers cannot self-approve risky work.
4. **Evidence-based stop conditions** instead of a subjective “agent thinks it is done”.
5. **Stagnation detection** to stop endless local patching.
6. **Budget governance** for cost/tokens/tool calls/parallelism.
7. **Concurrency isolation** via worktrees/VMs and ownership boundaries.
8. **Security/least privilege** as a role and as deterministic policy.
9. **Provenance/license tracking** for donor instructions/code.
10. **Architecture Decision Records + fitness functions** to prevent gradual drift.
11. **Model diversity for challenge** to reduce correlated multi-agent errors.
12. **Explicit autonomy classes** separating analysis, repository writes and production operations.

These were added to v0.1.

## Audit #2 — portability, reuse, foresight and evolution omissions found

A second pass found further failure modes:

1. **Role explosion:** too many permanent personas increase cost/context noise. Fixed with dynamic roster activation.
2. **Portable core contamination:** host-specific commands in the methodology create lock-in. Fixed with adapter-only host syntax.
3. **Premature universalization:** “make everything reusable” can create mega-abstractions. Fixed with semantic-contract and extraction thresholds.
4. **Forecast theater:** a model can produce confident narratives without calibration. Fixed with base rates, probability ranges, indicators, triggers and outcome scoring.
5. **Prediction overriding current evidence:** prohibited; forecasts modify optionality/decision risk only.
6. **Self-modifying workflow instability:** runtime learning may degrade quality. Fixed by versioned offline evaluation and matches-or-improves promotion.
7. **Runtime-owned memory lock-in:** canonical state must remain external/platform-owned.
8. **No trigger for re-evaluation:** every important forecast/ADR can carry an observable reconsideration trigger.
9. **No explicit exit strategy:** portability includes data export, adapter conformance and rollback drills.
10. **No distinction between facts/inference/forecast:** final reporting contract now separates them.

## Final verdict

Build **GoalOps as a portable control methodology**, not as another orchestration framework.

Use existing runtimes opportunistically:

- native `/goal`, skills, subagents and hooks where the host has them;
- Ruflo for optional swarm/routing/hooks/intelligence features;
- the project's own orchestrator/control plane as canonical authority where one already exists;
- external platform memory/knowledge/security/observability as durable state;
- AFlow/DSPy-style optimization only in an evaluated Evolution Engine, never as unbounded self-modification in production.

The essential architectural pattern is:

`GoalOps methodology + portable artifacts/contracts + dynamic roles + verification/fitness gates + host adapters + platform-owned state`

This preserves the ability to replace Cursor/Hermes/OpenCode/Claude/Codex/Ruflo or future agents without rewriting the actual operating method.
