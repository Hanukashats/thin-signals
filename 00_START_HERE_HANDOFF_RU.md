# Передача другому агенту — Thin Signals LivingSet

Ревизия LivingSet: **7.2** (2026-09-22). Хост записи: Georg VM101 `/opt/thin-signals`; git-канон — SourceCraft `shats123/thin-signals`.
Первая точка входа. Код продукта начат (`ts/`), продукт не развёрнут.

## Порядок чтения

1. Этот файл → `AGENTS.md` → `docs/EVOLUTION.md` → `STATUS.md`.
2. `docs/plan/PLAN_7.2.md` (утверждённый план) → `docs/adr/ADR-009-HARNESS-FIRST-7.2.md`.
3. `CONCEPT.md` → `ARCHITECTURE.md` → `docs/METHODOLOGY.md` → `plan.yaml` → `forks.yaml` → `requirements.yaml`.
4. `donors/README.md` и `docs/lineage/handoff_2026-09-21/KNOWN_GAPS_AND_ACCEPTANCE.md` — что взято у доноров и что нельзя считать gate.

## Что это

Кейс Газпромбанк.Тех «слабые сигналы» (`sources/1. Газпромбанк.Тех.pdf`). Дедлайн **29.09.2026 23:59 МСК**.
Путь: **логическая модель** (признаки P01–P18 + контр-признаки M01–M06 + gates + калиброванные пороги), frozen LLM из списка ТЗ как извлекатель фактов, Python harness, PostgreSQL+pgvector, Streamlit RU. Без обучения весов. Reuse сервисов бэкенда VM101 по URL.

## Проверка после клонирования

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
python3 scripts/check_living_links.py          # OK requirements=… waves=… forks=…
.venv/bin/python -m pytest -q ts/tests         # 39 passed (W1)
cd reference && python3 test_policy.py         # 15 OK (донор v6.1 без правок)
docker compose up -d pg && docker compose exec pg psql -U ts -d thin_signals -c 'select extversion from pg_extension where extname=$$vector$$'
```

Секретов в git нет; пути — `docs/ops/secrets.paths.yaml`. Для `pg` нужен `.secrets/pg_password`.

## Инвариант

LivingSet и код — одна ревизия. INTEGRATE каждой волны обновляет `STATUS.md` и затронутые ID. Исторические срезы — `docs/lineage/` (immutable). Правила скоринга версионируются (`rules-x.y`) и меняются только через повторный `ts eval`.
