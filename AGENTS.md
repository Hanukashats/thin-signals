# AGENTS.md — Thin Signals LivingSet v7.6

Обязательно для любого агента (Cursor / Codex / Hermes), работающего в этом workspace.
Вход при передаче: `00_START_HERE_HANDOFF_RU.md`.

## Канон

- Норма: базовая архитектура 7.2 (ADR-009) с живыми продолжениями до revision **7.6**. Текущий план: `docs/plan/PLAN_7.6.md`.
- Архивы и `lineage_copies/` — доноры и история, не silent override.
- Прочитать `STATUS.md` и открытые пункты `forks.yaml` перед изменениями.

## Планы и концепт живые

CONCEPT, ARCHITECTURE, plan, forks, requirements **эволюционируют в процессе разработки**. Их дополняют, меняют и версионируют вместе с кодом. Статический план после handoff — нарушение контракта. См. `docs/EVOLUTION.md`.

## Living contract

1. Код и LivingSet одной ревизии. Изменение метода без обновления CONCEPT/ARCHITECTURE/requirements/plan/STATUS/ADR — дефект.
2. Состояния: `proposed → implemented → tested → accepted`. Обсуждение в чате ≠ implemented.
3. Классы правок: `patch` (формулировка), `minor` (задача волны), `major` (развилка, схема, паттерн, приёмка). `major` → DecisionRecord архитектора + ADR при необходимости.
4. Смена scope/критериев → новая `plan_revision` / `goal_revision` с `parent`, `reason`, `impact`. Старый verifier snapshot не переписывать.
5. Production skill / pinned prompt не самоизменяются от одного удачного ответа. Путь: ADR → эксперимент → eval → pin.

## GoAll и роли

`execution.mode: goall` в `plan.yaml`.

| Hat | Может | Не может |
|---|---|---|
| **Architect / Governor (Planner)** | Читать S, выбирать OPEN forks, писать DecisionRecord и `D_t` | Мутировать продукт пока планирует; self-verify свою реализацию; CreateGoal |
| **Implementer** | Писать код/доки в scope `D_t` | Принимать COMPLETED как VERIFIED; расширять scope молча |
| **Independent Verifier** | Оценивать frozen candidate | Править тот же candidate, который принимает |

Цикл волны (7.2): `OBSERVE → EXECUTE → VERIFY → INTEGRATE`.  
**INTEGRATE обязан обновить LivingSet** (минимум STATUS + затронутые ID).

Автовыбор развилки без оператора — только autonomy **A1/A2**. Сразу к человеку: A3/A4, секреты, `operator_gate: true`, security P1, исчерпание бюджета, трактовка ТЗ про обучение модели.

Политика выбора: `BEST_FIT` | `MINIMAL` | `ALTERNATIVE`. LOCKED/DECIDED без нового ADR не переоткрывать.

Волна может: **CONTINUE** / **SKIP** / **JUMP** / **EXIT** (POL) по типизированному finding. Две пустые волны → SKIP/HOLD, не «ещё один промпт». Деградация при одном исполнителе: `degrade: keep_ledger` — режем периферию, не качество ledger/evidence.

## Запреты

- Установка donor Auto-Goal / goal-kernel как второго production-контроллера или второй БД.
- `CreateGoal` / второй Goal bar (инвариант GoalOps).
- Второй writable ledger рядом с PostgreSQL (goal.json как SoT — нет; только read-only проекция).
- Секреты в git/чат; правка `.cursor/settings.json` агентом.
- Заявление precision@15 / «80%» без независимого eval и denominator.
- Подмена X-Agent как авторизация.
- Перенос PASS процесса в «технология доказана».
- Тихий drift: код уехал, CONCEPT/plan зависли.

## Данные

- 100 строк XLSX / `dataset_patterns_100` — seed и design set, **не** ground truth и не нетронутый holdout.
- Оценки и «почему слабый» из таблицы — metadata; не feature для честного предсказания той же оценки.
- P01–P18 — проектные правила в `data/pattern_registry.json`.
- Critical path: логическая модель (METHODOLOGY) + harness + eval + RU UI (ADR-009). Обучение весов — нет.
- Донорские helpers (`donors/`, `reference/`) не правятся; их rc=0 — не gate (KNOWN_GAPS).
- Git SoT: SourceCraft `shats123/thin-signals` (+ зеркало GitHub для сдачи). Секреты — только пути в `docs/ops/secrets.paths.yaml`; на VM101 `.secrets/`.

## Приёмка агентской сессии

Перед stop: STATUS актуален; затронутые requirement IDs обновлены; major forks имеют DecisionRecord; evidence или явное `UNRESOLVED` + next trigger; нет секретов в diff.
