# donors/ — исходные skills-доноры Thin Signals

Получено: `Thin_Signals_Cursor_Donors_2026-09-21.zip` (SHA256 `cfa98189…697646`, полный хеш в `docs/lineage/handoff_2026-09-21/ARCHIVE_SHA256.txt`). Проверка `SHA256SUMS`: 150/150 OK (2026-09-22, VM101).

Файлы доноров **скопированы без правок**. Производные (адаптированные) skills и код живут в `ts/` и `skills/` с указанием происхождения. Донорские `install.py` / plugin manifest не запускать.

| Донор | Версия | Путь | Лицензия | Ключевые хеши (SHA256) | Решение 7.2 |
|---|---|---|---|---|---|
| AgiSpace Opportunity Radar | 0.1.1 (author Pavel Shats) | `agispace-opportunity-radar-0.1.1/skills/agispace-opportunity-radar/` | не указана в пакете (собственная разработка оператора) | SKILL.md `8201a3cd…8f132`; validate_run.py `de53d7ec…4b3cb` | **adapt**: references `signals.md`, `evidence.md`, `provenance.md`, `run-contract.md` → METHODOLOGY / source_trust; `validate_run.py` только структурный, не production gate (F02) |
| GoalOps Universal | 0.1 / 0.1.0 | `goalops-universal-0.1/` | MIT | SKILL.md `60a6ae91…6a76d` | **adapt (dev only)**: role contracts, quality gates, forecast/handoff schemas → AGENTS.md и DecisionRecord; не второй контроллер |
| Product Opportunity Lab | MASTER 1.2.1 | `product-opportunity-lab-1.2.1/skill/` (+ `tools/`, `tests/`) | MIT (Product Opportunity Lab contributors) | SKILL.md `d170d465…7e5d6`; audit_evidence.py `4f455c16…4f4ec`; simulate_routes.py `558fe509…845ee` | **adapt**: `references/adaptive-control-flow.md` (CONTINUE/SKIP/JUMP/EXIT), `research-and-evidence.md`, `trend-radar.md`; helpers с известными дефектами F01 (пустой evidence → rc 0) и deadline-before-hard_fail не переносить как gate |
| Reference policy v6.1 | из пакета 6.1 | `../reference/policy.py`, `test_policy.py` | часть пакета 6.1 | `8e72fd27…7e37f`; `b2917a99…61cd5` | **reuse as reference**: 15 тестов OK на VM101 2026-09-22; порядок gates переносится в `ts/scoring/policy.py` с исправлением F03 (типы до membership) |

Байт-в-байт сверки 2026-09-22:

- POL donor `source/skills/product-opportunity-lab` == `/opt/agi-space-backend/.cursor/skills/product-opportunity-lab` (`diff -rq` пуст; локальная копия admitted 2026-09-08, commit `ddc412d`). Локальную не перезаписывали.
- `data/*` донора == `data/*` репозитория (pattern_registry, predictor_registry, dataset_patterns_100 json/csv).
- `input/*.xlsx` и `input/*.pdf` == `sources/` репозитория (`1349a208…`, `226bf6b1…`).

Что из ZIP **не** скопировано: `packages/*.zip` (бинарные дубликаты), `baseline/v6_1/data` (дубликат `data/`), `baseline/v6_1/weak_signals_production_architecture_v6.md` (дубликат `lineage_copies/*_v6_1.md`), полный `source/` POL кроме skill/tools/tests (аудиты и patch — в `docs/audits/Library_Audit_2026-09-21_RU.md`), `input/` (дубликат `sources/`).

Известные дефекты доноров и приёмка адаптации: `docs/lineage/handoff_2026-09-21/KNOWN_GAPS_AND_ACCEPTANCE.md`, `docs/audits/Library_Audit_2026-09-21_RU.md` §7 (F01–F07).
