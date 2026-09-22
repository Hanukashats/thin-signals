# Контракт сохраняемого прогона

Копировать assets/run.template.json, заполнить as_of, mode, objective, scope и ограничения. Типовой запуск: python3 scripts/validate_run.py run.json.

Sources: id, locator, origin_group_id, event_id, available_at (ISO date или null), fetched_at, access_status (read/unavailable).
Claims: id, text, kind, status, critical, evidence_for/evidence_against (source IDs). Для гипотез источники могут отсутствовать. verified fact требует прочитанного доступного evidence; доступность и независимость проверять содержательно.
Edges: from, to, relation (supplier_of/capable_of/candidate_for/depends_on), evidence_refs. supplier_of требует источника, реально подтверждающего связь.
Gates: id, state PASS/UNKNOWN/FAIL, confidence verified/supported/weak, scope, evidence_refs.
Decision: action, scope, readiness, rationale, review_at; для HOLD ещё reentry_trigger.
Investment: assessed; при assessed=true указать instrument, price_as_of, financials_as_of, valuation_status complete/incomplete/unknown, access_status verified/unknown, evidence_refs. Наличие полей не доказывает качество оценки.
Forecasts: question, issued_at, resolve_by, outcome_rule; probability опционально 0–1.

Валидатор проверяет структуру, ID, ссылки, использование будущего evidence, source-read и часть gates. WARN не PASS содержательной экспертизы. Он не извлекает данные, не проверяет подлинность сайта, семантику цитаты, полноту финансовой модели или фактическую независимость. Человеческая/агентная проверка обязательна для выводов; инструмент не генерирует рекомендацию покупки.
