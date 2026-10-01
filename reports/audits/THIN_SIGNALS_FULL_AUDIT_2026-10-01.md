# Thin Signals full audit — 2026-10-01

Scope: canonical source, live deployment, scoring/evidence boundary, LLM provider boundary, persistence, Russian operator UI, Figma source and release remotes. Baseline: SourceCraft `main` `66581d0`. Work ran in isolated branch/worktree and did not touch the operator-owned untracked lineage/eval artifacts in `/opt/thin-signals`.

## Reality

- Canonical repository: private SourceCraft `https://sourcecraft.dev/shats123/thin-signals`, Git remote `https://git@git.sourcecraft.dev/shats123/thin-signals.git`.
- GitHub mirror: required by `hosting.sourcecraft` / `TZ-15`, but no remote or repository-scoped credential is configured on VM101. Unauthenticated candidate probes return 404; the only GitHub SSH identity is backend-specific and cannot read `Hanukashats/thin-signals`.
- Production host: VM101 `/opt/thin-signals`. Public URL `https://tsignal.aispaces.ru`; local API `127.0.0.1:8095`, UI `127.0.0.1:8501`, PostgreSQL `127.0.0.1:55432`.
- VM230 is a stale development checkout and is not current production.
- Design source: Figma file `RbbhSTdppIVib4AUkGKvia`; audited concepts `30:97`, `32:136`; final three-module v4 frame `41:178`.

## Findings and disposition

| Severity | Finding | Evidence | Disposition |
|---|---|---|---|
| P0 | `verified` Pxx/transition could score with no valid fragment link | Reproduced with missing/out-of-range `[n]` and a kept card | **Fixed** in `checklist-v14`; fail closed as `evidence_invalid` |
| P0 | Environment policy could overwrite mandatory ZDR/data collection fields | Mock request sent `zdr=false`, `data_collection=allow` | **Fixed**; reserved values applied last |
| P0 | Provider could return a different model outside the TZ allowlist | ZDR-listed surprise model was accepted | **Fixed**; returned model rejected before provider lookup |
| P1 | Checklist provider was discarded, leaving run provenance incomplete | `_mark` kept model only; wide report provider null | **Fixed**; one model/provider pair is retained from the same card |
| P1 | Mixed `watchlist` rows were presented as “Официальный ТОП-15” | Live payload: 0 weak signals, 2 observations | **Fixed**; per-card groups and “Отобранные находки” |
| P1 | Date fields looked like typed filters but only changed query prose | `compose_query` string concatenation; API has no date fields | **Fixed in UI**; labelled query context. Real filter remains separate API work |
| P1 | Facts and generated application hypotheses were mixed | Reach fields rendered next to source claims | **Fixed**; Facts / Hypotheses / Checks / Sources tabs |
| P1 | Run provenance/checklist drift/coverage gaps were hidden | v11 rows under v12 code, provider null, IND=0 | **Fixed**; integrity strip and explicit warnings |
| P1 | API/UI were transient root services with `Restart=no` | Units under `/run/systemd/transient` | **Fixed in repo**; persistent loopback units use separate DynamicUser identities and LoadCredential, restart on failure |
| P1 | Positive evidence can lower the score through primary reassignment | P01+P02 example is lower than P02 alone | **Open**; rules change requires new version, eval and independent acceptance |
| P1 | Total connector failure can still surface as `succeeded` | `public_report`/persistence hard-code success | **Open**; requires versioned API/persistence status contract |
| P1 | Intended durable step/evidence ledgers are not populated for existing runs | live DB audit | **Open**; separate persistence increment |
| Release | GitHub mirror absent/unverified | no remote, `gh` absent, repo-scoped auth absent | **Blocked**; SourceCraft push may proceed, dual-push claim may not |

## UI/design decision

The supplied metallic lockup is preserved byte-for-byte at `ui/assets/agi-space-logo-metallic-2026-10-01.jpg` (SHA-256 `b226984701d68a44fa9fa245ffbf061c9f79673076a444b896070b0472a7a1cd`). The UI uses a transparent derived PNG; the compact transparent mark is the favicon. Teal remains an action/evidence colour; brand colour does not encode verdict state.

The workbench has three real modules: live signals, a distinct potential review queue, and full-text lookup of the sealed 29.09 old-tech archive. Potential indices are deterministic triage priorities; archive cards are research hypotheses with explicit diligence holds, not commercial recommendations.

## Verification gates

- Full suite: **220 passed**, isolated PostgreSQL `thin_signals_test_1790887573`; one upstream Starlette/httpx deprecation warning.
- `ruff`, LivingSet link checker, `git diff --check`, `pip check`: **PASS**.
- Dependency audit: no known advisory in application runtime packages. Installer `pip 25.1.1` has 12 advisory records (six distinct IDs); no production packages were modified. Updating the installer is a separate maintenance item. JSON receipt is in outbox `1305367840_1790893410/dependency-audit.json`.
- Desktop 1440 and mobile 390: modules render, no app exceptions or horizontal overflow. Archive query «Кнудсен» returns one of 15 cards. Screenshots are in the same outbox.
- Backup: `/srv/thin-signals-backups/20261001-2230/database.dump`, SHA-256 `24b2b366e4a5d35c0ef9050163d8e35ae6ed31cac24fee7e06da2d63662c0892`; restored in a disposable database, 147 runs matched. Temporary restored database was removed; source data was unchanged.
- Independent code review: pending frozen candidate receipt.
- Staging/production health and rollback SHA: pending deployment receipt.

No scoring weight, threshold, P01–P18 registry, historical eval snapshot, donor file, database schema or secret value was changed.
