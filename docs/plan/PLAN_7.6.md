# Thin Signals — plan 7.6: evidence integrity and operator UI

Date: **2026-10-01**. Parent: **7.5**. Class: minor continuation inside W3/W4. The scoring weights, thresholds, registry P01–P18, database schema and admitted-order formula are unchanged.

## Why this increment exists

An independent reality audit found that the screen could visually promote `watchlist` cards as an “official TOP-15”, and that a model-produced `verified` value could reach scoring without a valid fragment reference. Provider policy also allowed host configuration to overwrite mandatory ZDR values. These are integrity defects, not a reason to redesign the scoring formula.

## In scope

1. Fail closed when a `verified` P01–P18 claim or verified transition has no in-range `[n]` reference to the actual fragments read by the checklist.
2. Force `zdr=true` and `data_collection=deny` after provider extras, and reject a response model outside the configured allowlist.
3. Persist one checklist model/provider pair into the run provenance.
4. Replace misleading aggregate verdicts with per-card verdict groups, run provenance and explicit integrity warnings.
5. Separate facts, model hypotheses, checks and sources in the Russian operator screen; describe dates as query context rather than a typed filter.
6. Implement the editable Figma workbench as three operator modules with the
   same filter/ranking/evidence-inspector grammar: current signals, a separate
   below-gate review queue, and the dated old-technology research archive.
7. Use a transparent AGI Space lockup and transparent compact favicon without a
   baked-in dark plate; preserve keyboard/mobile accessibility.
8. Replace transient root-run API/UI processes with versioned loopback-only
   systemd units using isolated dynamic identities, host credentials and
   restart-on-failure.
9. Review correction (`potential-v2`, `checklist-v15`): exclude off-topic cards before score-threshold returns; select high potential from current scored watchlist observations below 0.60 as well as near-watchlist exclusions below 0.35. Deduplicate candidates, expose the target gate and formula, and require a new run for historical checklist versions. This changes the separate triage contract, not `rules-0.1`.

## Explicitly out of scope

- Rebalancing weights or fixing score monotonicity without a new rules version, eval and independent acceptance.
- Claiming that archive lookup is fresh web discovery. The third module searches
  the integrity-checked 2026-09-29 research package; a new web research run is a
  separate versioned pipeline.
- Inventing typed date filtering before the API and connector contracts support it.
- Creating or taking the existing GOAL card owned by `project=thin-signals agent=cursor-bk2`.

## Acceptance

- Focused integrity/UI tests pass; full tests run against an isolated test database.
- Invalid/missing evidence links cannot yield a scored card; a valid link still can.
- Hostile provider extras cannot weaken ZDR; an unallowlisted returned model is rejected before provider lookup.
- The UI contains no “Официальный ТОП-15” claim for a mixed list and no run-wide decision inferred from the first card.
- Figma node `41:178` and production implement the same three-module workbench,
  transparent logo and Deep Space tokens.
- SourceCraft points to the release commit. A GitHub mirror is not claimed until
  its exact repository and dedicated credential are verified.
- Local API/UI and `https://tsignal.aispaces.ru` pass health checks after deployment; rollback commit is recorded.
