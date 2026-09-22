---
name: goalops-universal
description: Portable autonomous multi-agent GOAL workflow for software, infrastructure, research, and architecture tasks. Use when a long-running objective requires decomposition, specialized roles, parallel work, evidence-based verification, architectural foresight, reusable solution design, and controlled iteration until explicit success criteria are met.
license: MIT
compatibility: Agent Skills compatible harness preferred; graceful-degradation adapters for Cursor, Claude Code, OpenCode, Codex, Hermes, Ruflo and future agents.
metadata:
  version: "0.1.0"
  status: research-prototype
  architecture: runtime-neutral
---

# GoalOps Universal

GoalOps is a methodology skill, not a single giant prompt and not a replacement for the host agent/runtime.
It coordinates an objective through portable artifacts, explicit role contracts, deterministic gates, and runtime adapters.

## Core invariants

1. **Goal over activity.** Do not equate tool calls, commits, or agent output with progress. Progress means measurable closure of acceptance criteria.
2. **Evidence over claims.** No task is `done` until its verification evidence exists and is independently checked where required.
3. **Artifacts over chat state.** Persist goal, task graph, decisions, forecasts, evidence, review state, and handoffs in files/state stores.
4. **Contract-first reuse.** Before creating a new capability, search the capability registry and existing code. Prefer one stable core plus thin adapters.
5. **No premature abstraction.** Generalize only when there are at least two credible consumers, or when the capability is security/platform-critical and centralization is justified.
6. **Role separation.** An implementer must not be the sole final approver of its own high-impact work.
7. **Reversible by default.** Prefer choices with low migration cost until evidence justifies an irreversible commitment.
8. **Forecasts are probabilistic advice, not facts.** Track assumptions, probabilities, horizons, indicators, calibration, and decision triggers.
9. **Least privilege.** Agents receive only tools, credentials, paths and network access needed for their current task.
10. **Bounded autonomy.** Respect iteration, cost, tool-call, parallelism and risk budgets. Escalate instead of looping indefinitely.
11. **Stable run semantics.** Do not silently mutate role definitions, success criteria, or evaluation rules mid-run. Version changes explicitly.
12. **Graceful degradation.** Use advanced runtime features when available; preserve the same logical workflow when they are not.

## Required portable state

At GOAL start, create or resolve these artifacts:

- `goal.yaml` — objective, constraints, acceptance criteria, risk class, budgets.
- `context/index.md` — relevant repository/history/memory sources and freshness.
- `research/donor-matrix.md` — existing internal/external frameworks and reusable patterns.
- `tasks/task-graph.yaml` — dependency DAG, owner role, state, evidence requirements.
- `architecture/candidates.md` — alternatives and trade-offs for significant decisions.
- `decisions/ADR-*.md` — accepted architecture decisions.
- `forecast/register.yaml` — scenarios, probabilities, indicators, triggers, expiry dates.
- `reuse/capability-map.yaml` — existing and proposed reusable capabilities/contracts/adapters.
- `reviews/` — spec, quality, security and adversarial reviews.
- `evidence/` — test, benchmark, lint, build, policy and runtime evidence.
- `metrics/run.json` — progress, cost, retries, failures, review findings, forecast outcomes.
- `retrospective.md` — lessons and candidate workflow/skill improvements.

## Default dynamic roster

Do **not** instantiate every role for every task. Start with the smallest useful roster and expand from risk/complexity.

### Mandatory core

- **Goal Governor / Lead Architect** — owns objective normalization, decomposition, topology, decision synthesis, stopping condition. Avoids being the main bulk implementer.
- **Recon & Evidence Analyst** — mines prior project history/repository first, then current external sources when freshness matters; maintains provenance.
- **Implementer** — executes bounded tasks against explicit contracts; may have multiple isolated instances.
- **Independent Verifier** — checks acceptance criteria and evidence independently of the implementer.

### Conditional lenses

