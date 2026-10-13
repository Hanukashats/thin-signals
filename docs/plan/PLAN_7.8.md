# Thin Signals — plan 7.8: trustworthy retrieval and bounded review

Date: **2026-10-12**. Parent: **7.7**. Class: major reliability and methodology
revision. Organizer delivery reference remains **2026-09-29 22:45 MSK**;
implementation, test and Git timestamps remain real.

## Outcome

Thin Signals must discover and aggregate evidence broadly, challenge each
candidate once, and promote only evidence-qualified weak signals. The search
aims for ten qualified signals on the named wide-query benchmark, but never
fills a shortfall with watchlist/potential items or by weakening gates.

## GOAL queue

The existing goal-kernel remains the only controller. Ordered cards for
`project=thin-signals`, `agent=codex-backend`:

1. `g-2629cc78010b` — trustworthy baseline and run contracts (A2).
2. `g-62fcfd60cd61` — bounded retrieval, provenance and candidate aggregation (A2).
3. `g-c6ef2e986d34` — evidence-gated roles behind a disabled flag (A2).
4. `g-df30f33833c7` — frozen replay, holdout, ablations and target measurement (A2).
5. `g-277a6c4d68e2` — snapshot, canary, deployment and mirrored publication (A3).

`COMPLETED != VERIFIED`; a distinct verifier evaluates each frozen release
candidate. No second scheduler or product ledger is added.

## Wave 0 — baseline audit

State: **completed read-only**.

- Confirm SearXNG ↔ GPT Researcher wiring and absence of a GPT Researcher call
  from `run_query`.
- Record source coverage, search-engine degradation, resource use and current
  tests.
- Reproduce trust, run-status, countersearch and scoring defects.

Evidence: `reports/ASTRA_AUDIT_2026-10-12.md`.

## Wave 1 — reliability invariants

State: **in progress**.

- Host/type source trust (`source-trust-0.2`).
- Versioned `succeeded | degraded | failed` run contract.
- Countersearch completion and coverage must be truthful.
- Full suite uses a disposable migrated PostgreSQL database.

Acceptance: total connector failure is `failed`; partial failure is
`degraded`; failed countersearch cannot yield admission; unknown DOI-like URL
paths remain indicator; old runs remain immutable.

## Wave 2 — evidence retrieval

State: **remediation complete, independent re-verification pending**. Bounded fan-out,
SHA-256 primary-source preservation, typed `technology-candidate-0.1` grouping,
the default-off GPT Researcher advisory/refetch boundary and versioned OpenAlex
Work enrichment are implemented on the reliability branch. Astra rejected the
first frozen candidate on DNS-rebinding, slow-stream, unattested-snapshot and
short-title Work-mirror gaps; `retrieval-0.4`/`checklist-v19` close those exact
findings with regressions. Frozen replay and a fresh independent verdict remain
open.

- Bounded connector concurrency, per-call timing and one global deadline.
- Persist a retrieval fingerprint and a safe source funnel; show structured
  activity without raw prompts or hidden model reasoning.
- Fetch and preserve primary text with hashes and provenance.
- Group publications into typed technology hypotheses without false merges.
- Add the pinned GPT Researcher native adapter behind a default-off flag: one
  synchronous call per top-level run, one inherited deadline, generated prose
  discarded, and only re-fetched preserved sources admitted to evidence.
- Enrich OpenAlex identities, chronology, affiliations, OA locations and
  correction/retraction metadata.

Acceptance: deterministic ordering under concurrency; timeout/cancel tests;
snippet-only claims cannot be verified; joint DOI/Work/URL aliases make duplicate
views count once despite missing DOI metadata or repeated URLs, while conflicting
explicit DOIs stay separate; GPT-R failure is explicit degradation and never
direct evidence; OpenAlex Work/DOI mirrors count once, only explicit ROR values
contribute origin identity, and a negative Retraction Watch flag is not treated
as a completed integrity screen.

Reference benchmark and donor decision:
`reports/REFERENCE_WSIGNAL_REVIEW_2026-10-12.md`.

## Wave 3 — bounded adversarial review

