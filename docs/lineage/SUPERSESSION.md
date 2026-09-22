# Lineage и supersession — Thin Signals

Ревизия документа: **7.0** · Дата среза: **2026-09-17**.  
Этот файл immutable по смыслу lineage: новые редакции планов добавляют строки, не стирают историю.

## Канон сейчас

| Слой | Версия | Статус | Где |
|---|---|---|---|
| Живой комплект разработки и продукта | **v7.2** | **Канон** (ADR-009, 2026-09-22) | VM101 `/opt/thin-signals` → SourceCraft `shats123/thin-signals` |
| LivingSet 7.1 | v7.1 | Поглощена 7.2 (impl path + SourceCraft сохранены; стек сжат; классификатор = логическая модель) | STATUS 2026-09-19; `docs/lineage/handoff_2026-09-21/VERSION_AND_PLAN_RECONCILIATION.md` |
| Донорский пакет Cursor 2026-09-21 | radar 0.1.1 / GoalOps 0.1 / POL 1.2.1 / reference v6.1 | Доноры, без правок | `donors/`, `reference/`, `docs/lineage/handoff_2026-09-21/` (SHA256SUMS 150/150) |
| LivingSet freeze | v7.0 | Поглощена 7.1 (impl path + SourceCraft) | STATUS 2026-09-17 |
| Предметный план + Auto-Goal | v6.1 | Нормативная основа v7 (поглощена) | `weak_signals_production_architecture_v6_1.md`, пакет `Thin_Signals_Auto_Goal_Integration_v6_1` |
| Предметный план без Auto-Goal | v6.0 | Предыдущая норма | `weak_signals_production_architecture_v6.md`, `Thin_Signals_Implementation_Plan_v6_*` |
| ТЗ + harness без паттернов P01–P18 | v5.0 | История / источник TZ-* | Research Kit `01_ORIGINALS/.../weak_signals_production_architecture_v5.md` |
| Оркестратор и расширенное ТЗ | v4.0 | История | Research Kit v4 |
| Ранний «final» стек | stack_final_v1 | История; имя final не задаёт приоритет | Research Kit |
| Research Kit 1.0 | snapshot | Архив доноров; CURRENT_BASELINE внутри устарел (указывает на v5) | `Thin_Signals_Unified_Research_Kit_v1.0_*` |

SHA256 (проверено 2026-09-17):

- v6.0 plan: `cd148a33823fc46f6e8ef8175889de6e5fdf40d588058d4f582691f393c67a92`
- v6.1 plan: `1dc586da778015fa28daba05cd8dd864bfa1064d94d5b3dc56c6858db47325ec`
- Auto-Goal audit: `b70abb013e2a0aa08e7d696cff1c2ad8db9f875757a28ce11a7f4b7df150c77d`

## Что сохранено в v7 из предыдущих планов

| Источник | Сохранено |
|---|---|
| v6 / v6.1 | Frozen LLM, harness-first, 18 паттернов P01–P18, разметка 100 строк, 6 предикторов, четыре оси результата, PROCESSING_CONTRACT, календарь до 29.09 |
| v6.1 / ADR-006 | `goal_control` в PG, COMPLETED ≠ VERIFIED ≠ signal, IterationContract, acceptance TS-AG-01…18; **не** файловый Auto-Goal daemon |
| v5 | Таблица TZ-01…TZ-18 + ADM-01; конфликт «обучение модели» как открытая развилка |
| GoalOps AGiSpace | Роли Planner/Implementer/Verifier; один Cursor Goal; запрет CreateGoal / второго Goal bar; A0–A4 |
| POL 1.2.1 | CONTINUE / SKIP / JUMP / EXIT по типизированному finding |
| Trend Radar | Форма волн W0–W6 как донор структуры; не конкурирующий стек |
| Radar plugin 0.1.1 | Методический донор ledger / signal / evidence / opportunity |
| GoalOps Universal 0.1 | Контракты goal/acceptance/ADR для разработки |

