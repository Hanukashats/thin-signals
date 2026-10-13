# ADR-014: attested promotion gate and executed role ablations

Date: 2026-10-13
Status: accepted as a remediation candidate; production activation remains gated.

## Context

Independent Astra review of commit `74445de` found that a schema-valid
`supported` claim could cite two `preserved_non_primary` records and receive
`PROMOTE`. The runner required primary attestation only for a claim labelled
`verified`, while the arbiter counted every origin at its final diversity gate.
The same audit showed that `REFRAME` returned before checking another unknown
critical claim, and that evaluation ablations removed outputs after validation
instead of executing the reduced paths.

## Decision

- Version the deterministic contract as `review-arbiter-0.2`; historical
  `review-arbiter-0.1` decisions remain immutable.
- Before either `PROMOTE` or `REFRAME`, require primary attestation for every
  critical claim and cited accepted evidence from at least two independent
  `preserved_primary` origins. When critical claims exist, evidence cited only
  by an unrelated non-critical claim cannot satisfy this gate. Role-provided
  `status` cannot weaken it.
- Evaluate every unknown critical claim before returning a reframe.
- A resolved control finding must name the exact defender rebuttal and cite all
  evidence used by that rebuttal or its replacement claim. Objection-only
  findings remain valid for unresolved/fatal outcomes but cannot validate a
  defense. A critical replacement must remain critical and cannot be `unknown`.
- `CORRECT` and `NARROW` replace the effective claim and its evidence set.
  Evidence cited only by the superseded claim is not inherited; the replacement
  must explicitly cite every origin it wants credited. Multiple unordered
  replacements for the same original claim, a replacement mixed with any other
  same-claim defense, or colliding replacement identities are invalid and fail
  closed. `ADD_EVIDENCE` remains the only additive action; it cannot be silently
  applied before or after a replacement because it names the original claim.
- Run `no_defender` and `no_control` ablations twice through the same typed
  runner with the selected role unavailable while preserving every failure in
  the original scenario. Record actual validation errors, resources and replay
  stability; do not call the arbiter on post-hoc-mutated outputs.
- Derive evidence-less and unresolved-critical safety metrics from evaluated
  provenance and typed records, not editable fixture annotations. Report exact
  verdict accuracy so `PROMOTE` cannot silently substitute for `REFRAME`.
- A scoring replay with any `rules-0.1` reconstruction mismatch is invalid and
  its CLI exits non-zero before consumers can accept the comparison.

## Consequences

The stricter gate can only convert an unsafe acceptance to `HOLD`; it cannot
promote a new candidate. Evaluation coverage derives the same effective
replacement evidence rather than unioning old and new citations. The
role-removal ablations intentionally become fully
fail-closed and therefore measure necessity/safety rather than useful recall.
Fixture results still do not establish live-model quality, retrieval yield or
the optional ten-signal target. Those remain bounded canary evidence.