Status 2026-10-13: implemented and tested on the reliability branch; the
production flag remains off until Wave 4 acceptance.

- Typed claim, objection, rebuttal, control finding and arbiter schemas.
- One equal-budget researcher/critic/defender/control-critic round.
- Append-only review events in PostgreSQL with hashes, provenance, duration,
  tokens and cost.
- Durable pre-spend reservation under a PostgreSQL session lock, including
  one pinned connection, process-death recovery to stable `HOLD`, pool-saturation
  safety and cross-process canonical replay.
- Public role traces contain safe structured events only; raw prompts, secrets
  and hidden reasoning are excluded; rejected or mismatched route identifiers
  are erased. Async cancellation covers DNS through response parsing and forbids
  late dispatch after timeout.
- Deterministic arbiter and default-off feature flag.

Acceptance: malformed output, invalid citation, timeout or unresolved critical
objection yields `HOLD`; defender changes an outcome only through newly valid
evidence or a narrower re-evaluated claim.

## Wave 4 — quality and target evaluation

Status 2026-10-13: the first independent verifier rejected commit `74445de`
because supported non-primary evidence could promote, ablations bypassed the
runner and invalid baseline replay still exited successfully. The remediation
versions the arbiter to 0.2, derives safety/exact-verdict metrics, executes each
role-unavailability ablation twice and fails invalid replay closed. Fresh
independent re-verification and the optional live-yield target remain open.

The second verifier rejected `26b4e8d`: a resolved control finding was not bound
to the defender evidence, a critical replacement could remain unknown, and the
provider-failure ablations erased the original critic failure. The next frozen
candidate added those three fail-closed checks. A third verifier rejected
`9e5cc76` because corrected/narrowed claims retained superseded citations and
could satisfy the origin gate with only one replacement origin. The current
candidate replaces the effective evidence set, mirrors that rule in evaluation
coverage and rejects ambiguous multiple rewrites; it requires a fresh independent
verdict before Wave 5. The fourth verifier then found one replacement mixed with
one additive defense for the same claim remained order-dependent. The next
candidate rejects that unordered mix and tests every critic/defender permutation
for both `CORRECT` and `NARROW` before another independent verdict.

- Correct primary-pattern non-monotonicity in a new rules version.
- Run baseline, proposed, without-defender and without-control-critic paths on
  frozen replay plus a separate adjudicated holdout.
- Measure precision, recall, false promotion, evidence coverage, unresolved
  claims, stability, latency, tokens and cost.
- Report `qualified_weak_signals`, `watchlist`, `potential` and `shortfall`
  separately.

The ten-signal target is optional evidence of improved recall, not a release
gate. Required release gates are zero evidence-less promotions, zero unresolved
critical promotions and no worse false-promotion rate than baseline.

Evidence: `reports/eval/review-2026-10-13/` and
`reports/eval/rules-0.2-2026-10-13/`. The 170-row rules replay reproduces v0.1
exactly and changes no historical labels. The 16-case review evaluation records
all required quality/resource metrics and passes both safety gates. These are
fixture and stored-extraction evaluations; live search quality is not inferred.
The rejection receipt is `reports/ASTRA_WAVE4_AUDIT_74445DE_2026-10-13.md`;
the second receipt is `reports/ASTRA_WAVE4_REAUDIT_26B4E8D_2026-10-13.md`;
the third receipt is `reports/ASTRA_WAVE4_FINAL_9E5CC76_2026-10-13.md`;
the fourth receipt is `reports/ASTRA_WAVE4_FAIL_3AE2BDC_2026-10-13.md`;
ADR-014 records the evolving remediation contract.

## Wave 5 — canary, deploy and publish

- Snapshot/backup VM232 and verify exact rollback.
- Deploy with the new review flag off; check DB/API/UI/search/restart/reboot.
- Enable only after Wave 4 acceptance, run a bounded live canary, and roll back
  on any gate failure.
- Publish the same reviewed SHA to SourceCraft and a GitHub feature branch.
  Preserve real Git timestamps and avoid force-push. The historical delivery
  reference is metadata, never a fabricated commit date.
