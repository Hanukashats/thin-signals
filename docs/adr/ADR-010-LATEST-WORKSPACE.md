# ADR-010: shared latest completed workspace

Delivery package date: 2026-09-29. Status: proposed for independent review.
DecisionRecord: additive persistence contract, parent LivingSet 7.6.

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

Completed top-level runs publish inside the same transaction as Run/Decision.
Internal fanout children, incomplete work, failed transport and incompatible
versions cannot publish. A successful explicit cached replay may select its
existing immutable Run again; completion/publication order is serialized by the
workspace row lock, not search start time. A repeated publication of the current
run is a no-op. Archive writes use an expected revision and cannot overwrite a
concurrent run publication. Same descriptor retries are idempotent.

GET is read-only; new sessions load the shared snapshot. A missing workspace is
an honest empty state, with the sealed archive available. A separate operator
bootstrap can select the latest compatible historical parent run. Version drift
is reported explicitly; old run stats are never silently re-scored. An archive
digest mismatch cannot masquerade as the saved search result.

Verification: isolated PostgreSQL regressions for atomicity, child exclusion,
failure preservation, concurrent edits, repeat behavior, restart and API errors;
full product suite; desktop/mobile browser verification; one live narrow run,
derived Potential and one archive query, then restart/fresh-session restoration.
Back up/restore before migration; rollback deploys the prior code with the
additive table preserved. Scoring rules, gates, prompts and GOAL stay unchanged.
