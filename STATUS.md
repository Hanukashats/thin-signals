# STATUS.md — Thin Signals LivingSet

Delivery package deadline: **2026-09-29 23:59 MSK** · Plan revision: **7.8** (parent 7.7) · Reliability work performed: **2026-10-12**

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

7.8 continuation: evidence and provider boundaries are hardened without changing `rules-0.1`, weights, thresholds or P01–P18. `checklist-v18` validates reader structure and positive/counter evidence roles; only a preserved primary fragment can remain `verified`, while snippets and non-primary text are capped to `supported`. Off-topic rejection precedes below-watchlist return. Mandatory OpenRouter ZDR fields cannot be weakened; returned model and cached response provenance are checked. Three modules share the evidence-first shell: live signals, a separate potential queue over current scored observations, and search over the sealed 29.09 old-technology archive. Facts/hypotheses/checks/sources and run provenance stay separate. Figma v4 is node `41:178`; transparent logo/favicon are versioned. API/UI run as persistent DynamicUser units, active and enabled.

The public route is `https://tsignal.aispaces.ru` through Caddy on VM105 to
VM232's private `:18443` listener. Account hashes and provider/database
credentials remain only in host `.secrets/`. GOAL queue ownership remains
`project=thin-signals`, `agent=codex-backend`; active baseline card is
`g-2629cc78010b`, followed by bounded-retrieval card `g-62fcfd60cd61`.

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
| Checklist | branch `checklist-v18` + `technology-candidate-0.1`; production remains unchanged; old persisted rows remain historical and are excluded from the active potential queue |
| Production delivery | VM232 public; PostgreSQL/API/UI/sing-box/research services active+enabled; SearXNG patch upgrade and controlled container restart recovered automatically |
| Canonical Git | private SourceCraft `shats123/thin-signals`; public GitHub delivery snapshot `Hanukashats/thin-signals`, `main=0c1fdd3` verified |
| Reliability branch | `feat/thin-signals-reliability-20261012`; not deployed; real Git timestamps retained |

## Verified in this increment

- Astra independently audited the product path, live research containers and
  resource envelope. The branch now contains a default-off GPT Researcher
  adapter for its pinned synchronous API. One connector instance permits one
  call per top-level run and inherits the absolute run deadline. Generated prose
  is discarded; only bounded public URLs that pass a second SSRF-guarded fetch
  and normal preserved-evidence path can become hits. Reported cost, validation
  and request counts and hashed artifact references are exposed without prompts
  or local paths. Full findings: `reports/ASTRA_AUDIT_2026-10-12.md`.
- `openalex-work-0.1` now projects current official Work fields into allowlisted
  identity, chronology, ROR affiliation, access, integrity and reference-context
  roles. Work/DOI aliases deduplicate mirrors without merging conflicting Work
  IDs; only explicit ROR values contribute origin identity. Raw affiliations
  and unknown fields are dropped. A false retraction flag is explicitly
  `not_flagged`, not a completed integrity screen. One bounded live API canary
  returned a valid Work, DOI, ROR and typed roles.
- `run-status-0.2` makes total discovery failure `failed`, partial discovery or
  countersearch failure `degraded`, and failed countersearch blocks admission.
  The latest-run endpoint now returns the newest finished run instead of hiding
  failed/degraded outcomes. The complete suite now passes 319/319 against a fresh
  disposable migrated database; production data was not touched.
- `live-w20` attaches matching countersearch records to each candidate as a
  separate evidence channel. `checklist-v18` now requires at least one positive
  discovery fragment and refuses verified positive claims/transitions cited only
  to countersearch. A cited M01/M02/M03/M05/M06 finding may still exclude the
  card. Countersearch output cannot score or admit a card by itself.
- Wide theme results now form one versioned technology candidate per mechanism.
  DOI/URL mirrors count as one document/event, while independent origins count
  only explicit institution/lab identifiers. Distinct hosts without those IDs
  remain `unknown` and contribute no independence score; raw event funnel counts
  and cross-theme alias-bridge deduplication remain intact.
- `retrieval-0.3` runs connector calls with bounded concurrency and one inherited
  absolute deadline. Results completing after that deadline are discarded;
  changed wide budgets or ordered theme plans cannot reuse a deadline-failed
  child run. The safe global funnel treats DOI and URL as joint aliases,
  deduplicates the same source across themes despite incomplete DOI metadata or
  repeated URLs, keeps conflicting explicit DOIs separate, preserves the richer
  repeated-source metadata, and retains a source-backed child exclusion exactly once.
  Per-call timing, cached/executed counts, failures and skips use allowlisted scalar
  metadata only; raw prompts and hidden reasoning are not exposed.
