# GoalOps autonomous workflow

This is the runtime-neutral execution playbook for `goalops-universal`.

## Phase map

| Phase | Primary owner | Mandatory outputs | Exit gate |
|---|---|---|---|
| 0 Capability negotiation | Goal Governor | runtime-capabilities.yaml | execution profile resolved |
| 1 Internal context recovery | Recon Analyst | context/index.md | prior work + repo truth mapped |
| 2 External freshness research | Recon Analyst | donor-matrix.md | only relevant gaps researched |
| 3 Goal normalization | Goal Governor | goal.yaml | observable acceptance criteria |
| 4 Architecture divergence | Lead + conditional architects | candidates.md | >=2 candidates if significant |
| 5 Foresight | Evolution Architect | forecast/register.yaml | triggers + horizons recorded |
| 6 Architecture decision | Lead + Reuse Architect | ADRs + fitness functions | explicit rationale and rollback |
| 7 Task graph | Goal Governor | task-graph.yaml | dependencies/owners/evidence defined |
| 8 Implementation | Implementers | code/config/docs | task-local tests/evidence |
| 9 Verification | Independent Verifier | evidence/* | objective checks pass |
| 10 Challenge | Reviewer/Red Team | reviews/* | spec then quality/security passes |
| 11 Integration | Release/Integrator | merged state + regression evidence | global gates pass |
| 12 Learning | Goal Governor | retrospective.md | candidate improvements captured |
| 13 Stop | Goal Governor + verifier | final evidence manifest | all stop gates pass |

## Task routing heuristic

Use the minimum topology that fits the task:

- **Simple/local:** one primary agent + independent verifier.
- **Complex but decomposable:** supervisor + 2–5 focused subagents.
- **Large migration/refactor:** independent worktrees/VMs + integration owner.
- **Research uncertainty:** parallel researchers with non-overlapping hypotheses, then synthesis.
- **Hard debugging:** competing-hypothesis agents; after 3 failed fixes revisit architecture.
- **High risk/security:** deterministic orchestration + mandatory hooks/policy gates; minimize free-form routing.
- **Long-lived external dependency:** durable scheduler/workflow engine rather than keeping chat context alive.

## Required sequence for a new GOAL

1. `CAPABILITY_PROBE`
2. `RECOVER_INTERNAL_CONTEXT`
3. `MAP_EXISTING_CAPABILITIES`
4. `RESEARCH_EXTERNAL_GAPS`
5. `WRITE_GOAL_CONTRACT`
6. `CLASSIFY_RISK_COMPLEXITY`
7. `SELECT_DYNAMIC_ROSTER`
8. `GENERATE_CANDIDATES`
9. `RUN_REUSE_LENS`
10. `RUN_FORESIGHT_LENS`
11. `WRITE_ADR_AND_FITNESS_FUNCTIONS`
12. `BUILD_TASK_DAG`
13. `EXECUTE_READY_TASKS`
14. `VERIFY_EACH_TASK`
15. `SPEC_REVIEW`
16. `QUALITY_SECURITY_REVIEW`
17. `INTEGRATE`
18. `GLOBAL_REGRESSION`
19. `STOP_GATE`
20. if fail -> `NEXT_HIGHEST_RISK_GAP` or `REPLAN`
21. if pass -> `RETROSPECTIVE_AND_SKILL_EVAL_CANDIDATES`

## Autonomy classes

- **A0 advisory:** analysis only, no writes.
- **A1 bounded edits:** write code/docs within explicit paths; no external side effects.
- **A2 repository autonomy:** branches/worktrees/tests/PRs allowed; no production writes.
- **A3 controlled operations:** staging/deployment/migrations through policy gates with rollback.
- **A4 privileged production:** require explicit organization-defined human/dual-control gate unless policy explicitly pre-authorizes the exact operation.

Autonomy class is part of `goal.yaml`; subagents may never elevate it themselves.
