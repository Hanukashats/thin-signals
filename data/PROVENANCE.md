# Provenance данных LivingSet v7

Дата копирования: **2026-09-17**.  
Источник: `D:\WORK\HAKATON\SLABYE_SIGGNALY\Thin_Signals_Auto_Goal_Integration_v6_1\`.

Файлы в `data/` — побайтовые копии из пакета 6.1. Не ground truth; разметка 100 строк — `analyst_proposal_unadjudicated`.

| Файл | SHA256 (после копирования) | Назначение |
|---|---|---|
| `pattern_registry.json` | `C7B6C4146EBF26986F3DBE45A0AAD9CA2592F973ACEB61CFD0A50A2E708E230D` | 18 механизмов P01–P18 |
| `predictor_registry.json` | `21B136A5FB37C5FB8051E8E569750925992914FBB7BD988DE3C4EFEFD19FA7D8` | 6 предикторов |
| `dataset_patterns_100.json` | `D259CA6C98AFEDDA547F3FEBC49604874AEC0719762E62DE84E46E0832A839FC` | Разметка всех 100 строк |
| `dataset_patterns_100.csv` | `A0CF074740E5CAD70A3FBFA053C8FC6E192E9EED7800D03BACCEC3013D0631AF` | CSV той же разметки |
| `mapping_summary.json` | (из пакета 6.1) | Сводка паттернов и оценок |
| `donor_checks.json` | (из пакета 6.1) | Контрпримеры radar/POL |
| `archive_integrity.json` | (из пакета 6.1) | Целостность исходного Research Kit |
| `acceptance_ts_ag.json` | копия `integration/acceptance.json` | TS-AG-01…18 |

Контракт объектов: `docs/PROCESSING_CONTRACT.md` — копия v6 из пакета 6.1; для v7 действует LivingSet revision 7.0, семантика объектов без изменений до ADR.

При эволюции паттернов: major change → новая ревизия registry + строка в `plan.yaml` + ADR; старый hash сохраняется в lineage.


## Датасет организаторов

2026-09-22: оператор прислал `100_слабых_технологических_сигналов_сентябрь_2026_2.xlsx` (SHA256 `1349a208671cf9db9b036d9d137036fc8471297b6ec04fce0fc864e75e02ed03`) — байт-в-байт совпадает с `sources/100_слабых_технологических_сигналов_сентябрь_2026 (1).xlsx` и с `input/` донорского пакета 21.09. Один лист «Слабые сигналы», B1:J102, 100 строк, 9 колонок. Только положительные примеры; скрытая разметка у организаторов. Формат колонок — эталон для адаптера `ts eval` (EV-03); обязательные для инференса: №, Технология, Область, Компании, Источники; `Почему это слабый сигнал`, `Стадия`, `Тренд`, `Балл` — metadata, не признаки.
