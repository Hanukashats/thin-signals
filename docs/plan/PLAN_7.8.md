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

State: **implementation complete, verification pending**. Bounded fan-out,
SHA-256 primary-source preservation, typed `technology-candidate-0.1` grouping,
the default-off GPT Researcher advisory/refetch boundary and versioned OpenAlex
Work enrichment are implemented on the reliability branch; frozen replay and
independent verification remain open.

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

- Typed claim, objection, rebuttal, control finding and arbiter schemas.
- One equal-budget researcher/critic/defender/control-critic round.
- Append-only review events in PostgreSQL with hashes, provenance, duration,
  tokens and cost.
- Public role traces contain safe structured events only; raw prompts, secrets
  and hidden reasoning are excluded.
- Deterministic arbiter and default-off feature flag.

Acceptance: malformed output, invalid citation, timeout or unresolved critical
objection yields `HOLD`; defender changes an outcome only through newly valid
evidence or a narrower re-evaluated claim.

## Wave 4 — quality and target evaluation

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

## Wave 5 — canary, deploy and publish

- Snapshot/backup VM232 and verify exact rollback.
- Deploy with the new review flag off; check DB/API/UI/search/restart/reboot.
- Enable only after Wave 4 acceptance, run a bounded live canary, and roll back
  on any gate failure.
- Publish the same reviewed SHA to SourceCraft and a GitHub feature branch.
  Preserve real Git timestamps and avoid force-push. The historical delivery
  reference is metadata, never a fabricated commit date.
