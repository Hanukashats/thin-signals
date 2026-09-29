# CONTINUATION POINT — evidence-first audit and operator UI, 2026-10-01

## Verified delivery continuation

- SourceCraft/writer `86b6840`; production `f7a5a9d` (one caption commit behind).
- API/UI are now persistent, active and enabled; local API health/readiness and
  Streamlit health succeed. Public login renders with the transparent brand.
- The four previously untracked production evidence paths remain untouched.
- Before this delivery, production browser inspection confirmed that the requested `Source Sans 3` / `Source Serif 4`
  were not registered; only Streamlit's differently named `Source Sans` /
  `Source Serif` faces existed. The delivery candidate now passes real glyph
  inspection with local official fonts, 16 px controls, independent ACCEPT and
  all 223 product tests. The following older checkpoints are historical.
- Bounded continuation: supply official Cyrillic fonts through native Streamlit
  local font serving, verify desktop/mobile and isolated-DB tests, finalize the
  official-template presentation, reconcile Git and deploy the reviewed commit.
- Current Git contains no old presentation PPTX/PDF to remove. The two tracked
  PDFs are organizer requirements and must remain. Historical outboxes are
  evidence, not current delivery artifacts.
- Delivery package date is 2026-09-29. The operator reports organizer permission
  to use that date and omit actual integration/generation/verification dates
  from the delivery text and metadata. Replacement of the two delivery commits
  with an explicit `force-with-lease` is authorized. The package date does not
  assert when checks occurred. GOAL ownership remains unchanged.
- Search latency comparisons require request logs: database timestamps measure
  saving, not full research duration. Do not infer latency from those columns.

## Historical 2026-10-01 candidate checkpoint

- The final design is three-module Deep Space Figma frame `41:178`; the logo and favicon are transparent PNGs, without a dark plate.
- `checklist-v15` adds structural validation, evidence references for verified claims and fired exclusion counters, bounded cited excerpts, model/provider provenance and off-topic rejection before threshold returns. Cache reuse also validates mandatory policy and current routing.
- Potential-v2 is a separate deterministic review priority: high-index scored watchlist [0.35, 0.60) and near-watchlist [0.25, 0.35), current checklist only. New Life searches the 15-card integrity-checked research archive from 29.09.2026.
- Full isolated-DB test suite: 220 passed. Ruff, LivingSet links, diff and dependency consistency checks passed. Installer pip advisories remain a separate maintenance item; runtime packages had no known advisory in the audit.
- Desktop/mobile screenshots and dependency audit are in `/srv/codex-operator/outbox/1305367840_1790893410/`.
- Backup and restore verification: `/srv/thin-signals-backups/20261001-2230/database.dump`; 147 runs verified in a disposable restore database, subsequently removed.
- At this historical checkpoint, independent review/integration/receipt were pending. Its earlier Git-date convention was superseded by the explicit operator instruction recorded above.

Status before implementation:

- Canonical checkout `/opt/thin-signals`, `main` / SourceCraft `origin/main` at `66581d0`.
- This increment runs in isolated worktree `/srv/codex-operator/worktrees/1305367840_1790887573/thin-signals`, branch `fix/thin-signals-evidence-ui-1790887573`.
- The canonical checkout has four pre-existing untracked evidence paths (`docs/lineage/intake-2026-10-01/`, `reports/eval/2026-09-27-registry-7/`, `reports/eval/2026-09-27/`, `reports/goal/screen-c03.txt`). They are operator-owned and must not be changed or committed by this increment.
- SourceCraft is the configured canonical remote. The mandatory GitHub mirror is declared in `forks.yaml`, but no GitHub remote is configured in this checkout and the `gh` CLI is absent; mirror identity/authentication must be verified without exposing credentials before any push.
- Public UI `https://tsignal.aispaces.ru`, local API `127.0.0.1:8095`, local Streamlit `127.0.0.1:8501`, and PostgreSQL were healthy at audit start. API and UI are transient systemd units with `Restart=no`; deployment must preserve rollback and then verify process and public health.
- Current UI has the dusk theme and compact AGI Space favicon, but its semantics still overstate the result: a mixed weak-signal/watchlist list is titled “Официальный ТОП-15”, source totals refer only to selected cards, date fields are query prose rather than typed filters, and one card is used as the verdict for the whole run.
- Independent read-only audit reproduced two integrity defects: an LLM can mark a feature `verified` with a missing or out-of-range fragment reference and still score; provider policy extras can override mandatory ZDR fields and a response model is not rechecked against the allowlist.
- Score monotonicity and empty persistence ledgers remain method-level issues. They require a versioned rules/contract change and independent eval, so they are audit findings rather than silent hotfixes in this increment.
- GOAL ownership remains `project=thin-signals agent=cursor-bk2`; this Codex run does not create, claim, bind, or take that card.

Design source:

- Figma file: `https://www.figma.com/design/RbbhSTdppIVib4AUkGKvia`.
- Existing editable concept nodes: `30:97` (evidence-first desktop) and `32:136` (automation pipeline).
- Operator supplied a new metallic AGI Space lockup in `/srv/codex-operator/inbox/1305367840/1790887573_photo.jpg`.
- Chosen application: full metallic lockup on a dark plate for the login/brand moment; compact orbital mark for favicon and dense operational header. This preserves exact lettering and remains legible at both scales.

Continuation increment:

1. Add RED/GREEN tests and fail closed when any `verified` feature/transition lacks valid local evidence references.
2. Make ZDR/data-collection policy non-overridable and reject a response model outside the configured allowlist.
3. Update the operator UI to evidence-first, honest labels and explicit run provenance without changing weights, thresholds, ranking, or stored data.
4. Add the supplied logo as a versioned asset and update the editable Figma concept to document the selected responsive use.
5. Update the LivingSet status/requirements affected by the integrity and UI changes.
6. Run focused tests first, then the safe non-mutating test profile, link checks, lint, and independent review.
7. Reconcile with `main`, commit atomically, push SourceCraft and the verified GitHub mirror, deploy with rollback, and verify local/public health and screenshots.

Acceptance evidence required:

- Invalid/missing/out-of-range evidence references cannot produce a kept/scored card; valid `[1]` evidence still scores.
- Hostile provider extras cannot change `zdr=true` or `data_collection=deny`; an unlisted returned model is rejected.
- UI does not call a mixed list an official TOP-15 or infer a run-wide decision from the first card.
- New logo assets exist, Figma node IDs are recorded, and desktop/mobile presentation remains readable.
- No secret, operator-owned untracked artifact, score weight, threshold, donor file, or historical eval snapshot enters the diff.
- SourceCraft/GitHub commit identities, production health, and rollback point are recorded in the final handoff.
