# STATUS.md — Thin Signals LivingSet

Delivery package deadline: **2026-09-29 23:59 MSK** · Plan revision: **7.8** (parent 7.7) · Reliability work performed: **2026-10-12…13**

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

7.8 continuation: evidence and provider boundaries are hardened without changing `rules-0.1`, weights, thresholds or P01–P18. `checklist-v19` validates reader structure and positive/counter evidence roles; only a blob-backed, SHA-256-attested primary fragment can remain `verified`, while snippets, missing/corrupt snapshots and non-primary text are capped to `supported`. Off-topic rejection precedes below-watchlist return. Mandatory OpenRouter ZDR fields cannot be weakened; returned model and cached response provenance are checked. Three modules share the evidence-first shell: live signals, a separate potential queue over current scored observations, and search over the sealed 29.09 old-technology archive. Facts/hypotheses/checks/sources and run provenance stay separate. Figma v4 is node `41:178`; transparent logo/favicon are versioned. API/UI run as persistent DynamicUser units, active and enabled.

The bounded researcher/critic/defender/control-critic round is implemented behind
`TS_ADVERSARIAL_REVIEW_ENABLED=false`. It uses equal role budgets, a deterministic
fail-closed arbiter and an append-only PostgreSQL review ledger. Narrow and wide
product integration, disabled/no-call behavior, replay, failure HOLD, persistence
and safe public traces pass the complete 407-test suite on a disposable database.
Enabled runs reserve their identity durably before role spend under a PostgreSQL
session lock pinned to the same connection as its writes: concurrent processes
wait for one canonical result without exhausting the pool, while process death or
an interrupted save closes as a stable `HOLD` and cannot silently spend again.
Unattested or mismatched route identifiers are erased before public or persistent
output. Effective routing configuration and a cancellable hard wall-clock
registry-plus-completion deadline are validated fail-closed; DNS is resolved
inside the cancellable async request so a timed-out lookup cannot send a late
completion. The original hostname remains intact for native multi-address DNS,
proxy bypass and TLS/SNI, and missing returned-model metadata is rejected.
Evaluation and production activation remain separate gates.

The first bounded production canary correctly failed closed when live models
rewrote or cross-linked citation IDs. `adversarial-review-0.2` now constrains
structured decoding to current-round identifiers and supplies exact defender and
control-critic reference bindings. Its focused suite passes, and the complete
suite is **446 passed** on a new migrated disposable PostgreSQL database. A fresh
live canary and independent release verification are still pending.
An additional live run exposed an empty cited-evidence bundle on an otherwise
admitted card. `review-integration-0.2` now reports `skipped_no_evidence` without
spending four role calls; it never upgrades that absence into a positive review.
The same receipt showed a paywalled DOI while OpenAlex already carried an
explicit open-access location. `retrieval-0.9` now prefers that OA target for
snapshot acquisition under the unchanged SSRF, final-URL trust and SHA-256
attestation boundary; the DOI remains the canonical source identity.

Independent Astra verification accepted the frozen code commit `9f3a139` with
no scoped P0/P1/P2 finding: 407 tests and Ruff passed, including native route,
PostgreSQL, pool saturation, process-death, DNS/proxy/TLS and deadline probes.
Receipt: `reports/ASTRA_C05_PASS_9F3A139_2026-10-13.md`.

`rules-0.2` is now an evaluation-only candidate. It fixes the positive-evidence
non-monotonicity by separating semantic-primary explanation from strongest-first
scoring slots, while retaining v0.1 weights and thresholds. All executable
threshold consumers use the versioned scorer contract. Historical v0.1 rows are
unchanged and production still requires replay, holdout and independent review.
The remediated candidate repository gate is **455 passed** on a disposable
migrated PostgreSQL database; Ruff, LivingSet links, YAML and whitespace checks
pass, with exhaustive
primary-choice/status monotonicity, dynamic-threshold and attested-promotion
regressions.

Wave 4 deterministic evaluation is now implemented. The `rules-0.2` scorer
reproduces all 170 frozen `rules-0.1` rows exactly: 0 baseline mismatches,
0 changed labels and 0 confidence decreases; holdout F1 remains 0.9541. On a
separate 8-case replay and structurally distinct 8-case sealed holdout, the full
researcher/critic/defender/control path has P/R 1.0/1.0, zero false or
evidence-less promotions, zero unresolved-critical promotions, exact-verdict
accuracy 1.0 and stability 1.0. Defender/control role-unavailability ablations
now execute twice through the real runner and fail closed with recall 0.0;
their errors, resources and stability are measured rather than reconstructed.
The initial independent Astra audit of `74445de` rejected three safety/evaluation
gaps. A second audit of `26b4e8d` confirmed those fixes but found an unbound
control finding, an unknown critical replacement and a provider-failure ablation
that silently restored the critic. The current remediation binds control to the
exact rebuttal/evidence, validates the effective replacement and layers ablation
failures without erasing the scenario failure. A third audit of `9e5cc76` found
that corrected/narrowed claims still inherited citations from the superseded
claim. The current remediation replaces, rather than unions, effective evidence,
aligns coverage with that rule and rejects ambiguous multiple replacements.
The fourth audit of `3ae2bdc` then found mixed replacement plus additive defenses
for one claim were order-dependent. The current candidate rejects every such
unordered mixed round in validation and arbitration, and evaluation reports no
coverage for the invalid target regardless of record ordering.
Fresh independent re-verification is still required. These are deterministic
fixture/stored-extraction results,
not a claim about live model quality or the ten-signal target; bounded production
canary remains a release gate.

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
| Checklist | branch `checklist-v24` + `technology-candidate-0.1`; production remains unchanged; old persisted rows remain historical and are excluded from the active potential queue |
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
  failed/degraded outcomes. The complete suite now passes 327/327 against a fresh
  disposable migrated database; production data was not touched.
