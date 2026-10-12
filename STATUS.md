# STATUS.md — Thin Signals LivingSet

Delivery package deadline: **2026-09-29 23:59 MSK** · Plan revision: **7.7** (parent 7.6) · Recovery work performed: **2026-10-12**

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

The public route is `https://tsignal.aispaces.ru` through Caddy on VM105 to
VM232's private `:18443` listener. Account hashes and provider/database
credentials remain only in host `.secrets/`. GOAL queue ownership remains
`project=thin-signals`, `agent=cursor-bk2`; this Codex continuation did not
create, claim or take its card.

On 2026-10-12 recovery was completed on Home-PVE VM232: Ubuntu 26.04.1, 4
vCPU, 12 GB RAM and a 120 GB disk. All 148 saved runs were recovered before
the public cutover. SearXNG and GPT Researcher now run locally in private
containers, so live search no longer depends on backend VM101. Receipt:
`docs/ops/VM232.md` and `reports/VM232_RESEARCH_2026-10-12.md`.

## Current

| Field | Value |
|---|---|
| Host of record | Home-PVE VM232 `/opt/thin-signals` (`agent`) |
| Phase | **P3 LivePath / P4 AnalystUI / P6 recovery** |
| W3-live | **in_progress** — live search exists; honest scored TOP-15 and durable per-step ledger remain incomplete |
| W4-ui | **in_progress, deployed shell and verified typography** — three modules live; real-account authenticated production smoke remains unobserved |
| Rules | `rules-0.1`, unchanged |
| Checklist | `checklist-v15`; old persisted rows remain historical and are excluded from the active potential queue |
| Production delivery | VM232 public; PostgreSQL/API/UI/sing-box/research services active+enabled; SearXNG patch upgrade and controlled container restart recovered automatically |
| Canonical Git | private SourceCraft `shats123/thin-signals`; public GitHub delivery snapshot `Hanukashats/thin-signals`, `main=0c1fdd3` verified |

## Verified in this increment

- The historical VM231 recovery checkpoint preserved four PVE snapshots, a
  checksum-recorded PostgreSQL 16 backup and 148/148 restored runs; VM231 is no
  longer present in the live inventory and that receipt is retained as lineage.
- VM232 owns pinned SearXNG `2026.10.11-ad46ebd7d` at exact amd64 digest
  `sha256:00ad29bb7d72d896ac3b3ff8b252d9ad9939da3e014828934363c61dba9b7e09`
  and GPT Researcher v3.7.0 built from commit `0957c301`. The SearXNG upgrade
  passed an isolated canary, Trivy HIGH/CRITICAL gate, direct JSON/connector
  tests and controlled restart; GPT Researcher was not recreated. Both remain
  loopback-only, and API/UI/public health stayed HTTP 200.
- GPT Researcher live canary completed in 80.76 s, discovered 14 unique source
  URLs, wrote a 6,316-character report and reported $0.05347 cost. Its output
  remains advisory.
- Thin Signals live canary `f91b5e7d7676a800` read 24 sources, excluded 22,
  produced one potential item and correctly returned `HOLD` with zero admitted
  cards instead of filling the list.
- VM233 NetBird hub memory is 2 GB and remains separate from OpenWrt. Its
  dashboard is public and healthy, but initial NetBird setup is still required;
  a rebuilt peer/policy mesh is not yet claimed.
- VM104 `kingston-recovery` is stopped with `onboot=0`. VM105 OpenWrt/Caddy now
  boots first (order 10), followed by VM233 (20) and VM232 (30).
- Logout now clears the complete Streamlit session instead of retaining another
  user's filters, selections and draft query fields. The regression was RED
  before the fix and passes after it.
