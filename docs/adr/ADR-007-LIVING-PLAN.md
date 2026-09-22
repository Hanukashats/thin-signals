# ADR-007: Living plan и GoAll с архитектором на развилках

Дата: 2026-09-17. Статус: **accepted**. LivingSet revision **7.0**.

## Контекст

План 6.1 §13 требовал `CONCEPT` / `ARCHITECTURE` / `requirements` / `plan` / ADR, но файлов в рабочем дереве не было — норма уже начинала стареть относительно обсуждений. Research Kit CURRENT_BASELINE всё ещё указывал на v5. Нужна **синергия** v4–v6.1 + GoalOps + Auto-Goal audit и механизм, при котором концепт и план эволюционируют вместе с разработкой.

Требование оператора: фазы и волны; автоматический режим GoAll; автовыбор развилок главным архитектором; без зависания старых данных.

## Решение

1. Канон разработки — **LivingSet** в workspace `1/` (этот репозиторий документов): CONCEPT, ARCHITECTURE, requirements.yaml, plan.yaml, forks.yaml, STATUS, EVOLUTION, ADRs, data registries.
2. **Co-evolution**: любое major изменение метода обновляет LivingSet в том же change-set, что и код (когда код появится). Состояния `proposed → implemented → tested → accepted`. Чат ≠ implemented.
3. **Фазы P0–P6** и волны в `plan.yaml`; внутри волны — цикл GoalOps; INTEGRATE обязателен.
4. **`execution.mode: goall`**: главный архитектор (Governor/Planner) читает STATUS/requirements/forks, для OPEN выбирает BEST_FIT|MINIMAL|ALTERNATIVE, пишет DecisionRecord; LOCKED не переоткрывает без ADR. Implementer = один `D_t`; Verifier = frozen candidate; Architect не self-verify.
5. GoAll **не** равен установке Auto-Goal daemon и **не** CreateGoal / второму Goal bar (GoalOps invariant). Product goal_control остаётся ADR-006.
6. Адаптивность волн: CONTINUE/SKIP/JUMP/EXIT (POL). `degrade: keep_ledger`. Две пустые волны → HOLD.
7. Автономия без оператора только A1/A2; `operator_gate` (например `tz.classifier`) и A3/A4 — стоп к человеку.
8. Исторические планы — `docs/lineage/SUPERSESSION.md`; текущие файлы — активная ревизия.

## Рассмотренные варианты

- Оставить только markdown план 6.1 в корне SLABYE_SIGGNALY: снова застынет. **Отклонено**.
- Установить Auto-Goal kernel как оркестратор разработки: второй ledger, известные P1 дефекты донора. **Отклонено** для SoT; идеи перенесены в goal_control + GoAll hats.
- Полный Ruflo/swarm / Meta-Harness: запрещено GoalOps. **Отклонено**.
- LivingSet + GoAll Architect: **выбран**.

## Последствия

- P0 закрывается документами, не кодом.
- Первая архитектурная работа P1 — решить fork `backend.reuse` после inventory.
- Позже CI должен проверять связность ID; до кода — ручной INTEGRATE.
- CONCEPT/plan обязаны обновляться; иначе review отклоняет change-set.

## Условия пересмотра

Новый ADR, если: появляется платформенный PersistentGoal overlay с доказанной заменой STATUS/forks; или оператор явно меняет autonomy class для unattended runs (не самоэскалация).

## Приёмка этого ADR

- Файлы LivingSet 7.0 существуют.
- `plan.yaml` содержит `execution.mode: goall` и фазы P0–P6.
- `forks.yaml` содержит locked/decided/open и политику архитектора.
- `docs/EVOLUTION.md` описывает co-evolution.
- `STATUS.md` указывает P0 / W0-living-plan.
