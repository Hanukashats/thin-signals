# ADR-015: shared latest completed workspace

Date: 2026-10-16. Status: proposed for independent review.
DecisionRecord: additive persistence contract, parent LivingSet 7.8.

The operator requests a test across all three modules and restoration of the
last completed result after refresh, login and service restart. Canonical runs
already live in PostgreSQL; Potential is a persisted derivative of that run.
New Life searches a sealed archive, not the web.

Use one PostgreSQL workspace row referencing the canonical Run and storing only
an archive search descriptor (query, families, archive digest/version, result
identifiers). Do not duplicate run/card payloads or create another ledger.
The latest workspace is shared by the existing single-tenant operator desk.
Explicit archive search submissions change the shared result; selecting a card
or filtering Potential is session-local browsing. Show this behavior in the UI.

Completed top-level runs publish inside the same transaction as Run, Decision
and any review events. Internal fanout children, incomplete work, failed
transport and incompatible versions cannot publish. A successful explicit
cached replay may select its existing immutable Run again; completion and
publication order is serialized by the workspace row lock, not search start
time. A repeated publication of the current run is a no-op. Archive writes use
an expected revision and cannot overwrite a concurrent run publication. Same
descriptor retries are idempotent.

GET is read-only; new sessions load the shared snapshot. A missing workspace is
an honest empty state, with the sealed archive available. A separate operator
bootstrap can select the latest compatible historical parent run. Version drift
is reported explicitly; old run stats are never silently re-scored. An archive
digest mismatch cannot masquerade as the saved search result.

Verification requires isolated PostgreSQL regressions for atomicity, child
exclusion, review persistence, failure preservation, concurrent edits, replay,
restart and API errors; the full reliability suite; desktop/mobile browser
review; one live narrow run, its derived Potential and one archive query; then a
restart/fresh-session restoration check. Back up and restore before migration.
Rollback deploys the prior code while preserving the additive table. Scoring
rules, gates, prompts, review policy and GOAL stay unchanged.
