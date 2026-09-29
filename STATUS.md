# STATUS.md — Thin Signals LivingSet

Delivery package date: **2026-09-29** (operator reports organizer authorization) · Plan revision: **7.6** (parent 7.5)

Delivery verified: production runs the released three-module UI, including the
`86b6840` caption and finalized typography/presentation. The replacement package
preserves that product behavior. API/UI units remain persistent, active and enabled.
The new fonts are genuinely
loaded local Cyrillic Source Sans 3 / Source Serif 4, confirmed by Chrome glyph
inspection; controls are 16 px and metrics use tabular figures. The independent
typography and complete delivery reviews accepted the preceding frozen delivery.
The public production login also passes actual glyph inspection, desktop/mobile
overflow and browser-error checks. Fresh backup/restore verified 148/148 runs.
Detailed receipt: `reports/RELEASE_2026-09-29.md`.

The actual production sample has **2 watchlist / 2 potential**, while the previous
4/3 result was staging. Fresh production timing is approximately **8m13s** versus
the immediately preceding equivalent staging's **8m51s**. Old pre-checklist
production duration is unknown; search breadth/depth/thresholds were not weakened.
See `reports/SEARCH_TIMING_2026-09-29.md`.

7.6 continuation: evidence and provider boundaries are hardened without changing `rules-0.1`, weights, thresholds or P01–P18. `checklist-v15` validates reader structure and rejects verified features/transitions or fired exclusion counters without an actual `[n]` fragment; off-topic rejection precedes below-watchlist return. Mandatory OpenRouter ZDR fields cannot be weakened; returned model and cached response provenance are checked. Three modules share the evidence-first shell: live signals, a separate potential queue over current scored observations, and search over the sealed 29.09 old-technology archive. Facts/hypotheses/checks/sources and run provenance stay separate. Figma v4 is node `41:178`; transparent logo/favicon are versioned. API/UI run as persistent DynamicUser units, active and enabled.

The public route is `https://tsignal.aispaces.ru` through the home proxy to VM101. Account hashes and provider/database credentials remain only in host `.secrets/`. GOAL queue ownership remains `project=thin-signals`, `agent=cursor-bk2`; this Codex continuation did not create, claim or take its card.

## Current

| Field | Value |
|---|---|
| Host of record | Georg VM101 `/opt/thin-signals` (`cursor-agent`) |
| Phase | **P3 LivePath / P4 AnalystUI** |
| W3-live | **in_progress** — live search exists; honest scored TOP-15 and durable per-step ledger remain incomplete |
| W4-ui | **in_progress, deployed shell and verified typography** — three modules live; real-account authenticated production smoke remains unobserved |
| Rules | `rules-0.1`, unchanged |
| Checklist | `checklist-v15`; old persisted rows remain historical and are excluded from the active potential queue |
| Production delivery | Released three-module UI; API/UI persistent DynamicUser services, active+enabled, local/public health and actual fonts verified; package-date replacement does not change product code |
| Canonical Git | private SourceCraft `shats123/thin-signals`; GitHub mirror required but not configured/verified on VM101 |

## Verified in this increment

- Evidence-link and LLM-policy RED/GREEN tests reproduce the defects then pass after the fix.
- UI view-model tests prove a `watchlist` card is never grouped as a weak signal.
- Run integrity warns about checklist drift, missing provider and missing independent evidence.
- Independent review reproduced three potential defects: unreachable high-potential selection, off-topic admission below 0.35, and silent legacy re-ranking. RED/GREEN regressions cover all three. `potential-v2` uses scored watchlist observations in [0.35, 0.60) for high potential, deduplicates top/exclusions, and keeps near-watchlist selection in [0.25, 0.35). Distances explicitly name the 0.35 or 0.60 target; weak-signal labels and rules remain unchanged.
- Transparent logo and compact favicon remove the baked-in dark rectangle; the supplied source is preserved exactly.
- Versioned systemd units bind to loopback, use separate dynamic identities, `LoadCredential`, protected filesystem and `Restart=on-failure`.
- Figma frame `41:178` defines the three-module Deep Space workbench.
- 223 tests pass against `thin_signals_test_1790887573`; ruff, LivingSet links and diff checks pass. The three added regressions first failed on the reviewed candidate and passed after correction.
- Backup `/srv/thin-signals-backups/20261001-2230/database.dump` was restored into a disposable database; all 147 runs were present. Production data was not modified by the restore check.
- Current private delivery backup restored all 148/148 runs. All 223 product tests and 11 presentation-verifier regressions pass for the replacement package. The prior rollout restarted only UI; the date-only replacement requires no service restart. Public/local health and API readiness pass; the production public login has no browser errors or 390 px horizontal overflow.

## Open audit findings

1. **Rules change required:** score can be non-monotonic when adding a positive secondary feature because primary reassignment changes weights. Do not hotfix; create a new rules version, eval and independent acceptance.
2. **Run contract:** all search connectors failing can still end as `succeeded`; define a versioned degraded/failed status contract before changing persisted/API semantics.
3. **Persistence:** canonical step/evidence ledgers are not fully populated for existing live runs; JSON payloads are not a substitute for the intended durable ledger.
4. **Release:** GitHub mirror identity/authentication is absent on VM101. SourceCraft remains canonical; do not claim dual push until the exact mirror and dedicated credential are verified.
5. **Research scope:** New Life is a reproducible archive search, not new live web research. Its 15 hypotheses have no completed commercial/legal diligence.

## Requirements snapshot

- tested: `TZ-04`, `TZ-06`, `LLM-01`, `SC-12`, `TS-INV-02`, `TS-INV-03`
- implemented: `LP-01…07`, `DN-01`, `RM-01`, `TZ-03`, `TZ-07`, `SC-06`, `SC-07`
- implemented: `TZ-14` (15-slide editable PPTX/PDF and complete render/visual checks; personal team fields still require factual input)
- release blocker: `TZ-15` (GitHub mirror not verified)
- removed to lineage: `SC-01`, `SC-04`, `SC-05`, `SC-08`, `SC-10`, `TS-AG-01…16`, `TS-AG-18`

## Hosts

- **VM101 is the current production host:** PostgreSQL at `127.0.0.1:55432`, API at `127.0.0.1:8095`, Streamlit at `127.0.0.1:8501`; public TLS terminates on the home proxy and reaches VM101 over the existing internal route.
- VM230 remains a stale development/demo checkout and must not be treated as current production until it fast-forwards from SourceCraft and passes its own smoke tests.

## Next trigger

1. Fill the factual personal team fields in slides 2–4 before external submission;
   observe a real-account authenticated production smoke when an authorized
   existing session is available. No accounts were read or changed for this release.
2. Locate or create the exact GitHub mirror with dedicated repository-scoped authentication; push the identical SHA and close `TZ-15` only after comparing both refs.
3. Open separate versioned work for connector-total-failure status, durable ledger population and score monotonicity; none may be hidden inside this UI increment.
