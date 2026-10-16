# Передача другому агенту — Thin Signals LivingSet

Ревизия LivingSet: **7.8**, дата поставочного пакета **2026-09-29**. Хост записи и production: Georg VM101 `/opt/thin-signals`; git-канон — SourceCraft `shats123/thin-signals`.
Первая точка входа. Закрытый стенд развёрнут на `https://tsignal.aispaces.ru`; фактическое состояние и открытые дефекты — в `STATUS.md` и аудите 2026-10-01.

## Порядок чтения

1. Этот файл → `AGENTS.md` → `docs/EVOLUTION.md` → `STATUS.md`.
2. `docs/plan/PLAN_7.8.md` → родительские планы 7.7…7.2 → `docs/adr/ADR-009-HARNESS-FIRST-7.2.md` и `docs/adr/ADR-010-LATEST-WORKSPACE.md`.
3. `CONCEPT.md` → `ARCHITECTURE.md` → `docs/METHODOLOGY.md` → `plan.yaml` → `forks.yaml` → `requirements.yaml`.
4. `donors/README.md` и `docs/lineage/handoff_2026-09-21/KNOWN_GAPS_AND_ACCEPTANCE.md` — что взято у доноров и что нельзя считать gate.

## Что это

Кейс Газпромбанк.Тех «слабые сигналы» (`sources/1. Газпромбанк.Тех.pdf`). Исходный дедлайн **29.09.2026 23:59 МСК**.
Путь: **логическая модель** (признаки P01–P18 + контр-признаки M01–M06 + gates + калиброванные пороги), frozen LLM из списка ТЗ как извлекатель фактов, Python harness, PostgreSQL+pgvector, Streamlit RU. Без обучения весов. Reuse сервисов бэкенда VM101 по URL.

## Проверка после клонирования

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
python3 scripts/check_living_links.py          # OK requirements=… waves=… forks=…
.venv/bin/python -m pytest -q ts/tests         # use an isolated test database, never production
cd reference && python3 test_policy.py         # 15 OK (донор v6.1 без правок)
docker compose up -d pg && docker compose exec pg psql -U ts -d thin_signals -c 'select extversion from pg_extension where extname=$$vector$$'
```

Секретов в git нет; пути — `docs/ops/secrets.paths.yaml`. Для `pg` нужен `.secrets/pg_password`.

## Инвариант

LivingSet и код — одна ревизия. INTEGRATE каждой волны обновляет `STATUS.md` и затронутые ID. Исторические срезы — `docs/lineage/` (immutable). Правила скоринга версионируются (`rules-x.y`) и меняются только через повторный `ts eval`.

## Хосты

Production — VM101 `/opt/thin-signals`. VM230 `agi-thin-signals` — исторический dev/demo checkout; его актуальность нужно проверять отдельно. Код синхронизируется только через SourceCraft.
