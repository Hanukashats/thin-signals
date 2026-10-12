# ADR-011 — Evidence-gated researcher/critic/defender review

Status: **proposed; operator activation required**  
Date: 2026-10-12  
Decision class: major methodology and persistence change

## Problem

A researcher can overvalue an attractive candidate, while a critic can reject
one merely by sounding confident. Adding a “defender” helps only if promotion
depends on stronger evidence rather than rhetoric. The current deterministic
checklist and scoring must remain the authority.

## Proposed roles

1. **Researcher** produces typed claims, evidence references, uncertainty and a
   promotion hypothesis.
2. **Critic** attacks each critical claim using named failure modes: false
   novelty, mass adoption, dependence on one origin, weak provenance,
   chronology conflict, and unsupported market/technical transition.
3. **Defender** may answer only by adding an independent source, strengthening
   a source chain, correcting a factual error, or narrowing/reframing the
   claim. Unsupported confidence is ignored.
4. **Control critic** checks the rebuttal once. There is no unlimited debate.
5. **Deterministic arbiter** maps the typed ledger to `PROMOTE`, `REFRAME`,
   `HOLD` or `REJECT`. No model directly writes a target finding.

The defender can therefore cause promotion, but only indirectly: its new
evidence must satisfy the same machine-checkable gates as any other evidence.

## Proposed decision rules

- `REJECT`: verified fatal counterevidence, confirmed mass adoption, fabricated
  citation, or contradicted critical claim.
- `HOLD`: a critical objection remains unknown/disputed or lacks independent
  evidence after the bounded round.
- `REFRAME`: a narrower claim removes the contradiction and preserves cited
  novelty.
- `PROMOTE`: every critical objection is resolved by valid evidence, required
  origin diversity is met, existing exclusion gates pass, and the candidate
  meets the current versioned score threshold.

Deadline pressure never converts `UNKNOWN` into `PROMOTE`.

## Ledger and metrics

PostgreSQL remains the only writable source of truth. A proposed append-only
review event records:

- run/candidate/round/role and immutable input/output hashes;
- claim and evidence IDs, objection/rebuttal reason codes and arbiter verdict;
- model, returned provider, ZDR policy, prompt/template version;
- `started_at`, `finished_at`, `duration_ms`, token counts and cost;
- connector/scrape latency, source count, independent-origin count and errors.

The target-finding transition stores the arbiter event ID. GPT Researcher
Markdown is retained as an artifact, not substituted for this ledger.

## Bounded execution

- One researcher pass, one critic pass, one defender pass, one control-critic
  pass and one deterministic arbitration.
- Per-role token/time/cost caps; failure or budget exhaustion produces `HOLD`.
- Suggested role split for evaluation: primary Qwen for researcher/defender;
  allowlisted judge model for critic. The arbiter itself is code, not an LLM.
- Feature flag `TS_ADVERSARIAL_REVIEW_ENABLED=false` by default.

## Evaluation before activation

Compare baseline and proposed paths on a frozen replay plus a genuinely
separate labeled holdout. At minimum measure precision, recall, false-promotion
rate, evidence coverage, unresolved-critical-claim rate, latency and cost.
Activation requires:

- zero evidence-less promotions;
- zero promotions with unresolved critical objections;
- false-promotion rate no worse than baseline;
- reproducible verdicts from the same frozen ledger;
- documented latency/cost accepted by the operator;
- independent review of migrations, prompts and eval evidence.

## Operator gate

This ADR does not authorize schema changes, role prompts, production code or
activation. A separate authenticated operator command is required before the
implementation phase starts.

