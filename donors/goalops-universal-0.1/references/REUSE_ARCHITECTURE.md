# Reuse, elegance and portability architecture

The target is not maximum reuse. The target is **maximum justified reuse with minimum coupling**.

## Capability-first rule

Before implementing a feature, search the capability registry by **semantic purpose**, not package name.
Examples: `persistent-memory`, `repo-search`, `browser-research`, `policy-evaluation`, `code-review`, `task-scheduling`, `artifact-store`.

If an equivalent capability exists, extend/reuse it before introducing another implementation unless an ADR documents why not.

## Preferred shape

`portable core -> explicit contract/port -> thin host adapter -> runtime/tool`

The portable core contains domain logic and policies. Adapters contain translation, lifecycle integration and host-specific API calls.

## Reuse extraction test

Extract a reusable component when at least one is true:

- two or more credible current consumers share the same semantic contract;
- it is a platform-wide trust/security/observability primitive where centralization reduces risk;
- independent versioning/testing materially lowers system-wide cost.

Do not extract merely because two functions look syntactically similar.

## Universal Capability Score (UCS)

Score 0–5 for each:

- semantic stability;
- host/runtime independence;
- interface compactness;
- testability;
- observability;
- side-effect isolation;
- migration/exit cost (reverse-scored);
- number/quality of real consumers;
- security boundary clarity.

Low-scoring candidates remain local until evidence improves.

## Adapter budget heuristic

An adapter should translate contracts and lifecycle events; it should not become the location of core decision logic.
If multiple adapters duplicate substantial domain logic, move that logic into the portable core.

## Versioning

- contracts have explicit versions;
- consumers declare compatible contract versions/capabilities;
- adapters run a conformance suite;
- deprecations have a migration window and trigger;
- avoid agent-runtime names in core domain types.

## Architectural elegance tests

Ask:

1. Can a new agent/runtime be added without modifying existing core modules?
2. Can the capability run in a test harness with no real agent vendor present?
3. Can it be replaced without migrating unrelated state?
4. Is state owned by the platform rather than trapped inside the adapter/runtime?
5. Are failure modes observable at the contract boundary?
6. Can the component serve another workflow without copying its implementation?
