# Контракт обработки v6 (LivingSet v7)

Статус: спецификация для реализации, не утверждение о готовом API.  
LivingSet: revision **7.0**. Источник: пакет Thin Signals Auto-Goal Integration v6.1. Семантика объектов сохранена; эволюция — через ADR + `plan_revision` (см. `docs/EVOLUTION.md`).

## Runtime boundary

`RuntimeAdapter.run(ResearchTask) -> ResearchResult`, `cancel(run_id)`, `health()`.

ResearchTask: tenant_id, run_id, task_id, as_of, objective, pattern_ids, allowed_tools, allowed_models, evidence_bundle_refs, budget_tokens, budget_requests, deadline, schema_version, skill_hashes.

ResearchResult: task_id, status, proposed_claims, proposed_edges, cited_fragments, unresolved_questions, suggested_next_action, artifacts, usage, model_id, instruction_hash. Адаптер не может сам выставить production gate PASS. Ошибка/timeout возвращают частичный результат с явным состоянием, а не удачный пустой JSON.

Task states: queued/running/retryable/failed/cancelled/succeeded. Signal states: candidate/needs_evidence/watchlist/qualified/established/disputed/rejected. Это разные автоматы. `succeeded` задачи извлечения не делает signal `qualified`.

Идемпотентность: уникальная комбинация tenant, corpus_version, input_hash, step, step_version. Lease и heartbeat отдельно от аналитических состояний. Повтор внешнего запроса не создаёт новый event или grant. Checkpoint и outbox записываются транзакционно в PG; Neo4j применяет upsert с event sequence, затем подтверждает checkpoint.

## Объекты

| Объект | Обязательные поля |
|---|---|
| Document | id, tenant_id, url, title, language, source_type, content_hash, blob_ref, fetched_at, available_at, availability_basis, access_status |
| Fragment | id, document_id, start/end или page+quote, fragment_hash |
| Entity | id, type, canonical_name, aliases, identifiers, resolution_status |
| EvidenceEvent | id, type, entity_ids, event_at, planned_for, available_at, origin_group_ids, source_refs, dedup_status |
| Claim | id, subject_id, predicate, typed_value, unit, scope, kind, status, critical, evidence_for, evidence_against, event_id |
| Edge | id, from_entity_id, to_entity_id, relation, claim_ids, status, valid_from, valid_to, available_at |
| Observation | predictor_id, cohort_version, period_start/end, raw_counts, denominator, coverage, units, computed_at, code_version |
| Decision | id, signal_id, as_of, rule_version, required_gates, reason_codes, unresolved, next_action, review_at, reentry_trigger |

Для event_at/planned_for/available_at допустим UNKNOWN только с причиной. Факт без даты публичной доступности не допускается в строгий исторический backtest. Значение `available_at` нельзя вычислять просто из даты, написанной в тексте.

### Типы событий

research_result, replication, patent_publication, grant_awarded, funding_closed, funding_discussed, product_announced, product_released, pilot_started, deployment_confirmed, contract_signed, roadmap_announced, standard_draft, standard_adopted, regulation_published, regulation_effective, repository_release, job_opened, job_closed, negative_result.

**planned_for > as_of разрешено для roadmap_announced**, если сам анонс доступен до cutoff. Такой event не учитывается как deployment_confirmed. Опровержение одного performance claim не запрещает вообще хранить всю технологию: решение действует на конкретную гипотезу/scope.

## Семантические валидаторы после JSON Schema

1. Все references существуют, принадлежат tenant и разрешены текущему пользователю.
2. Evidence ссылается на прочитанный snapshot; цитата совпадает с fragment, число и единицы найдены или явно помечены как вычисленные.
3. `available_at <= as_of` для утверждения о прошлом; даты и версии источников согласованы. Непроверенная доступность не PASS.
4. Полный набор required gates определяется версией профиля, не агентом. У каждого PASS есть reason и допустимое основание. Пустой набор claims/gates никогда не qualifying.
5. Origin independence и event dedup не выводятся из числа URL. Unknown independence не повышает подтверждённый breadth.
6. Концы графа существуют; edge имеет тип, supporting claim и scoped status. Нет `supplier_of` из сходства описаний.
7. Growth допускается только при сопоставимых источниках, протоколе и завершённых окнах. Даже формально полный API ответ не устраняет index coverage bias.
8. Для критического verified finding проверяется актуальность и scope. Слабое отрицательное свидетельство идёт на verify, не на безусловный reject.
9. Любой auto/HOLD результат содержит причину, trigger и видимую нехватку данных. Поля uncertainty не скрываются в UI.
10. Agent action — предложение. Мутации fact ledger, gate decisions и внешние действия исполняет domain service через разрешённые команды.

## Профили источников

Scientific: mechanism, paper/version, code, dataset, experimental_conditions, replications.
Patent: family definition, publication, priority, applicants, CPC/IPC, jurisdiction, claims scope; не правовое заключение о патентоспособности.
Capital/grants: recipient legal entity, event type, amount/currency, announcement/close dates, status, independent primary sources.
Deployment: client/operator, environment, stage, paid/LOI, operating date, scale, conditions, measurement method.
Security/regulatory: threat model, affected version, attack/defense distinction, jurisdiction, adopted/effective dates.
Ecosystem: repo IDs, releases, users/bots, organisation linkage, historical coverage, observations, definitions.

Для нового направления сначала строится словарь механизма и отрицательных терминов, затем выбираются источники; не переносить AI-словарь из 100 строк на химию без проверки покрытия.

## Референсный код

`reference/policy.py` демонстрирует только порядок проверок. Он получает уже проверенные summary facts; не устанавливает их истинность и не заменяет перечисленные выше валидаторы. Коды `REJECT_OR_REFRAME`/`REFRAME_CHILD` требуют предметного решения о scope. `normalized_growth` — арифметический helper для равных завершённых дней; не статистический тест.
