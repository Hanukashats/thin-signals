# Adapter contract

A host adapter is deliberately thin. It maps GoalOps into native runtime primitives without changing the methodology.

## Adapter responsibilities

- install/discover `goalops-universal` skill;
- generate native subagent/role manifests from neutral role contracts;
- translate task launch/cancel/status operations;
- expose worktree/sandbox/parallelism primitives;
- map lifecycle hooks to GoalOps verification/stop gates;
- map MCP/A2A/tool permissions;
- report capability probe results;
- normalize structured handoffs/events.

## Adapter non-responsibilities

Adapters must not own:

- canonical project memory;
- the acceptance criteria;
- architecture decision logic;
- forecast policy;
- reusable domain capabilities;
- security policy source of truth.

## Conformance tests

Every adapter should pass:

1. skill discovery test;
2. role launch + context isolation test;
3. structured handoff test;
4. cancellation/timeout test;
5. permission-denial test;
6. evidence/stop-hook test where supported;
7. parallel isolation test where supported;
8. state recovery test when the host claims durability.