- **Evolution & Foresight Architect** — activates for architecture, platform, dependency, product-strategy, long-lived or expensive-to-reverse decisions.
- **Reuse & Simplicity Architect** — activates when new modules/services/skills/frameworks are proposed or duplication is likely.
- **Adversarial Reviewer / Red Team** — activates for important releases, uncertain designs, security-sensitive work, or high model-correlated error risk.
- **Security / Trust Reviewer** — activates when credentials, auth, network, sandbox, supply chain, PII, policy or privileged actions are involved.
- **Release / Integration Engineer** — activates for multi-branch/multi-worktree, migrations or deployment changes.
- **Domain Specialist** — activates only when domain knowledge materially changes correctness.

See `references/ROLE_CONTRACTS.md`.

## GOAL state machine

Run the following loop until the stopping gate passes or bounded-autonomy policy requires escalation:

`OBSERVE -> ORIENT -> SPECIFY -> DIVERGE -> FORECAST -> DECIDE -> EXECUTE -> VERIFY -> CHALLENGE -> INTEGRATE -> LEARN -> STOP/CONTINUE`

### 0. BOOTSTRAP / capability negotiation

Detect host capabilities: skills, persistent goal mode, subagents, parallel execution, isolated worktrees/VMs, hooks, team mailbox, MCP, A2A, durable scheduler, permission model, model routing, structured output.
Write the resolved execution profile to `context/runtime-capabilities.yaml`.
Do not let missing premium/runtime-specific features change the logical contracts.

### 1. OBSERVE — internal-first context recovery

Before global research or new implementation:

1. Search prior project history, memory, ADRs, plans, issues, docs, existing code, capability registry and previous failed attempts.
2. Identify what already exists, what is only planned, and what is actually verified.
3. Mark source freshness and confidence.
4. Build `context/index.md`.

Rule: **existing verified project truth outranks generic external patterns unless explicitly superseded.**

### 2. ORIENT — normalize the objective

Create `goal.yaml` with:

- desired outcome;
- non-goals;
- acceptance criteria expressed as observable checks;
- constraints and invariants;
- risk class (`low|medium|high|critical`);
- reversibility requirement;
- cost/time/token/tool budgets;
- allowed autonomy level;
- explicit human-approval gates if required.

Reject vague completion language such as “looks good”, “should work”, or “mostly done”.

### 3. SPECIFY — research and donor scan

For each capability needed:

1. Search internal code/skills/frameworks first.
2. Search current external frameworks/docs/repositories when needed.
3. Record license/provenance, activity, portability, maintenance, security posture, integration cost, runtime coupling, and extraction value.
4. Prefer **pattern adoption** over source copying unless the license/provenance is explicitly acceptable.
5. Update `research/donor-matrix.md` and `reuse/capability-map.yaml`.

### 4. DIVERGE — generate competing solution candidates

For architecturally significant work, generate at least two credible candidates; use three when uncertainty or lock-in is high.
Candidates must state:

- architecture and contracts;
- what is reused vs newly built;
- adapter boundaries;
- operational complexity;
- security/trust boundaries;
- test/observability plan;
- migration and rollback path;
- irreversible decisions;
- expected maintenance burden.

Do not converge merely because the first candidate is plausible.

### 5. FORECAST — strategic foresight pass

The Evolution & Foresight Architect must produce a forecast only when it can affect the decision.
Use `references/FORECASTING.md` and write `forecast/register.yaml`.

Minimum forecast dimensions:

- 3 horizons: near / medium / long;
- base rate or closest historical analogue where available;
- 3 scenarios: base / upside / downside;
- probability ranges, not false precision;
- leading indicators that would change the decision;
- dependency/vendor/protocol obsolescence risk;
- migration/optionality implications;
- explicit trigger: “If X becomes true, reconsider ADR Y.”

Forecasting cannot override failed tests, security policy, or current hard evidence.

