# STATUS.md — Thin Signals LivingSet

Updated: **2026-09-22** · Plan revision: **7.2** · Deadline: **2026-09-29 23:59 MSK**
Host of record: Georg VM101 `/opt/thin-signals` (cursor-agent). Plan: `docs/plan/PLAN_7.2.md`, ADR-009.

## Current

| Field | Value |
|---|---|
| Phase | **P1 Contract72** |
| Wave | **W1-contract** — in_progress |
| Done in W1 | LivingSet 7.2; ADR-009; METHODOLOGY; PLAN_7.2 persisted; donors/ + reference/ + lineage handoff with hashes; `ts/` skeleton (schemas, scoring/policy F03-fixed, 39 tests OK); compose pg (pgvector 0.8.6 on PG16 verified `CREATE EXTENSION vector`); venv `.venv` |
| Left in W1 | — (2026-09-23: Alembic v1 `90f5cc54dd46` applied on VM230, 11 tables incl. pgvector; `ts seed import` → 100 `seed_unverified`, idempotent; `ts llm zdr-check`/`probe` OK: qwen3.6 via Venice 0.7 s, gpt-5.6-luna via Azure 1.5 s; 47 tests) → W1 closes after independent check |
| Next wave | W2-scorer-eval: rules-0.1.yaml, negatives_v1.json, `ts eval`, P/R/F1 report |
| Blockers (operator) | dataset: operator re-sent XLSX 2026-09-22 (`…_2.xlsx`, SHA256 `1349a208…`), byte-identical to `sources/` — treated as the official **visible** dataset (100 positives; hidden labels stay with organizers, so `ts eval` adapter must accept rows with only Технология/Область/Компании/Источники); presentation template not received; LLM provider keys (Yandex AI Studio / GigaChat / OpenAI direct) — fork `llm.provider` operator_gate |

## Decisions this INTEGRATE (7.2, 2026-09-22)

| Fork | Choice | Class |
|---|---|---|
| `tz.classifier` | logical_scorer | BEST_FIT |
| `backend.reuse` | extend_via_urls | BEST_FIT |
| `graph.neo4j` | drop_pg_tables (closed) | MINIMAL |
| `sources.epo_cordis` | stub_unavailable (closed) | MINIMAL |
| `ui.stack` | streamlit_ru | MINIMAL |
| `goal.controller` | three_invariants_in_domain | MINIMAL |
| `runtime.adapter` | python_harness_hermes_optional | MINIMAL |
| `hosting.sourcecraft` | sourcecraft_plus_github_mirror | BEST_FIT |
| `llm.provider` | **open — operator gate** | — |

## Donor pack 2026-09-21

ZIP SHA256 `cfa98189…697646`; SHA256SUMS 150/150 OK. Radar 0.1.1, GoalOps 0.1, POL 1.2.1 (byte-identical to VM copy), reference policy (15/15 OK). Provenance: `donors/README.md`; gaps: `docs/lineage/handoff_2026-09-21/KNOWN_GAPS_AND_ACCEPTANCE.md`.

## Requirement snapshot

- implemented: LP-01…07, DN-01, RM-01
- planned W1: TZ-11, TZ-12, TS-INV-01…03
- blocked: TZ-14 (template)
- planned W1: LLM-01 (OpenRouter ZDR decided 2026-09-22, key in place)
- removed to lineage: SC-01, SC-04, SC-05, SC-08, SC-10, TS-AG-01…16, TS-AG-18

## Hosts

- VM230 `agi-thin-signals` (home PVE, 192.168.5.230) provisioned 2026-09-23: Ubuntu 24.04, Docker 29.8, sing-box AMS1 egress, repo checkout `9d6f3f1`, 39 tests pass, pg+pgvector healthy. See `docs/ops/VM230.md`, `docs/ops/hosts.yaml`. Pending: NetBird setup-key.

## SourceCraft

Repo `https://sourcecraft.dev/shats123/thin-signals` (private). **Pushed 2026-09-22:** `main` @ `3c0fbcb` (LP-05 implemented). Push auth: HTTPS + `GIT_ASKPASS=.secrets/git-askpass.sh`. SSH key not registered (UI-only).

## Next trigger

1. W2: rules-0.1.yaml, negatives_v1.json, `ts eval` (P/R/F1, organizer-format adapter).
2. W2: `ts/scoring/rules-0.1.yaml`, `data/negatives_v1.json`, `ts eval`, `reports/eval_<date>.md`.
3. Operator: presentation template; optional dedicated OpenRouter key for thin-signals.
