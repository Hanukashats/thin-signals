# EVOLUTION.md — Co-evolution of LivingSet and product

Revision: **7.2** · Date: **2026-09-22**

**Для агента-преемника:** план и концепт не статичны. В ходе реализации их обязательно обновлять. Нельзя «разработать по старому CONCEPT» и оставить документы 7.1 как музей.

## Problem this solves

Development adapts and moves forward while CONCEPT, plan, and old datasets freeze. v7 treats LivingSet as the **same revision contract** as code (when code exists). Drift is a defect, not a note.

## LivingSet members

`CONCEPT.md`, `ARCHITECTURE.md`, `requirements.yaml`, `plan.yaml`, `forks.yaml`, `STATUS.md`, `docs/adr/*`, `docs/plan/PLAN_7.2.md`, `docs/METHODOLOGY.md` (+ `ts/scoring/rules-*.yaml`), `docs/PROCESSING_CONTRACT.md`, `data/pattern_registry.json` (+ related registries), this file.

## Change classes

| Class | Examples | Required updates |
|---|---|---|
| `patch` | Typos, clarifications | Touched file only; STATUS optional |
| `minor` | New task inside a wave; status transition | `plan.yaml` / `requirements.yaml` + `STATUS.md` |
| `major` | Fork decision, schema, pattern rule, acceptance, stack | DecisionRecord + ADR if architectural + all affected LivingSet files + (later) code/tests in **one** change-set |
| `revision` | Scope/criteria of active goal or plan | New `plan_revision` or `goal_revision` with `parent`, `reason`, `impact`; old verifier snapshots immutable |

## Work states

`proposed → implemented → tested → accepted`

- Chat discussion ≠ implemented
- Script exists ≠ accepted
- Donor Auto-Goal tests PASS ≠ Thin Signals product accepted

## One change-set rule

For a method change, the same PR/session must update:

1. Code (when present)
2. Schema/contract if behavior changes
3. Affected patterns / requirements IDs
4. ADR when major
5. Wave row / STATUS INTEGRATE note

Missing LivingSet update on major change → reject in review (and later CI).

## Wave cycle and INTEGRATE

Every GoAll wave ends with **INTEGRATE**:

1. Update `STATUS.md` (phase, wave, blockers, next trigger)
2. Flip requirement `state` when evidence exists (or leave planned + UNRESOLVED)
3. Append fork `decisions_log` when Architect chose
4. Pin hashes of changed registries in `data/PROVENANCE.md` if data evolved
5. LEARN: optional Agentmemory fact for cross-session handoff (no secrets)

Empty waves (no typed knowledge/capability change) count toward `empty_waves_before_hold` in `plan.yaml`.

## Forbidden evolution paths

- Agent silently edits production skill / pinned prompt after one success
- Rewrite historical reports under new methodology without new snapshot id
- Reopen LOCKED fork without ADR
- Auto-elevate autonomy A2 → A3/A4
- Install second goal controller to «speed up» evolution

## Allowed evolution paths

- New idea → issue/ADR → experiment → eval → pin → LivingSet revision
- POL routing CONTINUE/SKIP/JUMP/EXIT with typed finding
- Forecasts change optionality; they never override failed tests (GoalOps)

## Future CI (after code exists)

Check: every `requirements.yaml` id referenced from a wave; every OPEN/DECIDED fork id valid; major ADR linked; release manifest binds commit + skill/model/schema hashes. Until CI exists, Architect/Verifier perform the check manually at INTEGRATE.
