# Astra frozen review of `c191975`

Date: 2026-10-12. Reviewer: independent Astra sub-agent. Reviewed tree:
`c191975a6e26f4c430d425b14554cc01f7ea34f2`, read-only.

## Frozen verdict

HOLD. No P0. Four P1 defects were reproduced despite a green 267-test suite:

1. countersearch text could be the only fragment and still support positive
   verified features and a transition;
2. a wide theme could reuse a failed child cache after the configured parent
   budget changed;
3. wide reports hid child connector failures and skipped-deadline themes;
4. a connector result completing after the absolute deadline could be accepted
   when the worker held the GIL long enough for the future to appear done.

P2 observations were stale LivingSet ownership/revision text, concurrent
check-then-insert persistence, approximate pending-call timing and Python's
inability to forcibly stop an already running worker thread.

## Remediation after the frozen review

- `checklist-v17` builds one ordered evidence bundle, requires positive-channel
  text, and requires verified positive features/transitions to cite its positive
  prefix. Negative maturity counters may still cite countersearch fragments.
- `retrieval-0.3` includes a stable hash of the plan version, ordered theme IDs
  and query hashes in child identity; absolute monotonic timestamps are not keys.
- Wide telemetry copies only allowlisted scalar connector metadata, labels
  cached versus executed calls, aggregates sequential theme timing, and exposes
  failed/degraded/skipped themes. Missing connector metrics remain unknown
  (`funnel=null`) rather than fabricated zeros.
- Connector output completed at or after the inherited deadline is discarded
  as `deadline_exceeded`.
- PostgreSQL live-run persistence uses a transaction advisory lock per query;
  concurrent identical writes return the canonical stored run.
- `plan.yaml` and `README.md` now point to LivingSet 7.8 and the active
  `codex-backend` queue.

## Evidence before second review

- Added deterministic regressions for all four P1 defects and the persistence
  race.
- Full suite: 273 passed, one pre-existing Starlette/httpx deprecation warning,
  on a fresh migrated disposable PostgreSQL database.
- Ruff, YAML parse, `git diff --check`, and LivingSet links
  (`requirements=52`, `waves=19`, `forks=13`) passed.
- The disposable database was removed; production was not read or modified.

This report records implementer evidence only. Promotion still requires a
second independent review of the remediation commit.

The second review of `444ba935` confirmed the four P1 remediations and the
concurrent persistence race, then found two P2 accounting/cache defects: the
same event was counted once per theme while child exclusions disappeared, and
a failed child could cross a changed plan boundary. Both now have executable
RED/GREEN regressions. The new implementer run is 276 passed on a fresh migrated
disposable database; final review is still required on the new frozen SHA.