- UI saved-result recovery hotfix is tested, pending release verification: a failed initial load remains retryable in the same session; «Загрузить последний результат» reloads saved cards without starting a search; Potential displays loading issues; unloaded Signals no longer claim a completed empty search. Existing cards survive reload failure, and successful load/logout clears stale warnings. Eight deterministic AppTest cases cover these transitions (seven RED before the fix); scoped 15/15 and safe non-database suite 227/227 pass, with four database integration tests deliberately not run for this UI-only patch. No API, schema, scoring or stored-run changes.
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
- Public GitHub `Hanukashats/thin-signals` is verified with default branch
  `main` at exact historical commit `0c1fdd37cd95`; no force-push or timestamp
  rewrite was used. The 45-commit reachable history passed a bounded secret
  pattern scan before publication, and the pre-push gate passed all 234 tests.

## Open audit findings

1. **Rules change required:** score can be non-monotonic when adding a positive secondary feature because primary reassignment changes weights. Do not hotfix; create a new rules version, eval and independent acceptance.
2. **Run contract:** all search connectors failing can still end as `succeeded`; define a versioned degraded/failed status contract before changing persisted/API semantics.
3. **Persistence:** canonical step/evidence ledgers are not fully populated for existing live runs; JSON payloads are not a substitute for the intended durable ledger.
4. **Research scope:** New Life is a reproducible archive search, not new live web research. Its 15 hypotheses have no completed commercial/legal diligence.
5. **Build-only dependencies:** the 2026-10-12 Trivy scan reports 13 HIGH and
   6 MEDIUM findings in presentation-only pins `Pillow==11.3.0` and
   `fonttools==4.60.0`. They are not imported by the API/UI runtime; update them
   in a separately reviewed presentation rebuild rather than silently changing
   the sealed delivery package.
6. **Evidence provenance:** the live harness does not fetch/snapshot source
   bodies, and a checklist `verified` status may therefore cite only a search
   or API snippet. Version the provenance rule and evaluate saved cases before
   changing labels.
7. **Search budget:** up to 34 connector calls run sequentially with 40-second
   request timeouts and no global deadline. Add bounded concurrency, timing
   evidence and an overall budget without weakening recall. Full review:
   `reports/LOGIC_AUDIT_2026-10-12.md`.

## Requirements snapshot

- tested: `TZ-04`, `TZ-06`, `LLM-01`, `SC-12`, `TS-INV-02`, `TS-INV-03`
- implemented: `LP-01…07`, `DN-01`, `RM-01`, `TZ-03`, `TZ-07`, `SC-06`, `SC-07`, `RS-01`
- proposed/operator-gated: `AR-01`
- implemented: `TZ-14` (15-slide editable PPTX/PDF and complete render/visual checks; personal team fields still require factual input)
- tested: `TZ-15` (public GitHub default branch resolves to exact delivery SHA)
- removed to lineage: `SC-01`, `SC-04`, `SC-05`, `SC-08`, `SC-10`, `TS-AG-01…16`, `TS-AG-18`

## Hosts

- **VM232 is production:** `192.168.5.232`; PostgreSQL `127.0.0.1:55432`, API
  `127.0.0.1:8095`, Streamlit `127.0.0.1:8501`, SearXNG `127.0.0.1:28088`, GPT
  Researcher `127.0.0.1:28000`; only private ingress `192.168.5.232:18443` is
  reachable by VM105.
- **VM233 is the separate NetBird control plane:** `192.168.5.233`, 2 GB RAM;
  deployment is healthy but network enrollment/policies remain incomplete.
- **VM104 is parked recovery tooling:** stopped, `onboot=0`.
- **VM230 is historical:** stopped and not production. VM231 no longer appears
  in the current PVE inventory; `docs/ops/VM231.md` is historical recovery
  evidence, not a live-host claim.

## Next trigger

1. Independently review and merge `chore/searxng-2026-10-11-audit`; VM232 is
   already running its verified candidate and the rollback snapshot remains
   available.
2. Issue a separate authenticated command before implementing or activating
   ADR-011 adversarial review.
3. Fill the factual personal team fields in slides 2–4 before external submission;
   observe a real-account authenticated production smoke when an authorized
   existing session is available. No accounts were read or changed for this release.
4. Open separate versioned work for connector-total-failure status, durable ledger population and score monotonicity; none may be hidden inside this recovery increment.
