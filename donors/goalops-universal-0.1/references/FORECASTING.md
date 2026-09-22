# Forecasting and evolutionary architecture

GoalOps uses forecasting to improve architectural choices, not to generate impressive future narratives.

## Forecast object

Each forecast should contain:

- `question`: falsifiable future proposition relevant to a current decision;
- `horizon`: date/window;
- `base_rate`: closest observed baseline or `unknown`;
- `current_probability`: range plus midpoint when useful;
- `evidence_for` / `evidence_against`;
- `assumptions`;
- `leading_indicators`;
- `decision_trigger`;
- `reversible_action_now`;
- `expiry/review_date`;
- later: `outcome` and probability score/calibration note.

## Three-horizon pass

- **Near:** compatibility, pricing, API/SDK deprecations, operational failure modes, immediate delivery risk.
- **Medium:** ecosystem consolidation, protocol adoption, staffing/maintenance burden, scaling bottlenecks, vendor direction.
- **Long:** architecture lock-in, data portability, replacement of agent runtimes/models, security/regulatory shifts, strategic optionality.

## Scenario set

Always prefer compact scenarios:

1. **Base:** most likely continuation.
2. **Upside:** key capability improves/adoption accelerates.
3. **Downside:** vendor/API disappears, costs rise, security constraint tightens, or runtime is replaced.

Avoid pretending the three scenarios exhaust reality.

## Decision policy

Forecasts affect architecture through **option value**:

- stable interface + thin adapter is favored when runtime churn probability is meaningful;
- irreversible migration is delayed when evidence is weak and waiting has low cost;
- cheap compatibility hooks may be added when they preserve a high-value future option;
- speculative subsystems are rejected when the future use case has no concrete consumer or trigger.

## Calibration

Track forecasts that resolve. Prefer Brier-style scoring for binary outcomes and calibration buckets across repeated forecasts.
A model that sounds confident but is poorly calibrated must lose decision weight.

## Research discipline

Current external evidence is required for time-sensitive forecasts. Retrieval reduces staleness but does not eliminate it. Separate:

- verified current facts;
- causal assumptions;
- probability judgments;
- strategic recommendation.

## Architecture fitness functions

Convert future-sensitive invariants into machine-checkable tests where feasible, e.g.:

- core package imports no host-agent SDK;
- all model/provider access goes through a versioned gateway contract;
- data export round-trip succeeds;
- no secret appears in trace payloads;
- adapter conformance suite passes for every supported runtime;
- deprecated API usage count is zero;
- migration rollback drill passes in staging.

Use LLM/agentic review for semantic architecture drift that deterministic tests cannot reliably express, but do not replace deterministic invariants with model judgment unnecessarily.
