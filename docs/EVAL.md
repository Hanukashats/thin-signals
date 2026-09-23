# EVAL.md — как измеряется качество логической модели

Revision 7.2 · W2 · требования EV-01..03, TZ-01, TZ-02. Команда: `ts eval`.

## Что измеряем

Бинарная задача ТЗ: `weak_signal` против всего остального (`watchlist`, `mature`, `noise`). Метрики: accuracy, precision, recall, F1, матрица ошибок; дополнительно 3-way матрица, recall по паттерну разметки организаторов, доля правильно отклонённых негативов по классу.

## Данные

| Набор | Файл | Метка | Вход для инференса |
|---|---|---|---|
| Positives 100 | `data/dataset_patterns_100.json` (= XLSX организаторов) | `weak_signal` | Технология, Область, Компании |
| Negatives 70 | `data/negatives_v1.json` | `mature` 45 / `noise` 17 / `watchlist` 8 | те же три поля |

Контаминация: `dataset_rationale`, `dataset_stage`, `dataset_trend`, `dataset_score`, `primary_pattern` организаторов **не подаются** ни экстрактору, ни скореру (тест `test_positives_and_negatives_load_with_contamination_guard`). Для негативов `note`/`category` — тоже только метаданные.

Контрпримеры собраны по классам METHODOLOGY §2.2: выраженные лидеры (M01), принятые стандарты (M02), массовое внедрение (M03), хайп без первичных фактов (M04/M05), старая категория (M06), плюс «известный фронтир» (`watchlist`: роботакси, дрон-доставка — известные направления, по ТЗ не «слабые»).

## Пайплайн

```
row(technology, domain, companies)
  → ts.extract (LLM qwen3.6-35b-a3b, ZDR, strict JSON): статус P01..P18, M01..M06, transition, distinct_actors/events
  → ts.scoring.scorer (детерминированно, rules-0.1.yaml): counters → mature/noise; иначе confidence = Σ w·v + w_ind·ind + w_tr·tr
  → метка по порогам τ / τ_watchlist
```

LLM заполняет чек-лист и не видит формулу; все слагаемые возвращаются в `predictors` (код, статус, вес, вклад, обоснование) — это объяснение для карточки.

### Режимы

- `description` (eval-v1, этот отчёт): нет документов → статус признака не выше `supported`; независимость — proxy: число организаций в поле «Компании» и `distinct_events` от LLM. Это **нижняя оценка**: модель судит по описанию и общим знаниям, без поиска.
- `ledger` (W3): признаки из Documents/Fragments/Claims, `verified` только со ссылкой на фрагмент, `evidence_events`/`independent_origins` из ledger. Пороги из `rules.thresholds`.

## Split и калибровка

Split по семантическим семействам (`FAMILIES` в `ts/eval.py`: №8/45/80, 44/84, 18/59, 47/60, 19/43/82, 2/50/67/69/91, 46/56/75 не разъезжаются; негативы — по `family`). Детерминированный sha256 → ~50/50. τ выбирается перебором по F1 на train (`calibrate_tau`), τ_watchlist = 0.6·τ; на holdout — только отчёт. Откалиброванное значение переносится в `rules-x.y.yaml → modes.<mode>.thresholds` и фиксируется в ADR.

## Формат организаторов (EV-03)

`ts eval --positives file.xlsx|csv|json [--negatives …]`: заголовки маппятся через `ORGANIZER_COLUMNS` (Технология / Область / Компании / Источники / Метка). Если колонки метки нет — все строки считаются `weak_signal` (как в видимой части датасета). Скрытая разметка организаторов: колонка «Метка»/«Класс» с значениями `weak_signal|watchlist|mature|noise` или маппинг через `label_map`.

## Артефакты

`reports/eval/<date>/summary.json`, `records.jsonl` (каждая строка: gold, pred, confidence, predictors, one_line_ru, model_id, provider), `report.md`. Кэш извлечений — `data/extractions/<sha>.json` (ключ: prompt_version|mode|model|text), коммитится для воспроизводимости.

## Известные ограничения eval-v1

- Знания модели, а не поиск: FN там, где LLM не знает нишу; FP там, где описание звучит «по-стартаперски». W3 заменяет описания фрагментами.
- Negatives авторские (один проход); расхождения с LLM-судьёй отмечаются в отчёте, спорные строки переводятся в `watchlist`.
- 170 примеров: доверительный интервал F1 ±~0.07.