- `live-w21` attaches matching countersearch records to each candidate as a
  separate evidence channel. `checklist-v19` now requires at least one positive
  discovery fragment and refuses verified positive claims/transitions cited only
  to countersearch. A cited M01/M02/M03/M05/M06 finding may still exclude the
  card. Countersearch output cannot score or admit a card by itself.
- Wide theme results now form one versioned technology candidate per mechanism.
  DOI/URL mirrors count as one document/event, while independent origins count
  only explicit institution/lab identifiers. Distinct hosts without those IDs
  remain `unknown` and contribute no independence score; raw event funnel counts
  and cross-theme alias-bridge deduplication remain intact.
- `retrieval-0.4` runs connector calls with bounded concurrency and one inherited
  absolute deadline. Results completing after that deadline are discarded;
  changed wide budgets or ordered theme plans cannot reuse a deadline-failed
  child run. The safe global funnel treats DOI and URL as joint aliases,
  deduplicates the same source across themes despite incomplete DOI metadata or
  repeated URLs, keeps conflicting explicit DOIs separate, preserves the richer
  repeated-source metadata, and retains a source-backed child exclusion exactly once.
  Per-call timing, cached/executed counts, failures and skips use allowlisted scalar
  metadata only; raw prompts and hidden reasoning are not exposed.
- Independent Astra verification of `e006a36` correctly rejected four gaps.
  The remediation candidate pins TCP to the already validated public IP (while
  retaining the original Host/TLS SNI), prevents snapshot reads from outliving
  the inherited deadline, re-hashes the stored blob plus fragment attestation
  before `verified`, and joins short-title DOI/OpenAlex mirrors by shared Work
  identity. Production remains untouched pending a fresh independent verdict.
- A second independent Astra pass over `4cccc20` found two deeper C02 bypasses
  and a late-EOF transport edge. The current frozen candidate binds URL, raw
  body, MIME type, canonical text and cited fragment through immutable SHA-256
  attestations; redirect trust can only decrease; final EOF is inside the same
  monotonic deadline. The complete suite is 332/332 on a disposable migrated
  database. Production and feature flags remain unchanged pending another
  independent verdict.
- A third frozen-candidate review found public citation misattribution and
  slow-header deadline drift. `checklist-v21` now cites the attested final URL;
  `retrieval-0.6` actively aborts header parsing at the same absolute deadline.
  Both exact RED regressions and the complete 334-test suite pass locally;
  production remains untouched pending a clean independent PASS.
- A fourth isolated review found that `fetched_source_type` was not covered by
  the manifest and that TLS handshake temporarily hid its socket from the
  deadline watchdog. `snapshot-evidence-0.3` now binds source type, while
  `retrieval-0.7` exposes the real TLS socket before handshake. Both exact RED
  regressions and the complete 336-test suite pass locally; production remains
  untouched pending a clean independent PASS.
- A fifth isolated review found a near-budget TCP→TLS race: a watchdog could
  fire before the socket was published, after which TLS reused the original
  timeout. `retrieval-0.8` recomputes the remaining absolute budget after TCP,
  TLS wrapping and handshake. Both 70 ms and 95 ms connection-delay regressions
  pass, as does the complete 337-test suite; production remains untouched
  pending a clean independent PASS.
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

1. **Rules release pending:** versioned `rules-0.2` fixes the known
   non-monotonicity, passes exhaustive property tests and reproduces all 170
   historical rows without change. A reconstruction mismatch now invalidates
   the replay and returns a non-zero CLI status. Fresh independent acceptance
   and canary are still required before production activation.
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
   `checklist-v24` are implemented and tested on the branch. Attested evidence
   contains only canonical snapshot text; mutable search titles cannot enter a
   verified quotation. A frozen replay and
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
- in progress and feature-off: `RS-05`; tested and feature-off: `AR-01` (independent review and canary pending)
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

1. Independently re-verify the remediated Wave 4 candidate, including the
   attested critical-claim gate, exact verdicts, executed role-unavailability
   ablations, replacement/mixed-action ordering and invalid 170-row replay behavior.
2. Deploy it first with the review
   flag off, run the production canary, then publish the same SHA to SourceCraft
   and GitHub feature branches.
3. Fill the factual personal team fields in slides 2–4 before external submission;
   observe a real-account authenticated production smoke when an authorized
   existing session is available. No accounts were read or changed for this release.
4. Continue separate versioned work for durable ledger population, bounded
   retrieval and score monotonicity; none may be hidden inside a recovery-only change.