### 6. DECIDE — architecture/reuse gate

The Lead Architect and Reuse Architect evaluate candidates against:

- goal fit;
- simplicity / minimal moving parts;
- reuse potential without speculative generalization;
- coupling and blast radius;
- observability/testability;
- security;
- portability and exit cost;
- forecast-adjusted risk;
- implementation and operating cost.

Record important decisions as ADRs. Encode measurable architecture invariants as fitness functions where practical.

### 7. EXECUTE — bounded parallel implementation

Build `tasks/task-graph.yaml` and schedule only ready nodes.

Rules:

- parallelize independent tasks, not tightly coupled edits;
- use isolated worktrees/branches/VMs when supported;
- assign explicit file/module ownership for concurrent work;
- give each subagent only the context its task requires plus relevant invariants;
- require structured handoffs (`schemas/handoff.schema.yaml`);
- write tests/contracts before or alongside implementation for behavior that can regress;
- do not bypass architecture/security fitness functions to “make tests green”.

### 8. VERIFY — evidence gate

Each task must satisfy its evidence contract. Typical evidence:

- unit/integration/e2e/contract tests;
- build/type/lint/static analysis;
- architecture fitness checks;
- security/policy scans;
- benchmark/performance evidence;
- migration/rollback rehearsal;
- documentation consistency checks.

A task moves to `verified` only when evidence exists, not when the agent asserts success.

### 9. CHALLENGE — independent/adversarial review

For medium+ risk, use two stages:

1. **Spec compliance review** — did the implementation meet the stated contract, no more and no less?
2. **Quality/adversarial review** — correctness, maintainability, security, edge cases, architecture drift, hidden coupling, simpler alternative.

When model/provider diversity exists, prefer a different model family for the adversarial review to reduce correlated mistakes.

### 10. INTEGRATE

Integrate only verified nodes.
Run repository-wide/regression gates after merge, not only branch-local tests.
Update docs, ADRs, capability registry, migration notes and operational runbooks.

### 11. LEARN — controlled evolution

Capture:

- repeated failure modes;
- reusable capabilities that emerged;
- adapters that should become standard;
- prompts/roles that were ineffective;
- metric deltas and review escape rate;
- forecast outcomes when observable.

Proposed changes to this skill/workflow are **candidates**, not automatic truth. Promote them only after replay/eval against a representative task set and a `matches-or-improves` gate. Keep rollback to the previous version.

### 12. STOP / CONTINUE

Stop only if all required conditions are true:

- every mandatory acceptance criterion is verified;
- no unresolved P0/P1 issue and no unaccepted security finding;
- architecture fitness functions pass;
- required reviews pass;
- integration/regression tests pass;
- documentation/ADR/capability state is current;
- remaining forecast risks are explicitly accepted/mitigated and have triggers;
- VCS/worktree state is coherent;
- evidence bundle is complete.

Otherwise continue with the smallest next task that reduces the largest unresolved risk or acceptance gap.

## Stagnation and recovery

Trigger `REPLAN` when any occurs:

- the same failure pattern repeats 3 times;
- two consecutive iterations produce no measurable acceptance/metric improvement;
- a blocker invalidates a key architecture assumption;
- review finds systemic rather than local defects;
- predicted cost exceeds remaining budget.

On `REPLAN`:

1. stop patching the current symptom;
2. restate the failing assumption;
3. spawn 2–3 competing hypotheses/solutions if supported;
4. seek new evidence;
5. revisit architecture/ADR if needed;
6. continue only after a changed plan is recorded.

## Completion response contract

The final response must distinguish:

- `VERIFIED` — supported by direct evidence;
- `INFERRED` — reasoned but not directly verified;
- `FORECAST` — probabilistic future claim;
- `UNRESOLVED` — known gap/blocker;
- `NEXT TRIGGER` — event/indicator that should cause reevaluation.

Never collapse these categories into a single confidence statement.
