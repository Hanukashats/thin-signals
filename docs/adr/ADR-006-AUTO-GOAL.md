# ADR-006: перенос механизмов Auto‑Goal в Thin Signals

Дата: 2026-09-17. Статус: **accepted (design)**; product implementation pending.  
Источник: пакет `Thin_Signals_Auto_Goal_Integration_v6_1/integration/ADR-006-AUTO-GOAL.md`. LivingSet revision **7.0** сохраняет решение без изменений смысла.

## Контекст

План v6 уже использует PG/Procrastinate, Hermes adapter, evidence ledger и 18 предметных паттернов. Auto‑Goal добавляет полезную дисциплину целей, но его файловый kernel не должен конкурировать с этим состоянием. Проверены commit `4e3257d8…`, 59 штатных тестов и 14 дополнительных проб донора.

## Решение

1. Встроить `goal_control` как модуль существующего Python backend, с формальными схемами и транзакционными командами.
2. Адаптировать compiler/catalog/context concepts; сохранять происхождение заимствованного кода и применимые права. Не копировать весь kernel/installer/hook как новую production-платформу.
3. PG — единственный writable ledger; Procrastinate доставляет jobs, Hermes выполняет разрешённые задания. LangGraph остаётся резервом; OpenCode проверяется тем же adapter acceptance.
4. Разделить process completion, verification, claim state и signal decision. Проверенное исследование может дать REJECT/HOLD.
5. Верифицировать frozen candidate с полным индексом evidence и unresolved findings; не полагаться на текстовый PASS.
6. Критерии immutable в ревизии; эволюция создаёт новый snapshot с явным impact и переносом только валидных результатов.
7. Локальный Auto‑Goal для разработки — отдельный добровольно подключаемый контур после исправлений; он не управляет runtime пользователей.

## Рассмотренные варианты

- Взять весь daemon: быстро для одиночного локального процесса, но появляется второй ledger. **Отклонено** для product runtime.
- Взять только SKILL.md: недостаточно для продуктовых gates.
- Переписать весь стек на новый оркестратор: не связано с находками и увеличивает риск срока. **Отклонено**.
- Перенести механизм в существующий domain: **выбран**.

## Последствия

Нужны IterationContract, revision/idempotency/receipts, principal policy, typed research progress и verification bundle. Нельзя считать process VERIFIED доказательством качества технологии.

## Приёмка

`data/acceptance_ts_ag.json` / requirements TS-AG-01…18. Статус ADR не означает, что проверки уже прошли на backend.

## Связь с v7

Fork `goal.controller` = **locked** → `goal_control_in_pg`. Dev automation uses GoAll on the same Cursor Goal (ADR-007), not this daemon.