- The default live path re-fetches a primary-first, configured maximum of source
  bodies inside the inherited deadline and stores immutable SHA-256 snapshots.
  Source cards distinguish `preserved` from `snippet_only`; verified features
  and transitions citing only snippets or non-primary text are deterministically
  capped to `supported`. Raw bodies and filesystem paths are not public.
- PostgreSQL persistence now serializes one live query with a transaction-scoped
  advisory lock. Concurrent identical saves return one canonical run instead of
  racing the unique constraints; the loser returns the stored result as a repeat.
- The operator-provided public wsignal reference was inspected read-only. Its
  normalized corpus series, evidence-bearing refutation and activity accounting
  were adopted as donor patterns; high agent count and public raw reasoning were
  rejected. Evidence: `reports/REFERENCE_WSIGNAL_REVIEW_2026-10-12.md`.
- Follow-up public runs showed unstable yield (64 agents/30 entries down to 56
  agents/one insufficient entry) and complete OpenAlex failure in three newer
  runs. Their breadth came mainly from corpus/query expansion plus web discovery.
  This supports bounded hypothesis generation followed by primary-source
  validation; it does not justify adding unbounded agents or treating HN/media
  volume as evidence.
- Source trust is now hostname/type based: DOI-shaped text in an unknown URL
  path cannot promote an untrusted web page to `primary`. The regression was
  RED before the fix and the focused trust suite passes after it;
  `source-trust-0.2` records the corrected contract.
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
2. **Persistence:** canonical step/evidence ledgers are not fully populated for existing live runs; JSON payloads are not a substitute for the intended durable ledger.
3. **Research integration:** GPT Researcher and SearXNG work together inside the
   research service. The Thin Signals adapter and preserved-source boundary are
   implemented and tested behind `TS_GPT_RESEARCHER_ENABLED=false`; it remains
   inactive until frozen replay/canary and the complete release candidate are
   independently accepted. OpenAlex enrichment is implemented on the branch but
   not deployed.
4. **Research scope:** New Life is a reproducible archive search, not new live web research. Its 15 hypotheses have no completed commercial/legal diligence.
5. **Build-only dependencies:** the 2026-10-12 Trivy scan reports 13 HIGH and
   6 MEDIUM findings in presentation-only pins `Pillow==11.3.0` and
   `fonttools==4.60.0`. They are not imported by the API/UI runtime; update them
   in a separately reviewed presentation rebuild rather than silently changing
   the sealed delivery package.
6. **Evidence provenance release gate:** bounded source snapshots and
   `checklist-v18` are implemented and tested on the branch. A frozen replay and
   canary must measure coverage/latency before production activation; saved
   historical runs remain immutable.
7. **Release state:** bounded search, timings, safe funnel and configuration
   fingerprint are implemented and tested on the reliability branch. Astra
   independently verified baseline SHA `5798a4f` after 285 tests on a fresh
   migrated database. W10 continues in later commits and is not deployed.
   Full original finding: `reports/LOGIC_AUDIT_2026-10-12.md`.
8. **Bounded-worker residue:** Python cannot forcibly stop an already running
   thread. Late results are rejected and HTTP calls inherit a remaining-time
   timeout, but a misbehaving connector may finish in the background. Keep the
   worker ceiling and include this case in load/canary verification.
9. **OpenAlex scope:** typed identity, chronology, affiliation, access and
   integrity metadata are implemented. Reference count is context, not proof of
   prior art or replication, and `not_flagged` is not a complete retraction
   screen. Those claims remain for the evidence-gated review/evaluation goals.

## Requirements snapshot

- tested: `TZ-04`, `TZ-06`, `LLM-01`, `SC-12`, `TS-INV-02`, `TS-INV-03`
- implemented: `LP-01…07`, `DN-01`, `RM-01`, `TZ-03`, `TZ-07`, `SC-06`, `SC-07`, `RS-01`
- tested: `RS-02`, `RS-03`, `RS-04`, `RS-06`
- in progress and feature-off: `RS-05`; planned and feature-off: `AR-01`
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

1. Complete W9 on `feat/thin-signals-reliability-20261012`, then publish the
   same verified SHA to SourceCraft and GitHub feature branches.
2. Implement W10/W11 behind disabled flags; do not activate the role loop until
   frozen replay, holdout, ablation and rollback criteria pass.
3. Fill the factual personal team fields in slides 2–4 before external submission;
   observe a real-account authenticated production smoke when an authorized
   existing session is available. No accounts were read or changed for this release.
4. Continue separate versioned work for durable ledger population, bounded
   retrieval and score monotonicity; none may be hidden inside a recovery-only change.