## Что заменено или отклонено

| Было | Решение v7 |
|---|---|
| Research Kit CURRENT_BASELINE → «актуален v5» | Устарело; норматив — LivingSet v7 |
| Файл `architecture_v6.md` внутри пакета 6.1 (заголовок 6.1) | В v7 явные имена: CONCEPT/ARCHITECTURE revision 7.0 |
| Установка Auto-Goal kernel как второго контроллера | Отклонено (ADR-006 / ADR-007) |
| Fine-tuning LLM / LoRA в MVP | Вне критического пути |
| Redis, Kafka, K8s, Temporal, вторая vector DB | Не добавлять до измеренного ограничения |
| BERTopic как обязательный входной фильтр | Нет; singleton-путь независим |
| Radar `validate_run.py` PASS как production gate | Нет; только после межобъектных валидаторов |
| POL simulator deadline до hard_fail | Не переносить без исправления приоритета |
| ThoughtState / NeuroEvolution как runtime | Отложить; lineage только |
| Самоизменение production skill агентом | Запрещено; путь через ADR → eval → pin |

## Заменено в 7.2 (ADR-009) — функция сохранена, компонент убран

| Было (7.1) | 7.2 | Replacement matrix |
|---|---|---|
| `tz.classifier` deferred optional | decided `logical_scorer` (обязателен) | PLAN_7.2 §2, §4 |
| goal_control с TS-AG-01…18 | TS-INV-01…03 в domain; TS-AG → `docs/lineage/baseline_v6_1/integration/acceptance.json` | ADR-009 §E |
| Neo4j-проекция, S3, Procrastinate, OIDC/tenant, BERTopic, Refine-стек, dual adapters | PG nodes/edges, content-addressed snapshots, PG runs + BackgroundTasks, basic-auth, словарь+дедуп TEI, Streamlit, один Python harness | PLAN_7.2 §6 |
| Hermes primary executor | Python harness; Hermes опционально | forks `runtime.adapter` |
| SourceCraft only | SourceCraft + GitHub mirror (ТЗ п. 5) | forks `hosting.sourcecraft` |
| GoAll 11-шаговый цикл | OBSERVE → EXECUTE → VERIFY → INTEGRATE | plan.yaml |

## Конфликты, снятые в v7

1. **v5 «актуальна» vs v6.1 «канон»** — снят: канон LivingSet 7.0; v5 = источник TZ и истории.
2. **Документы 6.1 §13 перечислены, файлов нет** — снят: комплект создан в `1/`.
3. **Процесс Auto-Goal vs предмет P01–P18** — снят: два слоя; процессный PASS ≠ signal qualified.
4. **Обучение модели (ТЗ) vs harness-first** — снят в 7.2: логическая модель (признаки + gates + калиброванные пороги) с отчётом P/R/F1 в формате организаторов; фраза ТЗ «математически (или логически)»; заявление соответствия — только по артефактам прогона `ts eval` (ADR-009).
5. **Hermes vs OpenCode** — зафиксирован default Hermes + fallback после одинакового acceptance (`runtime.adapter`).

## Доноры (не норма)

Пути относительно `D:\WORK\HAKATON\SLABYE_SIGGNALY\`:

- `Thin_Signals_Auto_Goal_Integration_v6_1/` — пакет 6.1
- `Thin_Signals_Implementation_Plan_v6_2026-09-17/` — пакет 6.0
- `Thin_Signals_Unified_Research_Kit_v1.0_2026-09-17/` — архив исследований
- `weak_signals_production_architecture_v6.md` / `_v6_1.md` — корневые копии планов
- `Auto_Goal_Audit_Thin_Signals_2026-09-17.md` — аудит Auto-Goal

Не копировать целиком ZIP Research Kit в workspace `1`. Данные паттернов переносятся с provenance (см. `data/PROVENANCE.md`).
