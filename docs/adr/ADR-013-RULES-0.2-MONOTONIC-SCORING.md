# ADR-013: rules-0.2 monotonic positive-evidence aggregation

Date: 2026-10-13  
Status: accepted as an evaluation candidate; production activation remains gated.

## Problem

`rules-0.1` gives the semantic primary pattern weight 0.35 and each secondary
pattern 0.15. If a newly recognised but weaker pattern becomes the semantic
primary, an already verified primary can move to a secondary slot. The evidence
set has improved, yet confidence can fall. This is a scoring artefact, not
negative evidence.

Threshold values also appeared as executable constants in the potential and
near-miss views. A future version could therefore score with one threshold and
display or filter with another.

## Decision

- Keep `rules-0.1.yaml` and every historical result immutable.
- Add `rules-0.2.yaml`. The semantic primary remains visible for explanation,
  while scoring slots are assigned deterministically by evidence status and
  pattern code. The strongest status receives the lead weight; remaining
  recognised patterns receive the capped support weight.
- Keep all v0.1 weights and thresholds unchanged for the first comparison. This
  isolates the aggregation correction from calibration.
- Load ledger and description thresholds through `thresholds_for()` in the
  scorer, checklist, potential queue, near-miss view and admin explanation.
- A rules version remains part of run identity. Old rows are never silently
  rescored; v0.2 requires a new run.

## Invariants

For a fixed evidence set, choosing a different semantic primary cannot change
confidence. Adding a positive pattern or upgrading a status cannot lower it.
Counters still short-circuit to mature/noise, evidence gates still run before
scoring, and thresholds remain non-scientific versioned heuristics.

Exhaustive regression tests cover every status combination for three patterns,
every primary choice and every non-decreasing status update. Separate tests
prove that potential and near-miss consumers follow an injected rules threshold
rather than module constants.

## Consequences

The candidate may change confidence and ordering for records whose semantic
primary was not their strongest evidenced pattern. It must therefore pass frozen
replay, a separate adjudicated holdout, ablations and independent verification
before the production environment selects `rules-0.2`.
