# Форматы данных и связи

Все основные JSON — UTF-8; ranking.csv — UTF-8 с BOM. research/ хранит оригинальную форму, в том числе разную точность дат. Шаблоны templates/ предназначены для заполнения, а не для немедленного расчёта.

## candidates.json — массив карточек

| Поля | Смысл |
|---|---|
| id, name, family | Устойчивый ID, точное название и область |
| history_class, historical_year, history | Тип преемственности, ориентир года и утверждение о прошлом |
| barrier_then, change_now | Прежнее ограничение и современное изменение |
| evidence, scientific_scope_limit | Что измерено и где заканчивается вывод |
| history_sources, current_sources, source_ids | Ссылки на ID источников; общий набор должен включать необходимые свидетельства |
| first_product, buyers | Гипотеза продукта и предполагаемые покупатели; не договорённости |
| risk, test, kill, horizon | Возражение, решающий тест, критерий прекращения и оценка срока |
| market_query, market_findings | Поисковый запрос и ограниченный вывод коммерческого поиска |
| scores, why_scores | Оценки восьми осей и исходное сводное обоснование |
| as_of | Дата информационного среза карточки |
| commercial_status, ip_status, funding_status | Состояния рынка, доступа и финансирования |
| science_status, retracted, retraction_screen | Научный статус и проверка исправлений |
| trl_estimate | Экспертная оценка зрелости, не сертификация |
| system_comparison_status | proposed или validated; второй требует выполненного сравнения |
| decisive_test_status | proposed или agreed; второй требует согласованного протокола |

Некоторые карточки дополнительно имеют market_sources. В исходном коде он не используется отдельно: соответствующие ID должны попадать в source_ids.

## Статусы

commercial_status: unknown / unoccupied_verified / commercial / scaled / licensed_exclusive / funded_business.
ip_status: unknown / access_verified / unavailable.
retracted: true / false / null. null — не установлено. Полный проход требует отдельного retraction_screen=screened_no_flag.
science_status: в исходных карточках experimental_support; refuted вызывает исключение.
funding_status — пояснительное поле; само по себе не закрывает и не открывает ворота. Код использует commercial_status.
У остальных произвольных значений, кроме специально разрешённого прохода, сохраняется HOLD.

Булево false у отзыва не равнозначно завершённому исследованию ретракций. Отсутствие данных Crossref об отзыве не позволяет автоматически назначить screened_no_flag.

## sources.json — реестр свидетельств

id; title; url; published; source_type; supports; doi; accessed; access_level; limitations.
Для проверенных DOI добавлены metadata_verified, crossref_published, canonical_title.

published может быть годом, годом-месяцем, полной датой или null. accessed — дата доступа. source_type описывает источник, но сам по себе не является рейтингом надёжности.
page_text — доступ к тексту страницы; indexed_text_or_abstract — доступ к фрагменту/аннотации. Ни одно автоматически не означает прочтение всех приложений.
supports — краткое указание, какое утверждение источник поддерживает.
metadata_verified — DOI получен через Crossref; это не независимое подтверждение научного результата.

## model.json

weights — восемь весов с суммой 100.
thresholds — minimum_age, research_priority_lower, investigate_lower, partner_review_lower.
as_of — дата среза.
stream — resurrection или emergence.
profile — содержательное название политики финансирования; в коде не является переключателем правил.
exclude_commercial_states — статусы, вызывающие исключение.
version/note — версия и смысловые ограничения.

## ranking.json

id/name/rank; score_lower/score_upper/unknown_weight; age_years_approx; decision;
fully_qualified; partner_review_ready; failures[]; holds[]; missing_dimensions[].

Это производный результат. Для изменения вывода менять входные данные с обоснованием и пересчитывать; не редактировать ранг вручную.

## exclusions.json и retired_candidates.json

exclusions: id, name, decision, reason, source_ids, иногда candidate_id и reference_url.
decision бывает exclude, hold_outside_15, out_of_historical_scope. Следовательно, все 14 записей нельзя называть 14 доказанно коммерциализированными технологиями.
У X08 источник сохранён как reference_url при пустом source_ids; ссылка присутствует в JSON, но исходный генератор не выводит её в таблицу отчёта. Эталон сохранён без исправления; новый отчёт должен учитывать оба поля.
retired_candidates — пять полных снятых карточек с добавленными основаниями пересмотра.

## Сетевые снимки и журнал поиска

metadata_snapshot.json: первоначальные 28 DOI, два запроса Crossref и два неуспешных Europe PMC.
metadata_doi_final.json: 43 полученных DOI.
Это отобранные поля ответов API, а не архив полных страниц издателей.
market_search_log.json: дата, ограничения, массив 20 query с id кандидата, временем проверки и URL. URL — обнаруженные указатели; не каждый результат релевантен и подтверждён.

## Новые формы доказательств

templates/evidence_record.json добавляет для будущего запуска granular claim_id, тип утверждения fact/inference/hypothesis, дату события, точное место источника, условия/единицы и противоречия. Эти поля рекомендуются для нового workflow; их не следует считать существовавшими в исходных 15 карточках.

templates/score_justification.json помогает фиксировать причины по каждой оси.
templates/search_record.json и decision_record.json — формы журнала запросов и изменений.
templates/comparison.md — форма сопоставления запуска с эталоном.

## Связи

candidate.source_ids → source.id;
candidate.history_sources/current_sources → source.id;
ranking.id → candidate.id;
exclusion.candidate_id → retired candidate.id, если поле присутствует;
market query.id → активная или снятая карточка;
evidence_record.candidate_id/source_id → соответствующие реестры нового запуска.

Не переиспользовать ID снятого кандидата для совершенно другой технологии. В исходном опыте новые кандидаты получили T16–T20.

