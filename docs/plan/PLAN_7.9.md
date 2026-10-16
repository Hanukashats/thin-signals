# Thin Signals — plan 7.9: shared workspace on the reliability line

Date: **2026-10-16**. Parent: **7.8**. ADR: **ADR-015**. Class: additive
persistence and browser presentation. The verified retrieval, attestation,
review, scoring and provider boundaries remain unchanged.

## Outcome

Restore one shared, durable three-module result after login, refresh and service
restart, while preserving immutable scientific history and the verified VM232
reliability line. Provide an honest browser-local demonstration mode without a
reset endpoint or a second ledger.

## Wave A — reconcile and verify

1. Add the singleton PostgreSQL workspace after the review-events migration.
2. Publish only completed compatible top-level runs, atomically with Run,
   Decision and review events; never publish fanout children or failed work.
3. Persist explicit archive query/families with archive digest and ordered IDs;
   reject stale writers with the workspace revision.
4. Preserve `/v1/runs/latest` as the newest-finished operational endpoint and
   add `/v1/workspace/latest` as the explicitly published operator view.
5. Re-run the complete disposable-database reliability suite, scoped Ruff,
   LivingSet links and migration-head checks. Independent verification remains
   required because the implementing role cannot accept its own candidate.

## Wave B — honest demonstration

1. Offer a browser-local new show with zero counters and no selected result.
2. Retain a deep-copied compatible saved example; reset/open make no HTTP calls.
3. Count distinct viewed Run IDs and confirmed archive submissions separately.
4. Preserve the POST replay flag before loading the workspace projection and
   disclose possible lower-level cache reuse.
5. Before an archive submission, show the total sealed corpus without presenting
   old matches as findings from the current show.

## Release gate

Take a private database backup and prove restore in a disposable database.
Validate the additive migration, fresh-session hydration, desktop/mobile layout,
API/UI restart and exact rollback on VM232. Run one explicitly authorized narrow
canary only after independent review. Production activation, GOAL changes and
scientific relabeling are outside this implementation checkpoint.
