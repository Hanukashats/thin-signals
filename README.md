# Thin Signals

Сервис для автоматизированного сбора и анализа зарождающихся трендов («слабые сигналы») в научно-технологических отраслях — кейс Газпромбанк.Тех. LivingSet revision **7.2**. Дедлайн: **29.09.2026 23:59 МСК**.

Подход: **логическая модель** слабого сигнала (18 механизмов P01–P18, 6 контр-признаков зрелости, порядок gates, воспроизводимая уверенность с reason codes) + открытый поиск по первичным источникам + русский интерфейс. LLM из списка ТЗ извлекает факты из прочитанных источников; решение считает код. Весов не обучаем — см. `docs/METHODOLOGY.md`, ADR-009.

Статус: W1 (контракт 7.2 + скелет). Продукт не развёрнут. Смотри `STATUS.md`.

## Быстрый старт (разработка)

```bash
git clone https://git.sourcecraft.dev/shats123/thin-signals.git && cd thin-signals
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest -q
mkdir -p .secrets && tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32 > .secrets/pg_password
docker compose up -d pg
cp .env.example .env
```

## Структура

| Путь | Роль |
|---|---|
| `docs/plan/PLAN_7.2.md`, `docs/adr/` | Утверждённый план, ADR-006…009 |
| `CONCEPT.md`, `ARCHITECTURE.md`, `docs/METHODOLOGY.md`, `docs/PROCESSING_CONTRACT.md` | Продукт, стек, логическая модель, объекты |
| `plan.yaml`, `forks.yaml`, `requirements.yaml`, `STATUS.md` | Волны, развилки, требования, текущее состояние |
| `ts/` | Код: `schemas/` (pydantic-контракты), `scoring/policy.py` (gates), `tests/` |
| `reference/` | Reference policy v6.1 без правок + 15 тестов |
| `donors/` | Radar 0.1.1, GoalOps 0.1, POL 1.2.1 — без правок, provenance в `donors/README.md` |
| `data/` | P01–P18, предикторы D01–D06, разметка 100 строк (seed, не ground truth) |
| `sources/` | ТЗ и XLSX организаторов |
| `docs/lineage/`, `lineage_copies/` | История планов v4–v7.1, донорский handoff 21.09 |
| `compose.yaml` | PostgreSQL 16 + pgvector; профили `laptop` / `vm101` |

## Волны

| Волна | Даты | Суть |
|---|---|---|
| W1 | 22–23.09 | LivingSet 7.2, доноры, репо, скелет `ts/`, PG |
| W2 | 23–24.09 | Скоринг rules-0.1, корпус контрпримеров, `ts eval`, P/R/F1 |
| W3 | 24–26.09 | Live path: поиск → snapshot → извлечение → gates → ТОП-15 |
| W4 | 26–27.09 | Streamlit RU UI |
| W5–W6 | 27–29.09 | README/Docker, зеркало GitHub, слайды 7–11, верификация, сдача |

Секреты только в `.secrets/` (gitignored); пути — `docs/ops/secrets.paths.yaml`.
