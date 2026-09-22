# Манифест архива передачи

Имя архива: `Thin_Signals_LivingSet_Handoff_v7.1_2026-09-19.zip`  
Корень внутри: LivingSet workspace `1/` плюс копии ключевых донорских планов в `lineage_copies/`.

## LivingSet (канон)

| Путь | Зачем |
|---|---|
| `00_START_HERE_HANDOFF_RU.md` | Старт для нового агента |
| `README.md` | Навигация |
| `AGENTS.md` | Правила агента |
| `CONCEPT.md` | Концепт (живой) |
| `ARCHITECTURE.md` | Стек и границы |
| `STATUS.md` | Текущая волна |
| `plan.yaml` | Фазы P0–P6, GoAll |
| `forks.yaml` | Развилки |
| `requirements.yaml` | TZ / SC / TS-AG / LP |
| `docs/EVOLUTION.md` | Co-evolution |
| `docs/PROCESSING_CONTRACT.md` | Объекты и gates |
| `docs/adr/ADR-006…008` | Решения |
| `docs/lineage/SUPERSESSION.md` | v4–v7 |
| `docs/ops/SOURCECRAFT.md` | Хостинг (без секретов) |
| `docs/ops/secrets.paths.yaml` | Только пути к SEC |
| `docs/audits/*` | Аудиты этой сессии |
| `data/*` | Паттерны, 100 строк, provenance |
| `schemas/README.yaml` | Stub схемы |
| `scripts/check_living_links.py` | Связность ID |
| `.gitignore` | Исключения |

## lineage_copies (не норма)

Копии планов/аудита 6.1 из родительской папки, чтобы пакет был самодостаточным. Канон — LivingSet 7.1.

## Исключено намеренно

- Значения секретов
- Research Kit ZIP (~16 MB)
- Исходный Auto-Goal kernel
- `1/.git` (история локальных коммитов не нужна в zip; файлы включены)
