# Thin Signals — plan 7.7: durable latest workspace

Parent: 7.6. Delivery package date: 2026-09-29. ADR-010.
Reason: operator requests a three-module test and persistent latest results.
Impact: additive PostgreSQL table/API; no scientific rule, prompt or gate changes.

1. Write isolated PostgreSQL regressions before implementation.
2. Publish a completed top-level Run and its existing Potential atomically.
3. Persist explicit archive query/families with archive digest and ordered IDs;
   use revision conflicts to prevent concurrent lost updates.
4. Restore one shared snapshot after login/refresh/restart, retry failed reads,
   and make global search versus local card selection explicit.
5. Back up/restore, independently review, then deploy by ordinary fast-forward.
6. Run one fresh narrow live search, verify its derived Potential and execute a
   sealed archive search. Verify a fresh browser session after service restart.

Failed/in-progress/internal-theme work cannot replace the completed workspace.
A no-hit run with successful connectors is a valid completed result; total
search/countersearch transport failure is not published. Historical statuses
remain unchanged. Cached explicit replay selects an existing Run without
rewriting provenance. Read-only restore never promotes history.

Production GOAL ownership and the unverified GitHub mirror gate remain unchanged.
